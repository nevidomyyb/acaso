"""Definições de usuário, sessão, primeira experiência e retorno (BDR-001 a BDR-008).

Fonte única das definições: a carga (ETL), a análise de sensibilidade e os testes usam este módulo.
Cada parâmetro de `Definicoes` corresponde a um BDR; os valores padrão são as escolhas aceitas.

Uso:
    con = duckdb.connect()
    usuarios = construir(con, "data/raw/wildchat_br.parquet", Definicoes(),
                         volume_diario="data/raw/wildchat_volume_diario.parquet")
    # tabelas criadas no DuckDB: conversas, eventos, eventos_sessao, sessoes, lacunas, usuarios
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import duckdb
import pandas as pd

VERSAO_DEFINICOES = "2026-11-11.1"  # muda quando qualquer padrão abaixo muda

CHAVES_USUARIO = {
    "ip": "hashed_ip",
    "ip_ua": "hashed_ip || '|' || coalesce(user_agent, '')",
    "ip_lang": "hashed_ip || '|' || coalesce(accept_language, '')",
}
REGRAS_RETORNO = ("nova_sessao", "apos_1h", "dia_seguinte")
UNIDADES = ("turno", "conversa")

# BDR-009: tema da 1ª conversa da 1ª sessão, em 7 grupos (validação manual de 12/11: 83,8% ponderada,
# contra 71,4% nos 11 temas). Os 11 temas ficam só nos gráficos descritivos.
GRUPO_TEMA = {
    "conhecimento_geral": "tarefa_conhecimento",
    "estudo_escola": "tarefa_conhecimento",
    "trabalho_profissional": "tarefa_conhecimento",
    "criativo_ficcao": "criativo_entretenimento",
    "roleplay_personagem": "criativo_entretenimento",
    "conteudo_adulto": "criativo_entretenimento",
    "saudacao_teste": "saudacao_teste",
    "programacao_tecnologia": "programacao_tecnologia",
    "traducao_reescrita": "traducao_reescrita",
    "conselho_pessoal": "conselho_pessoal",
    "outro": "outro",
}
# BDR-010: o fator é recusa `total` pelo LLM na 1ª conversa da 1ª sessão; o regex e a sessão inteira são sensibilidade.
RECUSA_FATOR = ("total",)


@dataclass(frozen=True)
class Definicoes:
    chave_usuario: str = "ip"  # BDR-001: ip | ip_ua | ip_lang
    max_uas_por_ip: int | None = None  # BDR-001: se definido, exclui IPs com mais user-agents (IP compartilhado)
    unidade_atividade: str = "turno"  # BDR-002: turno (cada resposta) | conversa (só o início/fim da conversa)
    gap_sessao_min: int = 30  # BDR-002: intervalo sem atividade que abre nova sessão
    aquecimento_semanas: int = 0  # BDR-003: exclui quem chega nas N primeiras semanas da base
    regra_retorno: str = "nova_sessao"  # BDR-004: nova_sessao | apos_1h | dia_seguinte
    janela_retorno_dias: int = 7  # BDR-004
    fuso: str = "America/Sao_Paulo"  # BDR-005: fuso de dia, semana e mês
    excluir_janela_com_lacuna: bool = True  # BDR-006: tira quem tem falha de coleta na janela de 7 dias
    limiar_lacuna: float = 0.15  # BDR-006: volume global < 15% da mediana = falha de coleta (feriado ≈ 20%)
    excluir_sem_conteudo: bool = True  # BDR-008: ignora conversa sem nenhuma mensagem de usuário

    def __post_init__(self) -> None:
        if self.chave_usuario not in CHAVES_USUARIO:
            raise ValueError(f"chave_usuario inválida: {self.chave_usuario}")
        if self.regra_retorno not in REGRAS_RETORNO:
            raise ValueError(f"regra_retorno inválida: {self.regra_retorno}")
        if self.unidade_atividade not in UNIDADES:
            raise ValueError(f"unidade_atividade inválida: {self.unidade_atividade}")

    def como_dict(self) -> dict:
        return asdict(self)


def criar_conversas(con: duckdb.DuckDBPyConnection, bruta: str) -> None:
    """Uma linha por conversa do Brasil, com colunas derivadas da base bruta. Sem texto."""
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"""
        CREATE OR REPLACE TABLE conversas AS
        WITH b AS (
            SELECT *,
                   list_filter(conversation, lambda c: c.role = 'user') AS turnos_usuario,
                   list_filter(conversation, lambda c: c.role = 'assistant') AS turnos_assistente
            FROM read_parquet('{bruta}')
            WHERE country = 'Brazil'  -- BDR-007
        )
        SELECT
            conversation[1].turn_identifier                                    AS conversa_id,
            hashed_ip,
            header."user-agent"                                                AS user_agent,
            header."accept-language"                                           AS accept_language,
            -- turnos do usuário não têm horário; o 1º horário é o da 1ª resposta do assistente
            list_min(list_transform(conversation, lambda c: c.timestamp))      AS inicio_utc,
            timestamp                                                          AS fim_utc,
            list_transform(turnos_assistente, lambda a: a.timestamp)           AS horarios_respostas,
            model                                                              AS modelo,
            turn                                                               AS turnos,
            language                                                           AS idioma,
            state                                                              AS estado,
            redacted,
            toxic,
            list_bool_and(list_transform(turnos_usuario, lambda u: trim(u.content) = '')) AS sem_conteudo,
            trim(turnos_usuario[1].content) = ''                               AS primeira_msg_vazia,
            length(turnos_usuario[1].content)                                  AS tam_msg_usuario_1,
            length(turnos_assistente[1].content)                               AS tam_resposta_1,
            list_avg(list_transform(turnos_assistente, lambda a: length(a.content))) AS tam_resposta_media
        FROM b
    """)


def criar_lacunas(con: duckdb.DuckDBPyConnection, volume_diario: str | None, limiar: float) -> None:
    """Dias com falha de coleta: volume global abaixo de `limiar` × mediana, ou dia ausente."""
    if volume_diario is None:
        con.execute("CREATE OR REPLACE TABLE lacunas (dia_utc DATE, conversas BIGINT)")
        return
    con.execute(f"""
        CREATE OR REPLACE TABLE lacunas AS
        WITH v AS (SELECT * FROM read_parquet('{volume_diario}')),
        cal AS (
            SELECT unnest(generate_series((SELECT min(dia_utc) FROM v), (SELECT max(dia_utc) FROM v),
                                          INTERVAL 1 DAY))::DATE AS dia_utc
        )
        SELECT cal.dia_utc, coalesce(v.conversas, 0) AS conversas
        FROM cal LEFT JOIN v USING (dia_utc)
        WHERE coalesce(v.conversas, 0) < {limiar} * (SELECT median(conversas) FROM v)
    """)


def construir(
    con: duckdb.DuckDBPyConnection,
    bruta: str,
    d: Definicoes,
    volume_diario: str | None = None,
) -> pd.DataFrame:
    """Cria conversas → eventos → sessões → usuários com retorno em 7 dias. Devolve `usuarios`."""
    criar_conversas(con, bruta)
    criar_lacunas(con, volume_diario, d.limiar_lacuna)
    chave = CHAVES_USUARIO[d.chave_usuario]

    filtros = ["TRUE"]
    if d.excluir_sem_conteudo:
        filtros.append("NOT sem_conteudo")
    if d.max_uas_por_ip is not None:
        filtros.append(f"""hashed_ip NOT IN (
            SELECT hashed_ip FROM conversas GROUP BY 1 HAVING count(DISTINCT user_agent) > {d.max_uas_por_ip})""")

    # Evento = um momento de uso. "turno": cada resposta do assistente (pega quem continua uma conversa
    # aberta dias depois). "conversa": só o intervalo início–fim de cada conversa.
    if d.unidade_atividade == "turno":
        eventos = "SELECT usuario_id, conversa_id, unnest(horarios_respostas) AS inicio_utc FROM u"
        eventos = f"SELECT *, inicio_utc AS fim_utc FROM ({eventos})"
    else:
        eventos = "SELECT usuario_id, conversa_id, inicio_utc, fim_utc FROM u"

    con.execute(f"""
        CREATE OR REPLACE TABLE eventos AS
        WITH u AS (SELECT *, md5({chave}) AS usuario_id FROM conversas WHERE {" AND ".join(filtros)})
        {eventos}
    """)
    # Sessão: nova quando o início passa do maior fim anterior + gap (conversas podem se sobrepor)
    con.execute(f"""
        CREATE OR REPLACE TABLE eventos_sessao AS
        WITH o AS (
            SELECT *, max(fim_utc) OVER (
                       PARTITION BY usuario_id ORDER BY inicio_utc, conversa_id
                       ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS fim_anterior
            FROM eventos
        )
        SELECT *, sum(CASE WHEN fim_anterior IS NULL
                             OR inicio_utc > fim_anterior + INTERVAL {d.gap_sessao_min} MINUTE
                           THEN 1 ELSE 0 END) OVER (
                       PARTITION BY usuario_id ORDER BY inicio_utc, conversa_id
                       ROWS UNBOUNDED PRECEDING) AS sessao_seq
        FROM o
    """)
    con.execute("""
        CREATE OR REPLACE TABLE sessoes AS
        SELECT usuario_id, sessao_seq, min(inicio_utc) AS inicio_utc, max(fim_utc) AS fim_utc,
               count(DISTINCT conversa_id) AS n_conversas
        FROM eventos_sessao GROUP BY ALL
    """)

    janela = f"INTERVAL {d.janela_retorno_dias} DAY"
    if d.regra_retorno == "nova_sessao":
        cond = "e.sessao_seq >= 2"  # já começa depois do fim da 1ª sessão + gap
    elif d.regra_retorno == "apos_1h":
        cond = "e.inicio_utc > p.inicio_utc + INTERVAL 1 HOUR"
    else:  # dia_seguinte: atividade em outro dia do calendário local
        cond = f"timezone('{d.fuso}', e.inicio_utc)::DATE > timezone('{d.fuso}', p.inicio_utc)::DATE"

    con.execute(f"""
        CREATE OR REPLACE TABLE usuarios AS
        WITH limites AS (SELECT min(inicio_utc) AS base_inicio, max(fim_utc) AS base_fim FROM conversas),
        p AS (SELECT * FROM sessoes WHERE sessao_seq = 1),
        r AS (
            SELECT p.usuario_id, min(e.inicio_utc) AS retorno_utc
            FROM p JOIN eventos_sessao e USING (usuario_id)
            WHERE {cond} AND e.inicio_utc <= p.inicio_utc + {janela}
            GROUP BY 1
        ),
        lac AS (
            SELECT p.usuario_id, count(*) > 0 AS janela_com_lacuna
            FROM p JOIN lacunas l
              ON l.dia_utc BETWEEN p.inicio_utc::DATE AND (p.inicio_utc + {janela})::DATE
            GROUP BY 1
        )
        SELECT p.usuario_id,
               p.inicio_utc                                                  AS primeira_inicio_utc,
               p.fim_utc                                                     AS primeira_fim_utc,
               p.n_conversas                                                 AS primeira_n_conversas,
               r.retorno_utc,
               r.retorno_utc IS NOT NULL                                     AS voltou_7d,
               p.inicio_utc + {janela} <= l.base_fim                         AS observavel_7d,
               p.inicio_utc < l.base_inicio + INTERVAL {d.aquecimento_semanas * 7} DAY AS em_aquecimento,
               coalesce(lac.janela_com_lacuna, FALSE)                        AS janela_com_lacuna,
               date_trunc('week', timezone('{d.fuso}', p.inicio_utc))::DATE  AS coorte_semana,
               date_trunc('month', timezone('{d.fuso}', p.inicio_utc))::DATE AS coorte_mes
        FROM p CROSS JOIN limites l
        LEFT JOIN r USING (usuario_id)
        LEFT JOIN lac USING (usuario_id)
    """)
    return con.execute("SELECT * FROM usuarios").fetchdf()


PADRAO = Definicoes()


def elegiveis(usuarios: pd.DataFrame, d: Definicoes = PADRAO) -> pd.DataFrame:
    """Denominador da taxa de retorno (BDR-003, BDR-006): observável por 7 dias, fora do aquecimento
    e, se a definição pedir, sem falha de coleta na janela."""
    m = usuarios.observavel_7d & ~usuarios.em_aquecimento
    if d.excluir_janela_com_lacuna:
        m &= ~usuarios.janela_com_lacuna
    return usuarios[m]
