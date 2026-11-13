"""Contagens iniciais do recorte Brasil (Dia 1).

Uso:
    python analysis/00_contagens_iniciais.py --br data/raw/wildchat_br.parquet

Responde:
  - quantas conversas/usuários/semanas o Brasil tem e em que período;
  - qualidade básica (turnos de usuário sem timestamp, entradas vazias, hash repetido);
  - N de primeiras conversas → recálculo do custo da classificação (PROJECT.md §12.1);
  - se conseguimos reproduzir o relatório do incidente (semana 20/11/2023: 1.172 novos / 352 voltaram
    por hashed_ip; dashboard: 2.034 / 366 com usuário = hashed_ip + user-agent).
"""

from __future__ import annotations

import argparse

import duckdb

PRECO_HORA = 0.714  # c7i.4xlarge on-demand em us-east-1 (premissa §12.1)
SEG_POR_CONVERSA = 6.2  # medido em 12/11 com 4 slots paralelos (ADR-004)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--br", default="data/raw/wildchat_br.parquet")
    args = ap.parse_args()

    con = duckdb.connect()
    con.execute("SET memory_limit='4GB'")
    con.execute("SET TimeZone='UTC'")
    con.execute(f"""
        CREATE VIEW conv AS
        SELECT
            conversation[1].turn_identifier                                   AS conversa_id,
            conversation_hash, model, turn, language, toxic, redacted, state, country, hashed_ip,
            header."user-agent"                                               AS user_agent,
            header."accept-language"                                          AS accept_language,
            timestamp                                                         AS ts_ultimo,
            list_min(list_transform(conversation, lambda c: c.timestamp))          AS ts_primeiro_turno,
            list_count(list_filter(conversation, lambda c: c.role = 'user'))       AS n_turnos_usuario,
            list_count(list_filter(conversation, lambda c: c.role = 'user' AND c.timestamp IS NULL))
                                                                              AS turnos_usuario_sem_ts,
            list_count(list_filter(conversation, lambda c: c.role = 'user' AND trim(c.content) = ''))
                                                                              AS turnos_usuario_vazios
        FROM read_parquet('{args.br}')
    """)

    def q(title: str, sql: str) -> None:
        print(f"\n## {title}")
        print(con.sql(sql))

    q(
        "Volume (todas as conversas do recorte × só country='Brazil')",
        """
        SELECT country = 'Brazil' AS is_br, count(*) conversas, count(DISTINCT hashed_ip) ips,
               count(DISTINCT conversa_id) ids_unicos, count(DISTINCT conversation_hash) hashes,
               min(ts_primeiro_turno) inicio, max(ts_ultimo) fim
        FROM conv GROUP BY 1 ORDER BY 1 DESC""",
    )

    con.execute("CREATE VIEW br AS SELECT * FROM conv WHERE country = 'Brazil'")

    q(
        "Qualidade básica (Brasil)",
        """
        SELECT count(*) conversas,
               sum(turnos_usuario_sem_ts) turnos_usuario_sem_ts,
               count(*) FILTER (WHERE turnos_usuario_vazios > 0) conversas_com_entrada_vazia,
               count(*) FILTER (WHERE ts_primeiro_turno IS NULL) sem_ts_primeiro,
               count(*) FILTER (WHERE ts_primeiro_turno::DATE <> ts_ultimo::DATE) atravessa_dia_utc,
               count(*) FILTER (WHERE toxic) toxicas, count(*) FILTER (WHERE redacted) redacted,
               count(*) FILTER (WHERE state IS NULL) sem_estado,
               count(*) FILTER (WHERE user_agent IS NULL OR user_agent = '') sem_ua
        FROM br""",
    )

    q(
        "Modelos e idiomas (Brasil)",
        """
        SELECT model, language, count(*) n FROM br GROUP BY ALL ORDER BY n DESC LIMIT 12""",
    )

    q(
        "Concentração: conversas por hashed_ip (Brasil)",
        """
        WITH u AS (SELECT hashed_ip, count(*) n FROM br GROUP BY 1)
        SELECT count(*) usuarios, median(n) mediana, quantile_cont(n, 0.99) p99, max(n) maximo,
               sum(n) FILTER (WHERE n >= quantile_cont_n) / sum(n) AS share_top1pct
        FROM u, (SELECT quantile_cont(n, 0.99) quantile_cont_n FROM u)""",
    )

    q(
        "Novos por semana (usuário = hashed_ip, 1º turno, semana UTC) — primeiras e últimas",
        """
        WITH f AS (SELECT hashed_ip, min(ts_primeiro_turno) t0 FROM br GROUP BY 1)
        SELECT date_trunc('week', t0)::DATE semana, count(*) novos FROM f GROUP BY 1 ORDER BY 1""",
    )

    # Custo da classificação na EC2 com N = nº de primeiras conversas (1 por usuário)
    n_users = con.execute("SELECT count(DISTINCT hashed_ip) FROM br").fetchone()[0]
    horas = n_users * SEG_POR_CONVERSA / 3600
    print(f"\n## Custo da classificação (N = {n_users} primeiras conversas por hashed_ip)")
    print(f"{horas:.1f} h de c7i.4xlarge ≈ US$ {horas * PRECO_HORA:.2f}")

    # Reprodução do incidente: variantes de definição para a semana de 20/11/2023
    print("\n## Reprodução do incidente — semana de 2023-11-20 (alvo relatório: 1.172 / 352; dashboard: 2.034 / 366)")
    variantes = {
        "ip | 1º turno | UTC | retorno >1h e <=7d": ("hashed_ip", "ts_primeiro_turno", "UTC", "1 hour"),
        "ip | 1º turno | UTC | retorno >0 e <=7d": ("hashed_ip", "ts_primeiro_turno", "UTC", "0 seconds"),
        "ip | último turno | UTC | retorno >1h": ("hashed_ip", "ts_ultimo", "UTC", "1 hour"),
        "ip | 1º turno | SP | retorno >1h": ("hashed_ip", "ts_primeiro_turno", "America/Sao_Paulo", "1 hour"),
        "ip+UA | 1º turno | UTC | retorno >1h": (
            "hashed_ip || '|' || coalesce(user_agent,'')",
            "ts_primeiro_turno",
            "UTC",
            "1 hour",
        ),
        "ip+UA | último turno | UTC | retorno >1h": (
            "hashed_ip || '|' || coalesce(user_agent,'')",
            "ts_ultimo",
            "UTC",
            "1 hour",
        ),
    }
    for nome, (chave, ts, tz, gap) in variantes.items():
        r = con.execute(f"""
            WITH c AS (SELECT {chave} AS u, {ts} AS t FROM br),
                 f AS (SELECT u, min(t) t0 FROM c GROUP BY 1),
                 w AS (SELECT f.u, f.t0,
                              EXISTS (SELECT 1 FROM c WHERE c.u = f.u
                                      AND c.t > f.t0 + INTERVAL '{gap}'
                                      AND c.t <= f.t0 + INTERVAL '7 days') AS voltou
                       FROM f
                       WHERE date_trunc('week', timezone('{tz}', f.t0))::DATE = DATE '2023-11-20')
            SELECT count(*) novos, count(*) FILTER (WHERE voltou) voltaram FROM w
        """).fetchone()
        taxa = r[1] / r[0] if r[0] else float("nan")
        print(f"  {nome:45s} novos={r[0]:5d} voltaram={r[1]:4d} taxa={taxa:.1%}")


if __name__ == "__main__":
    main()
