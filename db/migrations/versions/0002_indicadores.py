"""Indicadores do dashboard: IC de Wilson, regras de amostra e as views de retorno em 7 dias.

O SQL de cada indicador mora aqui (e no docs/METODOLOGIA.md §11). A API só filtra e soma estas views; a regra de
IC, de amostra suficiente e de k-anonimato é a mesma para todo endpoint.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LEITURA = "acaso_leitura"
Z95 = 1.959963984540054  # igual a etl/estatistica.py

# Dimensões que a tela pode abrir. "geral" = todos os novatos. Nível nulo vira 'sem_valor'.
DIMENSOES = {
    "geral": "'todos'",
    "tema_grupo": "tema_grupo",
    "tema": "tema",
    "familia_modelo": "familia_modelo",
    "dispositivo": "dispositivo",
    "idioma_3": "idioma_3",
    "faixa_horaria": "faixa_horaria",
    "resposta_quartil": "resposta_quartil",
    "recusa_total": "CASE WHEN recusa_total THEN 'sim' WHEN NOT recusa_total THEN 'nao' END",
    "estado_grupo": "estado_grupo",
}


def upgrade() -> None:
    # IC de Wilson 95% para uma proporção (igual a etl/estatistica.wilson; conferido em tests/test_api.py)
    for nome, sinal, limite in (("wilson_inf", "-", "greatest(0.0, {})"), ("wilson_sup", "+", "least(1.0, {})")):
        expr = f"(p + z * z / (2 * n) {sinal} z * sqrt(p * (1 - p) / n + z * z / (4.0 * n * n))) / (1 + z * z / n)"
        op.execute(f"""
            CREATE FUNCTION {nome}(sucessos bigint, n bigint) RETURNS double precision
            LANGUAGE sql IMMUTABLE AS $$
                SELECT CASE WHEN n IS NULL OR n = 0 THEN NULL ELSE {limite.format(expr)} END
                FROM (SELECT sucessos::float8 / nullif(n, 0) AS p, {Z95}::float8 AS z) c
            $$
        """)
    # Regras de exibição (PROJECT §6.1 e decisão de 14/11)
    op.execute("CREATE FUNCTION k_minimo() RETURNS integer LANGUAGE sql IMMUTABLE AS $$ SELECT 20 $$")
    op.execute("""
        CREATE FUNCTION amostra_suficiente(sucessos bigint, n bigint) RETURNS boolean
        LANGUAGE sql IMMUTABLE AS $$
            SELECT coalesce((wilson_sup(sucessos, n) - wilson_inf(sucessos, n)) / 2 <= 0.10, FALSE)
        $$
    """)

    # Retorno em 7 dias por coorte (semana e mês, fuso de São Paulo). Denominador = novatos elegíveis.
    op.execute("""
        CREATE VIEW vw_retorno_coorte AS
        WITH base AS (
            SELECT pais, 'mes' AS granularidade, coorte_mes AS coorte, voltou_7d
            FROM primeira_experiencia WHERE elegivel
            UNION ALL
            SELECT pais, 'semana', coorte_semana, voltou_7d
            FROM primeira_experiencia WHERE elegivel
        ),
        agg AS (
            SELECT pais, granularidade, coorte, count(*) AS novos, count(*) FILTER (WHERE voltou_7d) AS voltaram
            FROM base GROUP BY 1, 2, 3
        )
        SELECT pais, granularidade, coorte, novos, voltaram,
               voltaram::float8 / novos           AS taxa,
               wilson_inf(voltaram, novos)        AS ic_inf,
               wilson_sup(voltaram, novos)        AS ic_sup,
               amostra_suficiente(voltaram, novos) AS amostra_suficiente
        FROM agg
    """)

    # Uma linha por novato elegível e por dimensão: a API filtra por período e soma por nível.
    valores = ",\n                ".join(f"('{d}', {e})" for d, e in DIMENSOES.items())
    op.execute(f"""
        CREATE VIEW vw_novato_dimensao AS
        SELECT p.pais, p.usuario_sk, p.primeira_dia_local, p.coorte_semana, p.coorte_mes, p.voltou_7d,
               d.dimensao, coalesce(d.nivel, 'sem_valor') AS nivel
        FROM primeira_experiencia p
        CROSS JOIN LATERAL (VALUES
                {valores}
        ) AS d(dimensao, nivel)
        WHERE p.elegivel
    """)
    op.execute(f"GRANT SELECT ON vw_retorno_coorte, vw_novato_dimensao TO {LEITURA}")
    op.execute(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {LEITURA}")


def downgrade() -> None:
    op.execute("DROP VIEW vw_novato_dimensao, vw_retorno_coorte")
    op.execute("DROP FUNCTION amostra_suficiente(bigint, bigint), k_minimo(), wilson_sup(bigint, bigint), "
               "wilson_inf(bigint, bigint)")
