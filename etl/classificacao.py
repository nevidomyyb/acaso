"""Base da classificação de tema e recusa: taxonomia, entrada, schema e validação (ADR-004).

Fonte única dos valores de `tema` e `recusa`. Usado por:
  - etl/classificar_cpu.py          prepara, envia e coleta a classificação na EC2
  - etl/validacao_classificacao.py  amostra de rótulo manual e acurácia
  - etl/definicoes.py               agrupa os 11 temas em 7 grupos (BDR-009)

Quem chama o modelo é o executor em etl/llm_runner.py, que roda na EC2 ao lado do llama-server.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
REGIAO_PADRAO = "us-east-1"
MAX_CHARS_USUARIO = 2000  # p90 da 1ª mensagem = 1.158 chars
MAX_CHARS_ASSISTENTE = 1500  # p50 da 1ª resposta = 1.072 chars; recusas aparecem no início
MAX_CHARS_MOTIVO = 90  # limita a geração: em CPU, cada token de saída custa ~50 ms

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

# O llama.cpp converte este schema em gramática e só deixa o modelo gerar JSON que caiba nele.
NOME_SCHEMA = "classificacao"
SCHEMA = {
    "type": "object",
    "properties": {
        "motivo": {
            "type": "string",
            "description": "Até 12 palavras que explicam a escolha.",
            "maxLength": MAX_CHARS_MOTIVO,
        },
        "tema": {"type": "string", "enum": TEMAS},
        "recusa": {"type": "string", "enum": RECUSAS},
        "confianca": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["motivo", "tema", "recusa", "confianca"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------- entrada


def carregar_env(caminho: Path = RAIZ / ".env") -> None:
    """Carrega AWS_* e ACASO_* do .env sem sobrescrever o ambiente. Nunca imprime valores."""
    if not caminho.exists():
        return
    for linha in caminho.read_text().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        if valor and chave not in os.environ:
            os.environ[chave] = valor


def cliente_s3():
    """Cliente S3: único serviço AWS que os scripts locais chamam (entrada e saída da EC2)."""
    import boto3
    from botocore.config import Config

    carregar_env()
    regiao = os.environ.get("AWS_DEFAULT_REGION", REGIAO_PADRAO)
    return boto3.client("s3", region_name=regiao, config=Config(retries={"max_attempts": 8, "mode": "adaptive"}))


def bucket() -> str:
    carregar_env()
    b = os.environ.get("ACASO_S3_BUCKET")
    if not b:
        raise SystemExit("defina ACASO_S3_BUCKET no .env")
    return b


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


def texto_entrada(e: dict) -> str:
    """O que o modelo lê: 1ª mensagem e 1ª resposta, truncadas."""
    return (
        f"<mensagem_pessoa>\n{truncar(e['msg_usuario'], MAX_CHARS_USUARIO)}\n</mensagem_pessoa>\n\n"
        f"<resposta_assistente>\n{truncar(e['msg_assistente'], MAX_CHARS_ASSISTENTE)}\n</resposta_assistente>"
    )


def ler_sistema(versao: str) -> str:
    return (RAIZ / "etl" / "prompts" / f"classificacao_{versao}.md").read_text()


# ---------------------------------------------------------------------------- saída


def validar(dados: dict, base: dict) -> dict:
    """Confere os campos da classificação. Devolve os campos ou `erro`."""
    tema, recusa, conf = dados.get("tema"), dados.get("recusa"), dados.get("confianca")
    if tema not in TEMAS or recusa not in RECUSAS or not isinstance(conf, int | float) or not 0 <= conf <= 1:
        return {**base, "erro": f"saída inválida: {json.dumps(dados, ensure_ascii=False)[:200]}"}
    return {**base, "tema": tema, "recusa": recusa, "confianca": float(conf), "motivo": dados.get("motivo")}


def linha_resultado(e: dict, resultado: dict, fonte: str, versao: str, modelo: str | None = None) -> dict:
    from recusa_regex import recusa_regex

    return {
        "conversa_id": e["conversa_id"],
        "tema": resultado.get("tema"),
        "recusa": resultado.get("recusa"),
        "confianca": resultado.get("confianca"),
        "motivo": resultado.get("motivo"),
        "recusa_regex": recusa_regex(e["msg_assistente"]),
        "fonte": fonte,
        "modelo": modelo if fonte == "llm" else None,
        "versao_prompt": versao,
        "input_tokens": resultado.get("input_tokens"),
        "output_tokens": resultado.get("output_tokens"),
        "erro": resultado.get("erro"),
    }


def regra_vazio(e: dict, versao: str) -> dict:
    # Entrada vazia (bug do coletor): não há pedido a classificar e o LLM não é chamado.
    r = {"tema": "saudacao_teste", "recusa": "nao", "confianca": 1.0, "motivo": "mensagem vazia"}
    return linha_resultado(e, r, "regra_vazio", versao)


def resumir(df: pd.DataFrame) -> None:
    llm = df[df.fonte == "llm"]
    print(f"\nregistros: {len(df)} | via LLM: {len(llm)} | erros: {df.erro.notna().sum()}")
    print(f"tokens in/out: {llm.input_tokens.sum():,.0f} / {llm.output_tokens.sum():,.0f}")
    if "segundos" in llm:
        print(f"segundos por registro (mediana / p90): {llm.segundos.median():.1f} / {llm.segundos.quantile(0.9):.1f}")
    print("\ntema:\n" + df.tema.value_counts(dropna=False).to_string())
    print("\nrecusa (LLM) × recusa_regex:\n" + pd.crosstab(df.recusa, df.recusa_regex).to_string())
