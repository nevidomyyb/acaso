"""Classificação de tema e recusa com LLM aberto em CPU numa EC2 (ADR-004).

O modelo roda numa EC2 só com CPU: llama.cpp + Qwen3 (GGUF Q4_K_M). A saída JSON é garantida pela
gramática do llama.cpp, a partir do schema de etl/classificacao.py.

Escopo: só as conversas da 1ª sessão de cada usuário (3.361), que é o que a análise de retorno usa.

Subcomandos (rodam na máquina local; a EC2 é criada por infra/aws/ec2/classificacao.sh):
  preparar  gera o JSONL com o corpo de cada requisição   -> data/work/cpu_{versao}_{modelo}_sessao1[_amostraN]/
  enviar    copia entrada.jsonl e llm_runner.py para o S3  -> s3://$ACASO_S3_BUCKET/cpu/<pasta>/
  coletar   baixa saida.jsonl do S3 e grava o resultado    -> data/enriched/temas_{versao}_{modelo}.parquet
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classificacao import (  # noqa: E402
    NOME_SCHEMA,
    SCHEMA,
    bucket,
    carregar_entradas,
    cliente_s3,
    entrada_vazia,
    ler_sistema,
    linha_resultado,
    regra_vazio,
    resumir,
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


def corpo_cpu(e: dict, sistema: str, extra: dict | None = None) -> dict:
    """Corpo OpenAI-compatível do llama-server, com saída JSON forçada pelo schema."""
    return (extra or {}) | {
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": texto_entrada(e)}],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": NOME_SCHEMA, "schema": SCHEMA, "strict": True},
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


def cmd_preparar(args: argparse.Namespace) -> None:
    sistema = ler_sistema(args.versao)
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
    s3, b = cliente_s3(), bucket()
    p = pasta(args)
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
    cliente_s3().download_file(bucket(), f"{prefixo_s3(args)}/saida.jsonl", str(destino))
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
    resumir(df)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versao", default="v2")
    ap.add_argument("--modelo", default="qwen3_8b", choices=sorted(MODELOS))
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
