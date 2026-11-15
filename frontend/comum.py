"""Peças comuns das telas: cabeçalho, filtro de período, rodapé com definição e fonte, erro da API."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from cliente import ApiIndisponivel, Resposta, get
from graficos import MESES

DEFINICAO_RETORNO = (
    "**Retorno em 7 dias** = novatos com nova sessão em até 7×24 h do início da 1ª sessão ÷ novatos elegíveis. "
    "**Novato** = 1ª sessão de um IP no Brasil (BDR-001, BDR-003). **Sessão** = respostas do assistente sem "
    "pausa de 30 min (BDR-002). **Elegível** = observável por 7 dias, sem falha de coleta na janela (BDR-006). "
    "IC 95% de Wilson."
)


def rodape(*respostas: Resposta, definicao: str | None = None) -> None:
    meta = respostas[0].dados["meta"]
    fontes = " · ".join(f"`GET {r.rota}` ({r.dados['meta']['fonte']}, request_id `{r.request_id}`)"
                        for r in respostas)
    texto = f"{definicao}  \n" if definicao else ""
    st.caption(f"{texto}Fonte: {fontes}. Dados até {pd.Timestamp(meta['dados_ate']):%d/%m/%Y} · carga "
               f"#{meta['carga_id']} · definições {meta['definicao_versao']} · WildChat-1M, Brasil.")


def erro_api(e: ApiIndisponivel) -> None:
    st.error(f"Não foi possível carregar os números agora. {e}")
    st.stop()


def filtro_periodo(chave: str) -> tuple[date | None, date | None]:
    """Período pela 1ª sessão do novato, em meses (o padrão é a base inteira)."""
    try:
        meses = get("/api/retencao/coortes", granularidade="mes").dados["linhas"]
    except ApiIndisponivel as e:
        erro_api(e)
    opcoes = [pd.Timestamp(m["coorte"]).date() for m in meses]
    rotulo = {d: f"{MESES[d.month - 1]}/{d.year}" for d in opcoes}
    ini, fim = st.select_slider("Período (mês da 1ª sessão do novato)", options=opcoes,
                                value=(opcoes[0], opcoes[-1]), format_func=rotulo.get, key=chave)
    fim_mes = (pd.Timestamp(fim) + pd.offsets.MonthEnd(0)).date()
    if ini == opcoes[0] and fim == opcoes[-1]:
        return None, None
    return ini, fim_mes
