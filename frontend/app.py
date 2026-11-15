"""Dashboard de retenção (ADR-003): Streamlit com tema próprio, lendo só a API."""

import streamlit as st

st.set_page_config(page_title="Retenção do assistente", page_icon=":material/insights:", layout="wide")

st.markdown("""
<style>
  .block-container { max-width: 1180px; padding-top: 2rem; }
  h1 { font-size: 1.75rem !important; font-weight: 650 !important; letter-spacing: -0.01em; }
  h3 { font-size: 1.15rem !important; margin-top: 1.25rem !important; }
  [data-testid="stMetricValue"] { font-size: 1.9rem; font-variant-numeric: tabular-nums; }
  [data-testid="stCaptionContainer"] { color: #52514e; }
</style>
""", unsafe_allow_html=True)

paginas = st.navigation([
    st.Page("paginas/visao_geral.py", title="Quantos voltam", icon=":material/show_chart:", default=True),
    st.Page("paginas/fatores.py", title="O que faz voltar", icon=":material/tune:"),
], position="top")

with st.sidebar:
    st.markdown("**Retenção do assistente de IA**")
    st.caption("WildChat-1M · conversas do Brasil · abr/2023 a abr/2024")
    st.caption("O dashboard mostra só números agregados. Nunca mostra texto das conversas, IP, navegador nem "
               "grupos com menos de 20 pessoas.")

paginas.run()
