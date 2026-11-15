"""Ambiente do Alembic. Migrations escritas à mão (sem autogenerate): o schema é SQL explícito."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool


def url() -> str:
    """ACASO_DB_URL no formato postgresql://...; o SQLAlchemy usa o driver psycopg 3."""
    u = os.environ["ACASO_DB_URL"]
    return u.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(url=url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
