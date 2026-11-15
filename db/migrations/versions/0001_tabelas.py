"""Tabelas da base analítica: meta_carga, primeira_experiencia, resultado_efeitos + papel só de leitura.

A base analítica não guarda texto das conversas, hashed_ip, user-agent nem a chave md5 da análise (regra 6).
O usuário é um inteiro substituto (`usuario_sk`), sem tabela de mapeamento.

Revision ID: 0001
Revises:
Create Date: 2026-11-14
"""

import os

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

LEITURA = "acaso_leitura"  # papel da API: só SELECT, nunca escreve


def upgrade() -> None:
    op.execute("""
        CREATE TABLE meta_carga (
            carga_id              serial PRIMARY KEY,
            status                text        NOT NULL CHECK (status IN ('iniciada', 'ok', 'erro')),
            inicio_utc            timestamptz NOT NULL DEFAULT now(),
            fim_utc               timestamptz,
            duracao_s             numeric(10, 1),
            definicao_versao      text        NOT NULL,
            pais                  text        NOT NULL,
            bruta_arquivo         text        NOT NULL,
            bruta_sha256          text        NOT NULL,
            bruta_revisao         text,
            classificacao_arquivo text        NOT NULL,
            classificacao_sha256  text        NOT NULL,
            classificacao_versao  text,
            conversas_lidas       integer,
            usuarios_gravados     integer,
            elegiveis             integer,
            efeitos_gravados      integer,
            rejeitadas            jsonb,      -- motivo -> quantidade (conversas e usuários fora do denominador)
            dados_de              date,       -- 1ª e última data da base bruta (fuso de São Paulo)
            dados_ate             date,
            erro                  text
        )
    """)
    op.execute("""
        CREATE TABLE primeira_experiencia (
            usuario_sk            integer     PRIMARY KEY,
            carga_id              integer     NOT NULL REFERENCES meta_carga (carga_id),
            pais                  text        NOT NULL,
            primeira_inicio_utc   timestamptz NOT NULL,
            primeira_dia_local    date        NOT NULL,
            coorte_semana         date        NOT NULL,
            coorte_mes            date        NOT NULL,
            elegivel              boolean     NOT NULL,
            voltou_7d             boolean     NOT NULL,
            n_conversas_sessao1   integer,
            n_respostas_sessao1   integer,
            duracao_sessao1_min   numeric(10, 1),
            modelo                text,
            familia_modelo        text,
            idioma_3              text,
            dispositivo           text,
            estado_grupo          text,
            redacted              boolean,
            turnos_conversa_1     integer,
            tam_msg_usuario_1     integer,
            tam_resposta_1        integer,
            resposta_quartil      text,
            hora_local            smallint,
            faixa_horaria         text,
            dia_semana            smallint,
            fim_de_semana         boolean,
            tema                  text,
            tema_grupo            text,
            recusa                text,
            recusa_total          boolean,
            recusa_regex          boolean,
            recusa_total_sessao   boolean
        )
    """)
    op.execute("CREATE INDEX ix_pe_pais_mes ON primeira_experiencia (pais, coorte_mes) WHERE elegivel")
    op.execute("CREATE INDEX ix_pe_pais_dia ON primeira_experiencia (pais, primeira_dia_local) WHERE elegivel")
    op.execute("""
        CREATE TABLE resultado_efeitos (
            efeito_id             serial      PRIMARY KEY,
            carga_id              integer     NOT NULL REFERENCES meta_carga (carga_id),
            pais                  text        NOT NULL,
            ordem                 smallint    NOT NULL,   -- ordem de exibição do fator (efeitos.FATORES)
            fator                 text        NOT NULL,
            rotulo_fator          text        NOT NULL,
            nivel                 text        NOT NULL,
            rotulo_nivel          text        NOT NULL,
            referencia            text        NOT NULL,
            rotulo_referencia     text        NOT NULL,
            n                     integer     NOT NULL,
            bruto_pp              double precision NOT NULL,
            bruto_ic_inf          double precision NOT NULL,
            bruto_ic_sup          double precision NOT NULL,
            ajustado_pp           double precision NOT NULL,
            ajustado_ic_inf       double precision NOT NULL,
            ajustado_ic_sup       double precision NOT NULL,
            metodo                text        NOT NULL,
            n_modelo              integer     NOT NULL,
            definicao_versao      text        NOT NULL,
            UNIQUE (pais, fator, nivel)
        )
    """)
    senha = os.environ.get("ACASO_DB_SENHA_LEITURA", "acaso_leitura_local")
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{LEITURA}') THEN
                CREATE ROLE {LEITURA} LOGIN PASSWORD '{senha}';
            END IF;
        END $$
    """)
    op.execute(f"GRANT USAGE ON SCHEMA public TO {LEITURA}")
    op.execute(f"GRANT SELECT ON meta_carga, primeira_experiencia, resultado_efeitos TO {LEITURA}")


def downgrade() -> None:
    op.execute("DROP TABLE resultado_efeitos, primeira_experiencia, meta_carga")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {LEITURA}")
