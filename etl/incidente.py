"""Incidente da §4.2 do enunciado: o código de referência, reproduzido fielmente em DuckDB, e a versão corrigida.

O enunciado traz duas peças com defeito:
  - a CARGA diária (Python): `usuario_id = sha256(hashed_ip|user-agent)`, `ultimo_turno = c["timestamp"]` (o último
    turno) e `INSERT ... ON CONFLICT (conversa_id) DO NOTHING`;
  - o ENDPOINT (TypeScript/SQL): `min(ultimo_turno)` como 1ª vez, `date_trunc('week', ...)` sem fuso, retorno
    "> 1 hora e <= 7 dias" pelo último turno da conversa de retorno, e o `EXISTS` do retorno sem filtro de país.

Aqui cada peça existe nas duas versões, com a mesma interface, para o notebook 05 e os testes compararem:

    con = duckdb.connect(); con.execute("SET TimeZone = 'UTC'")   # o servidor do cliente roda em UTC
    criar_tabela(con, corrigida=False)
    carregar(con, "data/raw/wildchat_br.parquet", corrigida=False)  # uma "carga diária" com as conversas do arquivo
    coortes(con, "2023-11-06", "2023-11-27", corrigida=False)       # o que o endpoint devolve

A causa principal é a CHAVE do usuário (camada de carga). As outras quatro diferenças são defeitos secundários,
que o notebook mede um a um. A correção da chave segue o BDR-001 (usuário = hashed_ip).
"""

from __future__ import annotations

import duckdb
import pandas as pd

TABELA = "analytics_conversas"
UA = 'header."user-agent"'

# Chave do usuário. Na referência, o f-string do Python escreve "None" quando o user-agent é nulo.
CHAVE_REFERENCIA = f"sha256(hashed_ip || '|' || coalesce({UA}, 'None'))"
CHAVE_CORRIGIDA = "sha256(hashed_ip)"  # BDR-001: o user-agent muda com atualização de navegador; o IP fica


def criar_tabela(con: duckdb.DuckDBPyConnection, corrigida: bool) -> None:
    """A tabela `analytics.conversas` do enunciado. A corrigida guarda também o 1º turno."""
    extra = "primeiro_turno TIMESTAMPTZ," if corrigida else ""
    con.execute(f"DROP TABLE IF EXISTS {TABELA}")
    con.execute(f"""
        CREATE TABLE {TABELA} (
            conversa_id   BIGINT PRIMARY KEY,
            usuario_id    VARCHAR,
            {extra}
            ultimo_turno  TIMESTAMPTZ,
            modelo        VARCHAR,
            turnos        BIGINT,
            pais          VARCHAR
        )
    """)


def carregar(con: duckdb.DuckDBPyConnection, bruta: str, corrigida: bool, chave: str | None = None) -> None:
    """Uma execução da carga diária com as conversas de `bruta`.

    Referência: `ON CONFLICT DO NOTHING`. Uma conversa que continua no dia seguinte chega de novo com o mesmo
    `conversa_id` e é ignorada: o `ultimo_turno` fica com o valor do 1º dia.
    Corrigida: grava o 1º turno (1ª resposta do assistente; turnos do usuário não têm horário) e faz upsert,
    mantendo o menor 1º turno e o maior último turno.
    """
    if corrigida:
        chave = chave or CHAVE_CORRIGIDA
        con.execute(f"""
            INSERT INTO {TABELA} (conversa_id, usuario_id, primeiro_turno, ultimo_turno, modelo, turnos, pais)
            SELECT conversation[1].turn_identifier, {chave},
                   list_min(list_transform(conversation, lambda t: t.timestamp)), timestamp, model, turn, country
            FROM read_parquet('{bruta}')
            ON CONFLICT (conversa_id) DO UPDATE SET
                primeiro_turno = least({TABELA}.primeiro_turno, excluded.primeiro_turno),
                ultimo_turno   = greatest({TABELA}.ultimo_turno, excluded.ultimo_turno),
                turnos         = greatest({TABELA}.turnos, excluded.turnos)
        """)
    else:
        chave = chave or CHAVE_REFERENCIA
        con.execute(f"""
            INSERT INTO {TABELA} (conversa_id, usuario_id, ultimo_turno, modelo, turnos, pais)
            SELECT conversation[1].turn_identifier, {chave}, timestamp, model, turn, country
            FROM read_parquet('{bruta}')
            ON CONFLICT (conversa_id) DO NOTHING
        """)


def sql_coortes(corrigida: bool, fuso: str = "America/Sao_Paulo") -> str:
    """SQL do endpoint `GET /api/retencao/coortes`. Parâmetros: $inicio, $fim, $pais."""
    if not corrigida:  # fiel ao route.ts do enunciado
        return f"""
            WITH primeira AS (
                SELECT usuario_id, min(ultimo_turno) AS primeira_vez
                FROM {TABELA} WHERE pais = $pais GROUP BY usuario_id
            )
            SELECT date_trunc('week', p.primeira_vez)::DATE AS semana,
                   count(*) AS novos,
                   count(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM {TABELA} c
                       WHERE c.usuario_id = p.usuario_id
                         AND c.ultimo_turno > p.primeira_vez + INTERVAL 1 HOUR
                         AND c.ultimo_turno <= p.primeira_vez + INTERVAL 7 DAY
                   )) AS voltaram_7d
            FROM primeira p
            WHERE p.primeira_vez >= $inicio::TIMESTAMPTZ AND p.primeira_vez < $fim::TIMESTAMPTZ
            GROUP BY 1 ORDER BY 1
        """
    # Corrigido: 1ª vez pelo 1º turno; semana no fuso do país (BDR-005); retorno pelo INÍCIO da conversa de
    # retorno; o EXISTS filtra o país. A regra "> 1 hora" fica: é definição (−1,6 p.p., notebook 03), não defeito.
    return f"""
        WITH primeira AS (
            SELECT usuario_id, min(primeiro_turno) AS primeira_vez
            FROM {TABELA} WHERE pais = $pais GROUP BY usuario_id
        )
        SELECT date_trunc('week', timezone('{fuso}', p.primeira_vez))::DATE AS semana,
               count(*) AS novos,
               count(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM {TABELA} c
                   WHERE c.usuario_id = p.usuario_id AND c.pais = $pais
                     AND c.primeiro_turno > p.primeira_vez + INTERVAL 1 HOUR
                     AND c.primeiro_turno <= p.primeira_vez + INTERVAL 7 DAY
               )) AS voltaram_7d
        FROM primeira p
        WHERE timezone('{fuso}', p.primeira_vez)::DATE >= $inicio::DATE
          AND timezone('{fuso}', p.primeira_vez)::DATE < $fim::DATE
        GROUP BY 1 ORDER BY 1
    """


def coortes(con: duckdb.DuckDBPyConnection, inicio: str, fim: str, corrigida: bool,
            pais: str = "Brazil") -> pd.DataFrame:
    """O que o endpoint devolve: semana, novos, voltaram_7d (e a taxa, para leitura)."""
    df = con.execute(sql_coortes(corrigida), {"inicio": inicio, "fim": fim, "pais": pais}).df()
    df["taxa"] = df.voltaram_7d / df.novos
    return df


# Consulta de confirmação (item 2 da §4.2): roda na BASE BRUTA, que tem hashed_ip e user-agent.
# Para cada semana: novos pela chave da carga (IP + user-agent) e pela chave do relatório (IP), quantas chaves
# "novas" pertencem a um IP que já existia antes, e quantos user-agents distintos cada IP usou na semana.
SQL_CONFIRMACAO = f"""
    WITH c AS (
        SELECT hashed_ip, coalesce({UA}, 'None') AS ua, timestamp AS ultimo_turno
        FROM read_parquet($bruta) WHERE country = $pais
    ),
    chave_ua AS (SELECT hashed_ip, ua, min(ultimo_turno) AS primeira_vez FROM c GROUP BY 1, 2),
    chave_ip AS (SELECT hashed_ip, min(ultimo_turno) AS primeira_ip FROM c GROUP BY 1),
    novos AS (
        SELECT date_trunc('week', k.primeira_vez)::DATE AS semana,
               count(*)                                          AS novos_ip_ua,
               count(*) FILTER (WHERE i.primeira_ip < k.primeira_vez) AS ip_ja_existia
        FROM chave_ua k JOIN chave_ip i USING (hashed_ip)
        GROUP BY 1
    ),
    novos_ip AS (SELECT date_trunc('week', primeira_ip)::DATE AS semana, count(*) AS novos_ip FROM chave_ip GROUP BY 1),
    uas AS (
        SELECT semana, avg(n_ua) AS uas_por_ip, max(n_ua) AS max_uas_por_ip FROM (
            SELECT date_trunc('week', ultimo_turno)::DATE AS semana, hashed_ip, count(DISTINCT ua) AS n_ua
            FROM c GROUP BY 1, 2) GROUP BY 1
    )
    SELECT semana, novos_ip, novos_ip_ua, ip_ja_existia,
           ip_ja_existia::DOUBLE / novos_ip_ua AS pct_chave_nova_de_ip_antigo,
           novos_ip_ua::DOUBLE / novos_ip      AS razao_chaves_por_ip,
           uas_por_ip, max_uas_por_ip
    FROM novos JOIN novos_ip USING (semana) JOIN uas USING (semana)
    ORDER BY semana
"""


def confirmar(con: duckdb.DuckDBPyConnection, bruta: str, pais: str = "Brazil") -> pd.DataFrame:
    return con.execute(SQL_CONFIRMACAO, {"bruta": bruta, "pais": pais}).df()
