"""Tela 2 — O que na 1ª experiência faz a pessoa voltar?"""

import pandas as pd
import streamlit as st
from cliente import ApiIndisponivel, get
from comum import DEFINICAO_RETORNO, erro_api, filtro_periodo, rodape
from graficos import barras_taxa, forest, pp, preparar_taxas
from rotulos import DIMENSOES, nivel

st.title("O que na 1ª experiência faz a pessoa voltar?")
st.markdown(
    "Cada linha compara um grupo de novatos com uma **referência** (por exemplo, celular contra desktop). "
    "O número é a diferença na taxa de retorno em 7 dias, em **pontos percentuais (p.p.)**.")

ajuste = st.segmented_control(
    "Comparação", ["ajustado", "bruto"], default="ajustado", required=True,
    format_func={"ajustado": "Entre pessoas iguais no resto (ajustado)", "bruto": "Sem ajuste (bruto)"}.get)
try:
    ef = get("/api/fatores/efeitos", ajuste=ajuste)
except ApiIndisponivel as e:
    erro_api(e)

df = pd.DataFrame(ef.dados["efeitos"])
st.altair_chart(forest(df), width="stretch", theme=None)
st.caption(
    "Ponto = efeito; traço = IC 95%. **Azul**: o IC não cruza o zero (o dado separa o efeito de \"nenhum efeito\"). "
    "**Cinza**: cruza o zero (sem evidência). Referências: tema = tarefa · horário = tarde · idioma = português · "
    "1ª resposta = 2º quartil · modelo = GPT-3.5 · dispositivo = desktop · recusa = sem recusa total.")

rec = df[df.fator == "recusa_total"].iloc[0]
c1, c2 = st.columns(2)
with c1:
    st.markdown("##### O que isso mostra")
    st.markdown(
        f"- **Recusa total na 1ª conversa: {pp(rec.efeito_pp)}** (IC {pp(rec.ic_inf)} a {pp(rec.ic_sup)}). "
        "É o maior efeito, e resiste a todas as checagens de sensibilidade.\n"
        "- **Ajustado** compara pessoas iguais em tema, horário, idioma, dispositivo, estado e mês. A diferença "
        "entre o bruto e o ajustado é **seleção**: o perfil de quem tem o fator, e não o fator.\n"
        "- **GPT-4**: o bruto parece positivo, mas no mesmo mês e com o mesmo perfil a vantagem some.")
with c2:
    st.markdown("##### O que isso não prova")
    st.markdown(
        "- Não é experimento: um fator que não está nos dados (motivação, origem do tráfego) pode explicar "
        "parte do efeito. Confirme os efeitos principais com um **teste A/B**.\n"
        "- São 17 comparações: cerca de 1 pode parecer real só por acaso.\n"
        "- Usuário = IP. IP dinâmico ou compartilhado mistura ou separa pessoas.")

st.divider()
st.subheader("Retorno por tema e por modelo, sem ajuste")
st.markdown("Taxa de cada grupo, com IC 95%. A linha tracejada é a média do período. Grupo com menos de 20 "
            "novatos fica oculto (proteção de privacidade, k = 20).")
inicio, fim = filtro_periodo("periodo_fatores")
try:
    kpis = get("/api/kpis", inicio=inicio, fim=fim)
    media = kpis.dados["retorno_7d"]["taxa"]
    tema = get("/api/retencao/coortes", granularidade="periodo", dimensao="tema_grupo", inicio=inicio, fim=fim)
    modelo = get("/api/retencao/coortes", granularidade="periodo", dimensao="familia_modelo", inicio=inicio, fim=fim)
except ApiIndisponivel as e:
    erro_api(e)


def bloco(resp, titulo: str) -> None:
    d = preparar_taxas(resp.dados["linhas"])
    d["rotulo"] = d.nivel.map(nivel)
    st.markdown(f"**{titulo}**")
    st.altair_chart(barras_taxa(d, media), width="stretch", theme=None)


c1, c2 = st.columns([3, 2])
with c1:
    bloco(tema, "Tema da 1ª conversa")
with c2:
    bloco(modelo, "Modelo")
    st.caption("Comparação bruta: o GPT-4 não existe de jul. a out./2023. A comparação justa (mesmo mês) está "
               "no gráfico de cima.")

with st.expander("Abrir por outra dimensão"):
    outras = {k: v for k, v in DIMENSOES.items() if k not in ("tema_grupo", "familia_modelo")}
    dim = st.selectbox("Dimensão", list(outras), format_func=outras.get)
    try:
        outra = get("/api/retencao/coortes", granularidade="periodo", dimensao=dim, inicio=inicio, fim=fim)
    except ApiIndisponivel as e:
        erro_api(e)
    bloco(outra, outras[dim])

rodape(ef, tema, definicao=DEFINICAO_RETORNO + " Efeito ajustado: regressão linear com IC robusto (HC1).")
