"""Tela 1 — Quantos experimentam o assistente e quantos voltam em até 7 dias?"""

import pandas as pd
import streamlit as st
from cliente import ApiIndisponivel, get
from comum import DEFINICAO_RETORNO, erro_api, filtro_periodo, rodape
from graficos import barras_novatos, inteiro, linha_retorno, pct, preparar_taxas

st.title("Quantos experimentam o assistente e quantos voltam em até 7 dias?")
st.markdown(
    "Cada pessoa entra **uma vez**, no mês da sua 1ª sessão (a coorte). A pergunta é se ela abre uma nova "
    "sessão em até 7 dias. A linha mostra a taxa de cada coorte mensal; a faixa é o intervalo de confiança.")

inicio, fim = filtro_periodo("periodo_visao_geral")
try:
    kpis = get("/api/kpis", inicio=inicio, fim=fim)
    mensal = get("/api/retencao/coortes", granularidade="mes", inicio=inicio, fim=fim)
    semanal = get("/api/retencao/coortes", granularidade="semana", inicio=inicio, fim=fim)
except ApiIndisponivel as e:
    erro_api(e)

r, rec, meta = kpis.dados["retorno_7d"], kpis.dados["recusa_total"], kpis.dados["meta"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Novatos no período", inteiro(r["novos"]), border=True,
          help="Pessoas (IP) na 1ª sessão, elegíveis: observáveis por 7 dias e sem falha de coleta na janela.")
c2.metric("Voltam em até 7 dias", pct(r["taxa"]), border=True, help=DEFINICAO_RETORNO)
c2.caption(f"IC 95%: {pct(r['ic_inf'])} a {pct(r['ic_sup'])} · {inteiro(r['voltaram'])} voltaram")
c3.metric("Recusa total na estreia", pct(rec["taxa"]), border=True,
          help="O assistente recusou o pedido inteiro na 1ª conversa (classificação por LLM, BDR-010).")
c3.caption(f"IC 95%: {pct(rec['ic_inf'])} a {pct(rec['ic_sup'])} · {inteiro(rec['voltaram'])} novatos")
c4.metric("Dados até", f"{pd.Timestamp(meta['dados_ate']):%d/%m/%Y}", border=True,
          help="Último dia da base bruta. A base começa em 09/04/2023.")
c4.caption(f"carga #{meta['carga_id']}")
if not r["amostra_suficiente"]:
    st.warning("Amostra insuficiente no período escolhido: o IC passa de ±10 p.p. Leia a taxa com cautela.")

st.subheader("Retorno em 7 dias por mês de chegada")
dm = preparar_taxas(mensal.dados["linhas"])
st.altair_chart(linha_retorno(dm, r["taxa"], "mes"), width="stretch", theme=None)
st.caption(
    f"Linha tracejada = média do período ({pct(r['taxa'])}). Ponto cheio = amostra suficiente. "
    "**Ponto vazado = amostra insuficiente** (IC maior que ±10 p.p., cerca de "
    "80 novatos). Abril/2023 é o mês do lançamento; jan/2024 tem só 53 novatos (férias).")

st.subheader("Novatos por mês")
st.altair_chart(barras_novatos(dm, "mes"), width="stretch", theme=None)

with st.expander("Detalhe semanal (IC médio de ±15 p.p.: use para achar semanas fora do padrão)"):
    ds = preparar_taxas(semanal.dados["linhas"])
    st.altair_chart(linha_retorno(ds, r["taxa"], "semana"), width="stretch", theme=None)
    st.caption("Mediana de 39 novatos por semana. A semana de 17/07/2023 (9,1%; 3 de 33) fica abaixo do IC: "
               "quem chegou tinha o perfil de sempre, e o que caiu foi a taxa (notebook 04).")

with st.expander("Ver os números em tabela"):
    tabela = dm.assign(Mês=dm.coorte.dt.strftime("%m/%Y"))[
        ["Mês", "novos", "voltaram", "taxa_txt", "ic_txt", "amostra"]]
    tabela.columns = ["Mês", "Novatos", "Voltaram", "Retorno", "IC 95%", "Amostra"]
    st.dataframe(tabela, hide_index=True)

rodape(kpis, mensal, definicao=DEFINICAO_RETORNO)
