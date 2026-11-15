"""Os 4 endpoints (PROJECT §6.3). Toda resposta leva `meta` com request_id, versão das definições e carga."""

from __future__ import annotations

from flask import g
from flask_smorest import Blueprint

from . import consultas
from .banco import consultar, ultima_carga
from .schemas import (
    CoortesQuerySchema,
    CoortesSchema,
    EfeitosQuerySchema,
    EfeitosSchema,
    HealthSchema,
    KpisSchema,
    PeriodoSchema,
)

blp_kpis = Blueprint("kpis", __name__, url_prefix="/api", description="Indicadores principais do período")
blp_retencao = Blueprint("retencao", __name__, url_prefix="/api/retencao", description="Retorno em 7 dias por coorte")
blp_fatores = Blueprint("fatores", __name__, url_prefix="/api/fatores", description="Efeito de cada fator")
blp_health = Blueprint("health", __name__, url_prefix="/api", description="Estado da API e do banco")


def meta(fonte: str) -> dict:
    c = ultima_carga() or {}
    g.carga_id = c.get("carga_id")
    return {"request_id": g.request_id, "definicao_versao": c.get("definicao_versao"), "carga_id": c.get("carga_id"),
            "dados_de": c.get("dados_de"), "dados_ate": c.get("dados_ate"), "carga_em": c.get("fim_utc"),
            "fonte": fonte}


def taxa(n, sucessos, t, inf, sup, suficiente) -> dict:
    return {"novos": n, "voltaram": sucessos, "taxa": t, "ic_inf": inf, "ic_sup": sup,
            "amostra_suficiente": bool(suficiente)}


@blp_kpis.route("/kpis")
@blp_kpis.arguments(PeriodoSchema, location="query")
@blp_kpis.response(200, KpisSchema)
def kpis(q: dict):
    """Novatos, retorno em 7 dias e % de recusa total na 1ª conversa, com IC 95% de Wilson."""
    r = consultar(consultas.KPIS, q)[0]
    return {
        "meta": meta("primeira_experiencia (elegíveis)"), "pais": q["pais"], "inicio": q["inicio"], "fim": q["fim"],
        "retorno_7d": taxa(r["n"], r["voltaram"], r["taxa"], r["ic_inf"], r["ic_sup"], r["amostra_suficiente"]),
        "recusa_total": taxa(r["n"], r["recusas"], r["taxa_recusa"], r["recusa_ic_inf"], r["recusa_ic_sup"],
                             r["recusa_amostra_suficiente"]),
    }


@blp_retencao.route("/coortes")
@blp_retencao.arguments(CoortesQuerySchema, location="query")
@blp_retencao.response(200, CoortesSchema)
def coortes(q: dict):
    """Retorno em 7 dias por coorte (mês ou semana) ou no período, opcionalmente aberto por uma dimensão.

    Nível com menos de 20 novatos volta com `suprimido_k = true` e sem números (k-anonimato).
    """
    if q["dimensao"] == "geral" and q["granularidade"] != "periodo":
        linhas = consultar(consultas.COORTES_GERAL, q | {"trunc": "month" if q["granularidade"] == "mes" else "week"})
        fonte = "vw_retorno_coorte"
    else:
        linhas = consultar(consultas.COORTES_DIMENSAO, q)
        fonte = "vw_novato_dimensao"
    return {"meta": meta(fonte), "pais": q["pais"], "granularidade": q["granularidade"], "dimensao": q["dimensao"],
            "linhas": linhas}


@blp_fatores.route("/efeitos")
@blp_fatores.arguments(EfeitosQuerySchema, location="query")
@blp_fatores.response(200, EfeitosSchema)
def efeitos(q: dict):
    """Efeito de cada nível contra a referência, em p.p., com IC 95%: bruto ou ajustado (regressão linear)."""
    linhas = consultar(consultas.EFEITOS, q)
    for r in linhas:
        r["ic_cruza_zero"] = None if r["ic_inf"] is None else r["ic_inf"] <= 0 <= r["ic_sup"]
    primeiro = linhas[0] if linhas else {}
    return {"meta": meta("resultado_efeitos"), "pais": q["pais"], "ajuste": q["ajuste"],
            "metodo": primeiro.get("metodo"), "n_modelo": primeiro.get("n_modelo"), "efeitos": linhas}


@blp_health.route("/health")
@blp_health.response(200, HealthSchema)
@blp_health.alt_response(503, schema=HealthSchema)
def health():
    """Estado da API, do banco e da última carga."""
    try:
        c = ultima_carga()
    except Exception as e:  # banco fora: a API responde, com 503
        return {"status": "degradado", "banco": f"erro: {type(e).__name__}", "ultima_carga": None}, 503
    if c is None:
        return {"status": "degradado", "banco": "ok", "ultima_carga": None}, 503
    return {"status": "ok", "banco": "ok",
            "ultima_carga": {"carga_id": c["carga_id"], "fim_utc": c["fim_utc"].isoformat(),
                             "dados_ate": c["dados_ate"].isoformat()}}
