"""Confere o arquivo de classificação (ADR-004) antes da carga: colunas, valores da taxonomia e erros.

Uso: python etl/conferir_classificacao.py data/enriched/temas_v2_qwen3_8b.parquet
Sai com código 1 se o arquivo não serve para a carga.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classificacao import RECUSAS, TEMAS  # noqa: E402

COLUNAS = ["conversa_id", "tema", "recusa", "recusa_regex", "versao_prompt", "modelo"]


def problemas(df: pd.DataFrame) -> list[str]:
    faltam = [c for c in COLUNAS if c not in df.columns]
    if faltam:
        return [f"colunas ausentes: {faltam}"]
    p = []
    if df.empty:
        p.append("arquivo vazio")
    if df.conversa_id.duplicated().any():
        p.append(f"conversa_id repetido: {int(df.conversa_id.duplicated().sum())}")
    validos = df.tema.dropna()
    if not validos.isin(TEMAS).all():
        p.append(f"tema fora da taxonomia: {sorted(set(validos) - set(TEMAS))}")
    if not df.recusa.dropna().isin(RECUSAS).all():
        p.append("recusa fora da taxonomia")
    if "erro" in df.columns and df.erro.notna().any():
        p.append(f"registros com erro: {int(df.erro.notna().sum())}")
    return p


def main() -> int:
    arq = Path(sys.argv[1])
    df = pd.read_parquet(arq)
    p = problemas(df)
    if p:
        print(f"classificação inválida ({arq.name}): " + "; ".join(p), file=sys.stderr)
        return 1
    versoes = sorted({f"{v}:{m}" for v, m in df[["versao_prompt", "modelo"]].dropna().itertuples(index=False)})
    print(f"classificação ok: {arq.name} | {len(df)} conversas | {df.tema.nunique()} temas | "
          f"recusa total {int((df.recusa == 'total').sum())} | {', '.join(versoes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
