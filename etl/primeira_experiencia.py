"""Fatores da 1ª experiência: uma linha por usuário (BDR-003, BDR-009, BDR-010).

Duas unidades, de propósito:
  - CONTEÚDO vem da 1ª conversa da 1ª sessão: modelo, idioma, tema, recusa, tamanho da resposta, dispositivo,
    estado e `redacted`. É a intenção com que a pessoa chegou e a resposta que ela encontrou. A sessão inteira
    misturaria engajamento: quem abre mais conversas tem mais chance de levar recusa e também volta mais (BDR-010).
  - VOLUME vem da 1ª sessão inteira: conversas, respostas e duração.
O horário é o início da 1ª sessão, no fuso do BDR-005.

`usuario_id` é md5(hashed_ip): serve só para juntar tabelas dentro da análise. A carga troca a chave por uma
substituta antes de gravar no Postgres (regra 6: nenhum identificador exibível na base analítica).

Uso:
    con = duckdb.connect()
    pe = construir_primeira_experiencia(con, BRUTA, TEMAS, volume_diario=VOLUME)
    pe[pe.elegivel]  # o denominador da taxa de retorno, igual a definicoes.elegiveis()
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd
from definicoes import GRUPO_TEMA, PADRAO, RECUSA_FATOR, Definicoes, construir

RAIZ = Path(__file__).resolve().parent.parent
BRUTA = RAIZ / "data" / "raw" / "wildchat_br.parquet"
VOLUME = RAIZ / "data" / "raw" / "wildchat_volume_diario.parquet"
TEMAS = RAIZ / "data" / "enriched" / "temas_v2_qwen3_8b.parquet"

K_ANONIMATO = 20  # regra 6: recorte com menos de 20 usuários elegíveis vira "outros"
UA_MOBILE = "Mobile|Android|iPhone|iPad"  # mesmo critério do notebook 01 (36% mobile)
FAIXAS_HORA = (("madrugada", 0, 5), ("manha", 6, 11), ("tarde", 12, 17), ("noite", 18, 23))


def _caso(coluna: str, mapa: dict[str, str]) -> str:
    ramos = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in mapa.items())
    return f"CASE {coluna} {ramos} END"


def criar_primeira_experiencia(
    con: duckdb.DuckDBPyConnection, temas: str, d: Definicoes = PADRAO, k: int = K_ANONIMATO
) -> pd.DataFrame:
    """Requer as tabelas de `definicoes.construir()`. Cria a tabela `primeira_experiencia` e a devolve."""
    recusa = ", ".join(f"'{r}'" for r in RECUSA_FATOR)
    faixa = " ".join(f"WHEN hora_local BETWEEN {a} AND {b} THEN '{n}'" for n, a, b in FAIXAS_HORA)
    lacuna = "AND NOT u.janela_com_lacuna" if d.excluir_janela_com_lacuna else ""
    con.execute(f"""
        CREATE OR REPLACE TABLE primeira_experiencia AS
        WITH conv_s1 AS (
            SELECT DISTINCT usuario_id, conversa_id FROM eventos_sessao WHERE sessao_seq = 1
        ),
        prim AS (  -- a 1ª conversa da 1ª sessão
            SELECT usuario_id, first(conversa_id ORDER BY inicio_utc, conversa_id) AS conversa_id
            FROM eventos_sessao WHERE sessao_seq = 1 GROUP BY 1
        ),
        s1 AS (SELECT * FROM sessoes WHERE sessao_seq = 1),
        resp AS (  -- respostas do assistente dentro da janela da 1ª sessão (vale para as duas unidades do BDR-002)
            SELECT v.usuario_id, count(*) AS n_respostas
            FROM conv_s1 v
            JOIN (SELECT conversa_id, unnest(horarios_respostas) AS t FROM conversas) r USING (conversa_id)
            JOIN s1 USING (usuario_id)
            WHERE r.t BETWEEN s1.inicio_utc AND s1.fim_utc
            GROUP BY 1
        ),
        t AS (SELECT conversa_id, tema, recusa, recusa_regex FROM read_parquet('{temas}')),
        rec_s1 AS (  -- sensibilidade do BDR-010: recusa em qualquer conversa da 1ª sessão
            SELECT v.usuario_id, coalesce(bool_or(t.recusa IN ({recusa})), FALSE) AS recusa_total_sessao
            FROM conv_s1 v LEFT JOIN t ON t.conversa_id = v.conversa_id::VARCHAR
            GROUP BY 1
        ),
        base AS (
            SELECT
                u.usuario_id,
                u.coorte_mes,
                u.coorte_semana,
                u.primeira_inicio_utc,
                u.voltou_7d,
                u.observavel_7d AND NOT u.em_aquecimento {lacuna}                    AS elegivel,
                u.primeira_n_conversas                                              AS n_conversas_sessao1,
                coalesce(resp.n_respostas, 0)                                       AS n_respostas_sessao1,
                date_diff('second', s1.inicio_utc, s1.fim_utc) / 60.0               AS duracao_sessao1_min,
                c.modelo,
                CASE WHEN c.modelo LIKE 'gpt-4%' THEN 'gpt-4' ELSE 'gpt-3.5' END   AS familia_modelo,
                CASE c.idioma WHEN 'Portuguese' THEN 'portugues' WHEN 'English' THEN 'ingles'
                              ELSE 'outro' END                                      AS idioma_3,
                CASE WHEN regexp_matches(c.user_agent, '{UA_MOBILE}') THEN 'mobile'
                     ELSE 'desktop' END                                             AS dispositivo,
                c.estado,
                c.redacted,
                c.turnos                                                            AS turnos_conversa_1,
                c.tam_msg_usuario_1,
                c.tam_resposta_1,
                extract(hour FROM timezone('{d.fuso}', u.primeira_inicio_utc))::INT AS hora_local,
                isodow(timezone('{d.fuso}', u.primeira_inicio_utc))::INT            AS dia_semana,
                t.tema,
                {_caso("t.tema", GRUPO_TEMA)}                                       AS tema_grupo,
                t.recusa,
                t.recusa IN ({recusa})                                              AS recusa_total,
                t.recusa_regex,
                rec_s1.recusa_total_sessao
            FROM usuarios u
            JOIN prim USING (usuario_id)
            JOIN s1 USING (usuario_id)
            JOIN conversas c ON c.conversa_id = prim.conversa_id
            LEFT JOIN resp USING (usuario_id)
            LEFT JOIN t ON t.conversa_id = prim.conversa_id::VARCHAR
            LEFT JOIN rec_s1 USING (usuario_id)
        )
        SELECT *,
               CASE {faixa} END                                                     AS faixa_horaria,
               dia_semana IN (6, 7)                                                 AS fim_de_semana,
               CASE WHEN estado IS NULL
                      OR sum(elegivel::INT) OVER (PARTITION BY estado) < {k} THEN 'outros'
                    ELSE estado END                                                 AS estado_grupo
        FROM base
        ORDER BY primeira_inicio_utc, usuario_id
    """)
    return con.execute("SELECT * FROM primeira_experiencia").fetchdf()


def construir_primeira_experiencia(
    con: duckdb.DuckDBPyConnection,
    bruta: str,
    temas: str,
    d: Definicoes = PADRAO,
    volume_diario: str | None = None,
    k: int = K_ANONIMATO,
) -> pd.DataFrame:
    construir(con, bruta, d, volume_diario=volume_diario)
    return criar_primeira_experiencia(con, temas, d, k)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bruta", type=Path, default=BRUTA)
    ap.add_argument("--temas", type=Path, default=TEMAS)
    ap.add_argument("--saida", type=Path, help="grava o parquet (fica em data/work: tem usuario_id)")
    args = ap.parse_args()
    con = duckdb.connect()
    con.execute("SET memory_limit = '3GB'")
    volume = str(VOLUME) if VOLUME.exists() else None
    pe = construir_primeira_experiencia(con, str(args.bruta), str(args.temas), volume_diario=volume)
    el = pe[pe.elegivel]
    print(f"usuários: {len(pe)} | elegíveis: {len(el)} | retorno 7d: {el.voltou_7d.mean():.1%}")
    print(f"sem tema: {int(pe.tema.isna().sum())} | estados no grupo: {el.estado_grupo.nunique()}")
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        pe.to_parquet(args.saida, index=False)
        print(f"-> {args.saida}")


if __name__ == "__main__":
    main()
