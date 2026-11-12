"""Classificação de tema e recusa com Claude Haiku 4.5 no Amazon Bedrock (ADR-004).

Subcomandos:
  amostra         on-demand numa amostra, para ajustar o prompt  -> data/enriched/amostra_{versao}.parquet
  preparar-batch  gera o JSONL do batch                          -> data/work/batch_{versao}[_amostraN]/entrada.jsonl
  enviar-batch    envia o JSONL ao S3 e cria o job                -> data/work/batch_{versao}/job.json
  status          mostra o status do job
  coletar         baixa a saída do S3 e grava o resultado         -> data/enriched/temas_{versao}.parquet

Com `--amostra-n N`, os subcomandos de batch trabalham numa amostra fixa (mesma semente do `amostra`) e gravam
data/enriched/amostra_{versao}.parquet. Serve para ajustar o prompt via batch quando a cota on-demand é zero.

On-demand e batch usam o MESMO corpo de requisição (função `corpo_requisicao`), então o prompt validado
na amostra é exatamente o que roda no batch. Credenciais: variáveis AWS_* do ambiente ou do `.env`.
O `docker compose up` não roda este script: a carga lê o parquet versionado em data/enriched/.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recusa_regex import recusa_regex  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
MODELO = "us.anthropic.claude-haiku-4-5-20251001-v1:0"  # batch do Haiku 4.5 exige inference profile
REGIAO_PADRAO = "us-east-1"
MAX_CHARS_USUARIO = 2000  # p90 da 1ª mensagem = 1.158 chars
MAX_CHARS_ASSISTENTE = 1500  # p50 da 1ª resposta = 1.072 chars; recusas aparecem no início
MAX_TOKENS = 200
PRECO_IN, PRECO_OUT = 1.00 / 1e6, 5.00 / 1e6  # premissa §12.1 (on-demand); batch ≈ 50%
MIN_REGISTROS_BATCH = 100  # quota do Bedrock

TEMAS = [
    "saudacao_teste",
    "estudo_escola",
    "trabalho_profissional",
    "programacao_tecnologia",
    "traducao_reescrita",
    "criativo_ficcao",
    "roleplay_personagem",
    "conteudo_adulto",
    "conselho_pessoal",
    "conhecimento_geral",
    "outro",
]
RECUSAS = ["nao", "parcial", "total"]

FERRAMENTA = {
    "name": "registrar_classificacao",
    "description": "Registra o tema da 1ª mensagem da pessoa e se o assistente recusou o pedido.",
    "input_schema": {
        "type": "object",
        "properties": {
            "motivo": {"type": "string", "description": "Até 12 palavras que explicam a escolha."},
            "tema": {"type": "string", "enum": TEMAS},
            "recusa": {"type": "string", "enum": RECUSAS},
            "confianca": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["motivo", "tema", "recusa", "confianca"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------- entrada


def carregar_env(caminho: Path = RAIZ / ".env") -> None:
    """Carrega AWS_* do .env sem sobrescrever o ambiente. Nunca imprime valores."""
    if not caminho.exists():
        return
    for linha in caminho.read_text().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        if valor and chave not in os.environ:
            os.environ[chave] = valor


def carregar_entradas(bruta: Path) -> list[dict]:
    """1ª mensagem do usuário e 1ª resposta do assistente de cada conversa do Brasil."""
    con = duckdb.connect()
    linhas = con.execute(f"""
        SELECT conversation[1].turn_identifier::VARCHAR AS conversa_id,
               list_filter(conversation, lambda c: c.role = 'user')[1].content AS msg_usuario,
               list_filter(conversation, lambda c: c.role = 'assistant')[1].content AS msg_assistente
        FROM read_parquet('{bruta}')
        WHERE country = 'Brazil'
        ORDER BY conversa_id
    """).fetchall()
    return [{"conversa_id": c, "msg_usuario": u or "", "msg_assistente": a or ""} for c, u, a in linhas]


def truncar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[:limite] + " [...truncado]"


def entrada_vazia(e: dict) -> bool:
    return not e["msg_usuario"].strip()


def corpo_requisicao(e: dict, sistema: str) -> dict:
    texto = (
        f"<mensagem_pessoa>\n{truncar(e['msg_usuario'], MAX_CHARS_USUARIO)}\n</mensagem_pessoa>\n\n"
        f"<resposta_assistente>\n{truncar(e['msg_assistente'], MAX_CHARS_ASSISTENTE)}\n</resposta_assistente>"
    )
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "system": sistema,
        "messages": [{"role": "user", "content": [{"type": "text", "text": texto}]}],
        "tools": [FERRAMENTA],
        "tool_choice": {"type": "tool", "name": FERRAMENTA["name"]},
    }


# ---------------------------------------------------------------------------- saída


def interpretar(saida: dict) -> dict:
    """Extrai e valida a chamada da ferramenta. Devolve campos ou `erro`."""
    uso = saida.get("usage", {})
    base = {"input_tokens": uso.get("input_tokens"), "output_tokens": uso.get("output_tokens")}
    blocos = [b for b in saida.get("content", []) if b.get("type") == "tool_use"]
    if not blocos:
        return {**base, "erro": f"sem tool_use (stop_reason={saida.get('stop_reason')})"}
    dados = blocos[0].get("input", {})
    tema, recusa, conf = dados.get("tema"), dados.get("recusa"), dados.get("confianca")
    if tema not in TEMAS or recusa not in RECUSAS or not isinstance(conf, int | float) or not 0 <= conf <= 1:
        return {**base, "erro": f"saída inválida: {json.dumps(dados, ensure_ascii=False)[:200]}"}
    return {**base, "tema": tema, "recusa": recusa, "confianca": float(conf), "motivo": dados.get("motivo")}


def linha_resultado(e: dict, resultado: dict, fonte: str, versao: str) -> dict:
    return {
        "conversa_id": e["conversa_id"],
        "tema": resultado.get("tema"),
        "recusa": resultado.get("recusa"),
        "confianca": resultado.get("confianca"),
        "motivo": resultado.get("motivo"),
        "recusa_regex": recusa_regex(e["msg_assistente"]),
        "fonte": fonte,
        "modelo": MODELO if fonte == "llm" else None,
        "versao_prompt": versao,
        "input_tokens": resultado.get("input_tokens"),
        "output_tokens": resultado.get("output_tokens"),
        "erro": resultado.get("erro"),
    }


def regra_vazio(e: dict, versao: str) -> dict:
    # Entrada vazia (bug do coletor): não há pedido a classificar e o LLM não é chamado.
    r = {"tema": "saudacao_teste", "recusa": "nao", "confianca": 1.0, "motivo": "mensagem vazia"}
    return linha_resultado(e, r, "regra_vazio", versao)


def resumir(df: pd.DataFrame, fator_preco: float) -> None:
    llm = df[df.fonte == "llm"]
    custo = (llm.input_tokens.sum() * PRECO_IN + llm.output_tokens.sum() * PRECO_OUT) * fator_preco
    print(f"\nregistros: {len(df)} | via LLM: {len(llm)} | erros: {df.erro.notna().sum()}")
    print(f"tokens in/out: {llm.input_tokens.sum():,.0f} / {llm.output_tokens.sum():,.0f} | custo ≈ US$ {custo:.2f}")
    print("\ntema:\n" + df.tema.value_counts(dropna=False).to_string())
    print("\nrecusa (LLM) × recusa_regex:\n" + pd.crosstab(df.recusa, df.recusa_regex).to_string())


# ---------------------------------------------------------------------------- AWS


def cliente(servico: str):
    import boto3
    from botocore.config import Config

    carregar_env()
    regiao = os.environ.get("AWS_DEFAULT_REGION", REGIAO_PADRAO)
    cfg = Config(retries={"max_attempts": 8, "mode": "adaptive"}, read_timeout=90)
    return boto3.client(servico, region_name=regiao, config=cfg)


def ler_sistema(versao: str) -> str:
    return (RAIZ / "etl" / "prompts" / f"classificacao_{versao}.md").read_text()


def selecionar(entradas: list[dict], n: int, semente: int) -> list[dict]:
    """Amostra fixa (n > 0) ou todas as conversas (n = 0). Mesma semente = mesma amostra."""
    return random.Random(semente).sample(entradas, n) if n else entradas


def cmd_amostra(args: argparse.Namespace) -> None:
    sistema = ler_sistema(args.versao)
    amostra = selecionar(carregar_entradas(args.bruta), args.amostra_n or 200, args.semente)
    rt = cliente("bedrock-runtime")

    def classificar(e: dict) -> dict:
        if entrada_vazia(e):
            return regra_vazio(e, args.versao)
        try:
            resp = rt.invoke_model(modelId=MODELO, body=json.dumps(corpo_requisicao(e, sistema)))
            return linha_resultado(e, interpretar(json.loads(resp["body"].read())), "llm", args.versao)
        except Exception as exc:  # registra e segue; a linha fica com `erro`
            return linha_resultado(e, {"erro": f"{type(exc).__name__}: {exc}"[:300]}, "llm", args.versao)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.paralelo) as pool:
        df = pd.DataFrame(list(pool.map(classificar, amostra)))
    saida = args.saida or RAIZ / "data" / "enriched" / f"amostra_{args.versao}.parquet"
    saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(saida, index=False)
    print(f"{len(df)} classificadas em {time.time() - t0:.0f}s -> {saida}")
    resumir(df, fator_preco=1.0)


def pasta_batch(args: argparse.Namespace) -> Path:
    sufixo = f"_amostra{args.amostra_n}" if args.amostra_n else ""
    return RAIZ / "data" / "work" / f"batch_{args.versao}{sufixo}"


def cmd_preparar(args: argparse.Namespace) -> None:
    sistema = ler_sistema(args.versao)
    selecao = selecionar(carregar_entradas(args.bruta), args.amostra_n, args.semente)
    entradas = [e for e in selecao if not entrada_vazia(e)]
    if len(entradas) < MIN_REGISTROS_BATCH:
        raise SystemExit(f"batch exige ≥ {MIN_REGISTROS_BATCH} registros; há {len(entradas)}")
    pasta = pasta_batch(args)
    pasta.mkdir(parents=True, exist_ok=True)
    with (pasta / "entrada.jsonl").open("w") as f:
        for e in entradas:
            f.write(json.dumps({"recordId": e["conversa_id"], "modelInput": corpo_requisicao(e, sistema)}) + "\n")
    print(f"{len(entradas)} registros -> {pasta / 'entrada.jsonl'}")


def cmd_enviar(args: argparse.Namespace) -> None:
    pasta = pasta_batch(args)
    carimbo = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    prefixo = f"batch/{pasta.name}/{carimbo}"
    cliente("s3").upload_file(str(pasta / "entrada.jsonl"), args.bucket, f"{prefixo}/entrada.jsonl")
    job = cliente("bedrock").create_model_invocation_job(
        jobName=f"acaso-{pasta.name.replace('_', '-')}-{carimbo}".lower(),
        roleArn=args.role_arn,
        modelId=MODELO,
        inputDataConfig={"s3InputDataConfig": {"s3Uri": f"s3://{args.bucket}/{prefixo}/entrada.jsonl"}},
        outputDataConfig={"s3OutputDataConfig": {"s3Uri": f"s3://{args.bucket}/{prefixo}/saida/"}},
        timeoutDurationInHours=24,
    )
    info = {"job_arn": job["jobArn"], "bucket": args.bucket, "prefixo": prefixo, "criado_em": carimbo}
    (pasta / "job.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    info = json.loads((pasta_batch(args) / "job.json").read_text())
    job = cliente("bedrock").get_model_invocation_job(jobIdentifier=info["job_arn"])
    print(job["status"], job.get("message", ""))


def cmd_coletar(args: argparse.Namespace) -> None:
    info = json.loads((pasta_batch(args) / "job.json").read_text())
    s3 = cliente("s3")
    objs = s3.list_objects_v2(Bucket=info["bucket"], Prefix=f"{info['prefixo']}/saida/").get("Contents", [])
    chaves = [o["Key"] for o in objs if o["Key"].endswith(".jsonl.out")]
    if not chaves:
        raise SystemExit("saída ainda não disponível")
    brutos: dict[str, dict] = {}
    for chave in chaves:
        corpo = s3.get_object(Bucket=info["bucket"], Key=chave)["Body"].read().decode()
        (pasta_batch(args) / Path(chave).name).write_text(corpo)
        for linha in corpo.splitlines():
            reg = json.loads(linha)
            saida = reg.get("modelOutput")
            brutos[reg["recordId"]] = interpretar(saida) if saida else {"erro": json.dumps(reg.get("error"))[:300]}

    linhas = []
    for e in selecionar(carregar_entradas(args.bruta), args.amostra_n, args.semente):
        if entrada_vazia(e):
            linhas.append(regra_vazio(e, args.versao))
        else:
            resultado = brutos.get(e["conversa_id"], {"erro": "ausente na saída"})
            linhas.append(linha_resultado(e, resultado, "llm", args.versao))
    df = pd.DataFrame(linhas)
    nome = f"amostra_{args.versao}" if args.amostra_n else f"temas_{args.versao}"
    saida = RAIZ / "data" / "enriched" / f"{nome}.parquet"
    df.to_parquet(saida, index=False)
    print(f"-> {saida}")
    resumir(df, fator_preco=0.5)


def main() -> None:
    carregar_env()  # antes do argparse: os padrões de --bucket e --role-arn vêm do .env
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versao", default="v1")
    ap.add_argument("--bruta", type=Path, default=RAIZ / "data" / "raw" / "wildchat_br.parquet")
    ap.add_argument("--amostra-n", type=int, default=0, help="0 = todas as conversas; N > 0 = amostra fixa")
    ap.add_argument("--semente", type=int, default=42)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("amostra")
    a.add_argument("--paralelo", type=int, default=4)
    a.add_argument("--saida", type=Path)
    sub.add_parser("preparar-batch")
    env = sub.add_parser("enviar-batch")
    env.add_argument("--bucket", default=os.environ.get("ACASO_S3_BUCKET"), required=False)
    env.add_argument("--role-arn", default=os.environ.get("ACASO_BEDROCK_ROLE_ARN"), required=False)
    sub.add_parser("status")
    sub.add_parser("coletar")
    args = ap.parse_args()
    if args.cmd == "enviar-batch" and not (args.bucket and args.role_arn):
        ap.error("enviar-batch precisa de --bucket e --role-arn (ou ACASO_S3_BUCKET / ACASO_BEDROCK_ROLE_ARN)")
    {
        "amostra": cmd_amostra,
        "preparar-batch": cmd_preparar,
        "enviar-batch": cmd_enviar,
        "status": cmd_status,
        "coletar": cmd_coletar,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
