"""Contrato da API e regras dos indicadores, sobre a carga real num banco temporário (marca `db`).

A API conecta com o papel só de leitura (`acaso_leitura`), como no compose.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg
import pytest
from banco import banco_temporario, pular_sem_banco, trocar_banco
from carga import executar
from estatistica import wilson

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from api import create_app  # noqa: E402
from api.schemas import DIMENSOES  # noqa: E402

SNAPSHOT = Path(__file__).parent / "snapshots" / "openapi.json"
pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def ambiente():
    pular_sem_banco()
    with banco_temporario() as url:
        executar(url)
        nome = url.rsplit("/", 1)[1]
        leitura = trocar_banco(url, nome, "acaso_leitura", os.environ.get("ACASO_DB_SENHA_LEITURA",
                                                                          "acaso_leitura_local"))
        app = create_app({"ACASO_DB_URL": leitura, "TESTING": True})
        yield url, app.test_client()
        app.extensions["pool"].close()


def get(cliente, url: str, status: int = 200) -> dict:
    r = cliente.get(url)
    assert r.status_code == status, r.get_json()
    return r.get_json()


def test_wilson_do_banco_igual_ao_do_python(ambiente):
    url, _ = ambiente
    casos = [(0, 10), (1, 10), (5, 58), (635, 2219), (106, 106), (3, 7)]
    with psycopg.connect(url) as c:
        for s, n in casos:
            inf, sup = c.execute("SELECT wilson_inf(%s, %s), wilson_sup(%s, %s)", (s, n, s, n)).fetchone()
            assert (inf, sup) == pytest.approx(wilson(s, n), abs=1e-12)


def test_kpis_batem_com_a_analise_e_trazem_meta(ambiente):
    _, c = ambiente
    r = c.get("/api/kpis", headers={"X-Request-ID": "teste-123"})
    d = r.get_json()
    assert r.headers["X-Request-ID"] == "teste-123" and d["meta"]["request_id"] == "teste-123"
    assert d["retorno_7d"]["novos"] == 2219 and d["retorno_7d"]["voltaram"] == 635
    assert (round(d["retorno_7d"]["ic_inf"], 3), round(d["retorno_7d"]["ic_sup"], 3)) == (0.268, 0.305)
    assert d["recusa_total"]["voltaram"] == 106  # novatos com recusa total na 1ª conversa
    assert {"definicao_versao", "carga_id", "dados_ate", "fonte"} <= d["meta"].keys()


def test_coortes_mensais_somam_o_total_e_janeiro_tem_amostra_insuficiente(ambiente):
    _, c = ambiente
    linhas = get(c, "/api/retencao/coortes?granularidade=mes")["linhas"]
    assert sum(r["novos"] for r in linhas) == 2219 and len(linhas) == 13
    jan = next(r for r in linhas if r["coorte"] == "2024-01-01")
    assert jan["novos"] == 53 and not jan["amostra_suficiente"]


def test_total_semanal_aparece_mesmo_com_menos_de_20(ambiente):
    _, c = ambiente
    linhas = get(c, "/api/retencao/coortes?granularidade=semana")["linhas"]
    pequenas = [r for r in linhas if r["novos"] < 20]
    assert pequenas and all(not r["suprimido_k"] and r["taxa"] is not None for r in pequenas)


def test_k_anonimato_oculta_nivel_com_menos_de_20(ambiente):
    _, c = ambiente
    linhas = get(c, "/api/retencao/coortes?granularidade=mes&dimensao=estado_grupo")["linhas"]
    ocultas = [r for r in linhas if r["suprimido_k"]]
    assert ocultas, "esperava recortes de estado × mês com menos de 20 novatos"
    assert all(r["novos"] is None and r["voltaram"] is None and r["taxa"] is None and r["ic_inf"] is None
               for r in ocultas)
    assert all(r["novos"] >= 20 for r in linhas if not r["suprimido_k"])


def test_filtro_de_periodo_muda_o_denominador(ambiente):
    _, c = ambiente
    jul = get(c, "/api/kpis?inicio=2023-07-01&fim=2023-07-31")["retorno_7d"]
    assert jul["novos"] == 167 and jul["voltaram"] == 41


def test_efeitos_ajustado_e_bruto_da_recusa(ambiente):
    _, c = ambiente
    for ajuste, esperado in (("ajustado", -17.4), ("bruto", -14.2)):
        d = get(c, f"/api/fatores/efeitos?ajuste={ajuste}")
        rec = next(e for e in d["efeitos"] if e["fator"] == "recusa_total")
        assert round(rec["efeito_pp"], 1) == esperado and rec["ic_cruza_zero"] is False
    assert d["n_modelo"] == 2219 and len(d["efeitos"]) == 17


def test_dimensoes_da_api_iguais_as_da_view(ambiente):
    url, _ = ambiente
    with psycopg.connect(url) as c:
        banco = {r[0] for r in c.execute("SELECT DISTINCT dimensao FROM vw_novato_dimensao")}
    assert banco == set(DIMENSOES)


@pytest.mark.parametrize("consulta", [
    "/api/retencao/coortes?dimensao=xpto", "/api/retencao/coortes?granularidade=dia",
    "/api/kpis?inicio=2024-01-01&fim=2023-01-01", "/api/fatores/efeitos?ajuste=ipw",
])
def test_entrada_invalida_devolve_422(ambiente, consulta):
    _, c = ambiente
    assert c.get(consulta).status_code == 422


def test_health(ambiente):
    _, c = ambiente
    d = get(c, "/api/health")
    assert d["status"] == "ok" and d["ultima_carga"]["carga_id"] >= 1


def test_contrato_openapi_nao_muda_sem_revisao(ambiente):
    """Mudou o contrato? Rode com ACASO_ATUALIZAR_SNAPSHOT=1, revise o diff do snapshot e commite junto."""
    _, c = ambiente
    atual = get(c, "/openapi.json")
    if os.environ.get("ACASO_ATUALIZAR_SNAPSHOT") or not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(atual, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    assert atual == json.loads(SNAPSHOT.read_text())
