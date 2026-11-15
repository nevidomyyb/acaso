"""Conexão com a base analítica: pool do psycopg 3, papel só de leitura (acaso_leitura)."""

from __future__ import annotations

from flask import Flask, current_app, g
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

ULTIMA_CARGA = """
    SELECT carga_id, definicao_versao, dados_de, dados_ate, fim_utc
    FROM meta_carga WHERE status = 'ok' ORDER BY carga_id DESC LIMIT 1
"""


def iniciar(app: Flask) -> None:
    url = app.config["ACASO_DB_URL"]
    if not url:
        raise RuntimeError("defina ACASO_DB_URL")
    # open=False + abrir na 1ª consulta: a API sobe mesmo se o banco demorar, e o /api/health mostra o estado
    app.extensions["pool"] = ConnectionPool(url, min_size=1, max_size=4, open=False,
                                            kwargs={"row_factory": dict_row, "autocommit": True})


def _pool() -> ConnectionPool:
    pool: ConnectionPool = current_app.extensions["pool"]
    if pool.closed:
        pool.open(wait=True, timeout=10)
    return pool


def consultar(sql: str, params: dict | None = None) -> list[dict]:
    """Executa um SELECT e devolve as linhas como dicionários. Conta as linhas para o log da requisição."""
    with _pool().connection() as c:
        linhas = c.execute(sql, params or {}).fetchall()
    g.linhas = getattr(g, "linhas", 0) + len(linhas)
    return linhas


def ultima_carga() -> dict | None:
    linhas = consultar(ULTIMA_CARGA)
    return linhas[0] if linhas else None
