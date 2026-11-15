"""Carga: conversões sem banco e, com Postgres (marca `db`), a carga real ponta a ponta."""

from __future__ import annotations

import math

import pandas as pd
import psycopg
import pytest
from banco import banco_temporario, pular_sem_banco
from carga import executar, linhas, montar_efeitos, nivel_texto

# Números da análise com as definições aceitas (CLAUDE.md, notebooks 03 e 04). Se mudarem, a carga mudou.
USUARIOS, ELEGIVEIS, VOLTARAM = 2354, 2219, 635
RECUSA_PP, RECUSA_IC = -17.4, (-25.4, -9.4)
PROIBIDAS = r"(ip|agent|usuario_id|motivo|texto|content|hash|^estado$)"


def test_nivel_booleano_vira_sim_nao():
    assert nivel_texto(True) == "sim" and nivel_texto(False) == "nao" and nivel_texto("Q1") == "Q1"


def test_linhas_trocam_nan_e_nat_por_none():
    df = pd.DataFrame({"a": [1.0, math.nan], "b": [pd.Timestamp("2024-01-01"), pd.NaT], "c": ["x", None]})
    assert list(linhas(df)) == [(1.0, pd.Timestamp("2024-01-01"), "x"), (None, None, None)]


def test_efeitos_tem_rotulo_e_ordem_dos_fatores():
    tab = pd.DataFrame({
        "fator": ["recusa_total", "tema_grupo"], "rotulo": ["Recusa", "Tema"], "nivel": [True, "conselho_pessoal"],
        "referencia": [False, "tarefa_conhecimento"], "n": [10, 20],
        "bruto_pp": [1.0, 2.0], "bruto_ic_inf": [0.0, 1.0], "bruto_ic_sup": [2.0, 3.0],
        "ajustado_pp": [1.5, 2.5], "ic_inf": [0.5, 1.5], "ic_sup": [2.5, 3.5],
    })
    ef = montar_efeitos(tab, n_modelo=30)
    assert ef.ordem.tolist() == [0, 1]
    assert ef.nivel.tolist() == ["sim", "conselho_pessoal"] and ef.referencia.tolist() == ["nao", "tarefa_conhecimento"]
    assert ef.rotulo_nivel.tolist() == ["Sim", "Conselho pessoal"]
    assert ef.ajustado_ic_inf.tolist() == [0.5, 1.5]


@pytest.mark.db
def test_carga_real_e_idempotente_e_nao_grava_dado_pessoal():
    pular_sem_banco()
    with banco_temporario() as url:
        executar(url)
        executar(url)  # 2ª vez: substitui, não duplica
        with psycopg.connect(url) as c:
            assert c.execute("SELECT count(*), count(DISTINCT carga_id) FROM primeira_experiencia").fetchone() == (
                USUARIOS, 1)
            assert c.execute("SELECT count(*) FROM meta_carga WHERE status = 'ok'").fetchone()[0] == 2
            novos, voltaram = c.execute(
                "SELECT sum(novos), sum(voltaram) FROM vw_retorno_coorte WHERE granularidade = 'mes'").fetchone()
            assert (novos, voltaram) == (ELEGIVEIS, VOLTARAM)
            pp, inf, sup = c.execute("SELECT ajustado_pp, ajustado_ic_inf, ajustado_ic_sup FROM resultado_efeitos "
                                     "WHERE fator = 'recusa_total'").fetchone()
            assert (round(pp, 1), round(inf, 1), round(sup, 1)) == (RECUSA_PP, *RECUSA_IC)
            proibidas = c.execute("SELECT table_name || '.' || column_name FROM information_schema.columns "
                                  "WHERE table_schema = 'public' AND column_name ~ %s", (PROIBIDAS,)).fetchall()
            assert proibidas == []
            rej = c.execute("SELECT rejeitadas FROM meta_carga ORDER BY carga_id DESC LIMIT 1").fetchone()[0]
            assert rej == {"conversas_sem_conteudo": 76, "usuarios_censurados": 48, "usuarios_falha_coleta": 87}


@pytest.mark.db
def test_carga_que_falha_nao_apaga_a_anterior(tmp_path):
    pular_sem_banco()
    with banco_temporario() as url:
        executar(url)
        quebrada = tmp_path / "temas.parquet"
        pd.DataFrame({"conversa_id": ["1"], "versao_prompt": ["v2"], "modelo": ["x"]}).to_parquet(quebrada)
        with pytest.raises(Exception):  # noqa: B017 — qualquer erro serve: falta coluna na classificação
            executar(url, temas=quebrada)
        with psycopg.connect(url) as c:
            assert c.execute("SELECT count(*) FROM primeira_experiencia").fetchone()[0] == USUARIOS
            assert c.execute("SELECT status FROM meta_carga ORDER BY carga_id").fetchall() == [("ok",), ("erro",)]
