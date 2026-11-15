"""Banco de teste para os testes marcados com `db`: cria um banco novo no Postgres do compose e apaga no fim.

Rode com:  docker-compose up -d postgres
           ACASO_DB_URL_TESTE=postgresql://acaso:acaso_local@localhost:5433/acaso .venv/bin/python -m pytest -q
A URL aponta para o servidor; o teste cria e apaga o banco `acaso_teste_<pid>`, sem tocar no banco `acaso`.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parent.parent
BRUTA = RAIZ / "data" / "raw" / "wildchat_br.parquet"


def url_servidor() -> str | None:
    return os.environ.get("ACASO_DB_URL_TESTE")


def pular_sem_banco() -> None:
    if not url_servidor():
        pytest.skip("defina ACASO_DB_URL_TESTE para rodar os testes de banco")
    if not BRUTA.exists():
        pytest.skip("base bruta ausente em data/raw (rode etl/download.py e etl/recorte_brasil.py)")


def trocar_banco(url: str, banco: str, usuario: str | None = None, senha: str | None = None) -> str:
    p = urlsplit(url)
    auth = f"{usuario or p.username}:{senha or p.password}@" if (usuario or p.username) else ""
    return urlunsplit((p.scheme, f"{auth}{p.hostname}:{p.port or 5432}", f"/{banco}", "", ""))


@contextmanager
def banco_temporario():
    """Cria um banco vazio e devolve a URL dele. Apaga o banco no fim, mesmo se o teste falhar."""
    servidor = url_servidor()
    nome = f"acaso_teste_{os.getpid()}"
    with psycopg.connect(trocar_banco(servidor, "postgres"), autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {nome}")
        c.execute(f"CREATE DATABASE {nome}")
    try:
        yield trocar_banco(servidor, nome)
    finally:
        with psycopg.connect(trocar_banco(servidor, "postgres"), autocommit=True) as c:
            c.execute(f"DROP DATABASE IF EXISTS {nome} WITH (FORCE)")
