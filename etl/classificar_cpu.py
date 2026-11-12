"""Classificação de tema e recusa com LLM aberto em CPU numa EC2 (ADR-011; substitui o ADR-004 no desafio).

Motivo: a conta AWS nova não tem cota no Bedrock (nenhum modelo) nem GPU. O enunciado exige que o LLM rode
na AWS. Então o modelo roda numa EC2 só com CPU: llama.cpp + Qwen3-4B-Instruct-2507 (GGUF Q4_K_M).

Escopo: só as conversas da 1ª sessão de cada usuário (3.361), que é o que a análise de retorno usa.

Subcomandos (rodam na máquina local; a EC2 é criada por infra/aws/ec2/classificacao.sh):
  preparar  gera o JSONL com o corpo de cada requisição   -> data/work/cpu_{versao}_sessao1[_amostraN]/entrada.jsonl
  enviar    copia entrada.jsonl e llm_runner.py para o S3  -> s3://$ACASO_S3_BUCKET/cpu/<pasta>/
  coletar   baixa saida.jsonl do S3 e grava o resultado    -> data/enriched/temas_{versao}_qwen3_4b.parquet

O prompt é o mesmo arquivo do Bedrock (etl/prompts/classificacao_{versao}.md). Só a linha que manda usar a
ferramenta vira "responda com JSON"; o formato é garantido pela gramática JSON do llama.cpp (mesmo schema).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_bedrock import (  # noqa: E402
    FERRAMENTA,
    carregar_entradas,
    cliente,
    entrada_vazia,
    ler_sistema,
    linha_resultado,
    regra_vazio,
    texto_entrada,
    validar,
)
from definicoes import PADRAO, construir  # noqa: E402
from llm_runner import ler_jsonl  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BRUTA = RAIZ / "data" / "raw" / "wildchat_br.parquet"
VOLUME = RAIZ / "data" / "raw" / "wildchat_volume_diario.parquet"

# Chave = nome usado em infra/aws/ec2/classificacao.sh (repo, revisão e SHA-256 fixados lá).
MODELOS = {
    "qwen3_4b": {"rotulo": "Qwen3-4B-Instruct-2507-Q4_K_M@llama.cpp-v0.9.0", "extra": {}},
    # Qwen3-8B é híbrido: sem "thinking", a saída JSON começa direto (e o tempo cai).
    "qwen3_8b": {
        "rotulo": "Qwen3-8B-Q4_K_M@llama.cpp-v0.9.0",
        "extra": {"chat_template_kwargs": {"enable_thinking": False}},
    },
}
MAX_TOKENS = 160
MAX_CHARS_MOTIVO = 90  # limita a geração: em CPU, cada token de saída custa ~50 ms

LINHA_FERRAMENTA = "Registre a classificação com a ferramenta `registrar_classificacao`."
LINHA_JSON = "Responda só com um objeto JSON com os campos `motivo`, `tema`, `recusa` e `confianca`, nesta ordem."


def sistema_json(versao: str) -> str:
    sistema = ler_sistema(versao)
    if LINHA_FERRAMENTA not in sistema:
        raise SystemExit(f"prompt {versao}: linha da ferramenta não encontrada; ajuste LINHA_FERRAMENTA")
    return sistema.replace(LINHA_FERRAMENTA, LINHA_JSON)


def schema_json() -> dict:
    s = copy.deepcopy(FERRAMENTA["input_schema"])
    s["properties"]["motivo"]["maxLength"] = MAX_CHARS_MOTIVO
    return s


def corpo_cpu(e: dict, sistema: str, extra: dict | None = None) -> dict:
    """Corpo OpenAI-compatível do llama-server, com saída JSON forçada pelo schema."""
    return (extra or {}) | {
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": texto_entrada(e)}],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": FERRAMENTA["name"], "schema": schema_json(), "strict": True},
        },
        "cache_prompt": True,  # reaproveita o prompt de sistema já processado no slot
    }


def ids_primeira_sessao(con: duckdb.DuckDBPyConnection, bruta: str, volume: str | None) -> set[str]:
    """Conversas com atividade na 1ª sessão de cada usuário, pelas definições padrão (BDR-001 a 008)."""
    construir(con, bruta, PADRAO, volume_diario=volume)
    linhas = con.execute("SELECT DISTINCT conversa_id::VARCHAR FROM eventos_sessao WHERE sessao_seq = 1").fetchall()
    return {c for (c,) in linhas}


def selecionar_sessao1(bruta: Path, volume: Path | None, n: int, semente: int) -> list[dict]:
    con = duckdb.connect()
    con.execute("SET memory_limit = '3GB'")
    ids = ids_primeira_sessao(con, str(bruta), str(volume) if volume and volume.exists() else None)
    entradas = [e for e in carregar_entradas(bruta) if e["conversa_id"] in ids]
    return random.Random(semente).sample(entradas, n) if n else entradas


def pasta(args: argparse.Namespace) -> Path:
    sufixo = f"_amostra{args.amostra_n}" if args.amostra_n else ""
    return RAIZ / "data" / "work" / f"cpu_{args.versao}_{args.modelo}_sessao1{sufixo}"


def prefixo_s3(args: argparse.Namespace) -> str:
    return f"cpu/{pasta(args).name}"


def bucket() -> str:
    from classify_bedrock import carregar_env

    carregar_env()
    b = os.environ.get("ACASO_S3_BUCKET")
    if not b:
        raise SystemExit("defina ACASO_S3_BUCKET no .env")
    return b


def cmd_preparar(args: argparse.Namespace) -> None:
    sistema = sistema_json(args.versao)
    selecao = selecionar_sessao1(args.bruta, VOLUME, args.amostra_n, args.semente)
    p = pasta(args)
    p.mkdir(parents=True, exist_ok=True)
    llm = [e for e in selecao if not entrada_vazia(e)]
    with (p / "entrada.jsonl").open("w") as f:
        for e in llm:
            registro = {"recordId": e["conversa_id"], "body": corpo_cpu(e, sistema, MODELOS[args.modelo]["extra"])}
            f.write(json.dumps(registro) + "\n")  # ensure_ascii: U+2028 no texto não quebra a linha
    (p / "selecao.json").write_text(json.dumps(sorted(e["conversa_id"] for e in selecao)))
    print(f"selecionadas: {len(selecao)} | via LLM: {len(llm)} | vazias (regra): {len(selecao) - len(llm)} -> {p}")


def cmd_enviar(args: argparse.Namespace) -> None:
    s3, b, p = cliente("s3"), bucket(), pasta(args)
    s3.upload_file(str(p / "entrada.jsonl"), b, f"{prefixo_s3(args)}/entrada.jsonl")
    s3.upload_file(str(RAIZ / "etl" / "llm_runner.py"), b, f"{prefixo_s3(args)}/llm_runner.py")
    print(f"s3://{b}/{prefixo_s3(args)}/ (entrada.jsonl, llm_runner.py)")


def interpretar_cpu(r: dict) -> dict:
    uso = r.get("uso", {})
    base = {"input_tokens": uso.get("prompt_tokens"), "output_tokens": uso.get("completion_tokens")}
    if r.get("erro"):
        return {**base, "erro": r["erro"]}
    try:
        dados = json.loads(r["conteudo"])
    except (json.JSONDecodeError, TypeError):
        return {**base, "erro": f"JSON inválido (fim={r.get('fim')}): {str(r.get('conteudo'))[:200]}"}
    return validar(dados, base)


def montar(selecao: list[dict], brutos: dict[str, dict], versao: str, rotulo: str) -> pd.DataFrame:
    linhas = []
    for e in selecao:
        if entrada_vazia(e):
            linhas.append(regra_vazio(e, versao))
            continue
        r = brutos.get(e["conversa_id"])
        resultado = interpretar_cpu(r) if r else {"erro": "ausente na saída"}
        linha = linha_resultado(e, resultado, "llm", versao, modelo=rotulo)
        linha["segundos"] = r.get("segundos") if r else None
        linhas.append(linha)
    return pd.DataFrame(linhas)


def cmd_coletar(args: argparse.Namespace) -> None:
    p = pasta(args)
    destino = p / "saida.jsonl"
    cliente("s3").download_file(bucket(), f"{prefixo_s3(args)}/saida.jsonl", str(destino))
    brutos: dict[str, dict] = {}
    for r in ler_jsonl(destino):
        if r["recordId"] not in brutos or not r.get("erro"):  # a última tentativa sem erro vale
            brutos[r["recordId"]] = r
    ids = set(json.loads((p / "selecao.json").read_text()))
    selecao = [e for e in carregar_entradas(args.bruta) if e["conversa_id"] in ids]
    df = montar(selecao, brutos, args.versao, MODELOS[args.modelo]["rotulo"])
    nome = f"{'amostra' if args.amostra_n else 'temas'}_{args.versao}_{args.modelo}"
    saida = (p if args.amostra_n else RAIZ / "data" / "enriched") / f"{nome}.parquet"
    saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(saida, index=False)
    print(f"-> {saida}")
    resumir_cpu(df)


def resumir_cpu(df: pd.DataFrame) -> None:
    llm = df[df.fonte == "llm"]
    print(f"\nregistros: {len(df)} | via LLM: {len(llm)} | erros: {df.erro.notna().sum()}")
    print(f"tokens in/out: {llm.input_tokens.sum():,.0f} / {llm.output_tokens.sum():,.0f}")
    print(f"segundos por registro (mediana / p90): {llm.segundos.median():.1f} / {llm.segundos.quantile(0.9):.1f}")
    print("\ntema:\n" + df.tema.value_counts(dropna=False).to_string())
    print("\nrecusa (LLM) × recusa_regex:\n" + pd.crosstab(df.recusa, df.recusa_regex).to_string())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versao", default="v1")
    ap.add_argument("--modelo", default="qwen3_4b", choices=sorted(MODELOS))
    ap.add_argument("--bruta", type=Path, default=BRUTA)
    ap.add_argument("--amostra-n", type=int, default=0, help="0 = todas da 1ª sessão; N > 0 = amostra fixa")
    ap.add_argument("--semente", type=int, default=42)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("preparar", "enviar", "coletar"):
        sub.add_parser(nome)
    args = ap.parse_args()
    {"preparar": cmd_preparar, "enviar": cmd_enviar, "coletar": cmd_coletar}[args.cmd](args)


if __name__ == "__main__":
    main()
