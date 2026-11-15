"""Gráficos em Altair com a paleta da análise (analysis/estilo.py, validada pela skill de dataviz).

Regras: 1 eixo por gráfico; IC sempre visível; amostra insuficiente = marca vazada e esmaecida, nunca escondida;
texto em tinta neutra, nunca na cor da série; tooltip em toda marca.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

COR = "#2a78d6"  # série 1 (azul)
COR_2 = "#eb6834"  # série 2 (laranja)
TINTA, TINTA_2, MUDO = "#0b0b0b", "#52514e", "#898781"
GRADE, EIXO, FUNDO = "#e1e0d9", "#c3c2b7", "#fcfcfb"
PCT = "replace(format(datum.value, '.0%'), '.', ',')"
PP = "(datum.value == 0 ? '0' : replace(format(datum.value, '+.0f'), '.', ',')) + ' p.p.'"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def pct(x: float | None, casas: int = 1) -> str:
    return "—" if x is None or pd.isna(x) else f"{100 * x:.{casas}f}%".replace(".", ",")


def pp(x: float | None) -> str:
    return "—" if x is None or pd.isna(x) else f"{x:+.1f}".replace(".", ",") + " p.p."


def inteiro(x: float | None) -> str:
    return "—" if x is None or pd.isna(x) else f"{int(x):,}".replace(",", ".")


def mes_ano(d: pd.Timestamp) -> str:
    return f"{MESES[d.month - 1]}/{d.year % 100:02d}"


def _tema(ch: alt.Chart) -> alt.Chart:
    return (ch.configure(background=FUNDO, font="Inter, system-ui, sans-serif")
            .configure_view(stroke=None)
            .configure_axis(gridColor=GRADE, domainColor=EIXO, tickColor=EIXO, labelColor=TINTA_2,
                            titleColor=TINTA_2, labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
            .configure_legend(labelColor=TINTA_2, titleColor=TINTA_2, labelFontSize=12, orient="top",
                              titleFontWeight="normal"))


def preparar_taxas(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    if "coorte" in df and df.coorte.notna().any():
        df["coorte"] = pd.to_datetime(df.coorte)
    df["taxa_txt"] = df.taxa.map(pct)
    df["ic_txt"] = [f"{pct(a)} a {pct(b)}" for a, b in zip(df.ic_inf, df.ic_sup, strict=True)]
    df["novos_txt"] = df.novos.map(inteiro)
    df["amostra"] = df.amostra_suficiente.map({True: "suficiente", False: "insuficiente (IC > ±10 p.p.)"})
    return df


def linha_retorno(df: pd.DataFrame, media: float, granularidade: str) -> alt.Chart:
    """Taxa de retorno por coorte, com a faixa do IC 95%. Coorte com amostra insuficiente: ponto vazado."""
    df = df.assign(rotulo=df.coorte.map(mes_ano) if granularidade == "mes" else df.coorte.dt.strftime("%d/%m/%y"))
    x = alt.X("coorte:T", title=None, axis=alt.Axis(format="%m/%y" if granularidade == "mes" else "%d/%m/%y",
                                                    grid=False, labelAngle=0, tickCount=8))
    y = alt.Y("taxa:Q", title="Retorno em 7 dias", scale=alt.Scale(domain=[0, max(0.6, df.ic_sup.max())]),
              axis=alt.Axis(labelExpr=PCT, tickCount=6))
    dica = [alt.Tooltip("rotulo:N", title="Coorte"), alt.Tooltip("taxa_txt:N", title="Retorno"),
            alt.Tooltip("ic_txt:N", title="IC 95%"), alt.Tooltip("novos_txt:N", title="Novatos"),
            alt.Tooltip("voltaram:Q", title="Voltaram"), alt.Tooltip("amostra:N", title="Amostra")]
    base = alt.Chart(df)
    faixa = base.mark_area(color=COR, opacity=0.14).encode(x=x, y=alt.Y("ic_inf:Q"), y2="ic_sup:Q")
    linha = base.mark_line(color=COR, strokeWidth=2).encode(x=x, y=y)
    pontos = base.mark_point(size=70, strokeWidth=2, opacity=1).encode(
        x=x, y=y, tooltip=dica,
        fill=alt.condition("datum.amostra_suficiente", alt.value(COR), alt.value(FUNDO)),
        stroke=alt.condition("datum.amostra_suficiente", alt.value(FUNDO), alt.value(MUDO)))
    ref = alt.Chart(pd.DataFrame({"m": [media]}))
    regua = ref.mark_rule(color=MUDO, strokeDash=[4, 4], strokeWidth=1).encode(y="m:Q")
    return _tema((faixa + regua + linha + pontos).properties(height=300))


def barras_novatos(df: pd.DataFrame, granularidade: str) -> alt.Chart:
    df = df.assign(rotulo=df.coorte.map(mes_ano) if granularidade == "mes" else df.coorte.dt.strftime("%d/%m/%y"))
    unidade = "month" if granularidade == "mes" else "week"
    ch = alt.Chart(df).mark_bar(color=COR, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("yearmonth(coorte):O" if unidade == "month" else "coorte:T", title=None,
                axis=alt.Axis(labelExpr="timeFormat(datum.value, '%m/%y')", labelAngle=0, grid=False)),
        y=alt.Y("novos:Q", title="Novatos", axis=alt.Axis(tickCount=4)),
        tooltip=[alt.Tooltip("rotulo:N", title="Coorte"), alt.Tooltip("novos_txt:N", title="Novatos")])
    return _tema(ch.properties(height=180))


def forest(df: pd.DataFrame) -> alt.Chart:
    """Efeito de cada nível contra a referência (p.p.), com IC 95%. Azul = IC fora do zero; cinza = cruza o zero."""
    df = df[~df.suprimido_k].copy()
    df["linha"] = [f"{n}  ·  {f.lower()}" if f != "Recusa total na 1ª conversa" else "Recusa total na 1ª conversa"
                   for n, f in zip(df.rotulo_nivel, df.rotulo_fator, strict=True)]
    df["evidencia"] = df.ic_cruza_zero.map({False: "IC fora do zero", True: "IC cruza o zero (sem evidência)"})
    df["efeito_txt"] = df.efeito_pp.map(pp)
    df["ic_txt"] = [f"{pp(a)} a {pp(b)}" for a, b in zip(df.ic_inf, df.ic_sup, strict=True)]
    df["ref_txt"] = "contra: " + df.rotulo_referencia
    ordem = df.sort_values("efeito_pp", ascending=False).linha.tolist()
    lim = max(abs(df.ic_inf.min()), abs(df.ic_sup.max())) + 2
    y = alt.Y("linha:N", sort=ordem, title=None, axis=alt.Axis(labelLimit=340, labelFontSize=12, grid=False,
                                                                  domain=False, ticks=False, labelPadding=8))
    x = alt.X("efeito_pp:Q", title="Diferença no retorno em 7 dias, em pontos percentuais",
              scale=alt.Scale(domain=[-lim, lim]), axis=alt.Axis(labelExpr=PP, tickCount=8))
    cor = alt.Color("evidencia:N", title=None, scale=alt.Scale(
        domain=["IC fora do zero", "IC cruza o zero (sem evidência)"], range=[COR, MUDO]))
    dica = [alt.Tooltip("linha:N", title="Nível"), alt.Tooltip("ref_txt:N", title="Referência"),
            alt.Tooltip("efeito_txt:N", title="Efeito"), alt.Tooltip("ic_txt:N", title="IC 95%"),
            alt.Tooltip("n:Q", title="Novatos no nível")]
    base = alt.Chart(df)
    zero = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=TINTA_2, strokeWidth=1).encode(x="z:Q")
    ic = base.mark_rule(strokeWidth=2).encode(y=y, x=alt.X("ic_inf:Q"), x2="ic_sup:Q", color=cor, tooltip=dica)
    ponto = base.mark_circle(size=90, opacity=1, stroke=FUNDO, strokeWidth=2).encode(
        y=y, x=x, color=cor, tooltip=dica)
    return _tema((zero + ic + ponto).properties(height=28 * len(df) + 40))


def barras_taxa(df: pd.DataFrame, media: float, titulo_eixo: str = "Retorno em 7 dias") -> alt.Chart:
    """Retorno por nível (barras horizontais) com IC 95%. Nível com < 20 novatos: sem barra, com aviso."""
    df = df.copy()
    df["status"] = df.suprimido_k.map({True: "menos de 20 novatos: oculto", False: ""})
    ordem = df.sort_values("taxa", ascending=False, na_position="last").rotulo.tolist()
    y = alt.Y("rotulo:N", sort=ordem, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=12, domain=False,
                                                                   ticks=False, grid=False, labelPadding=8))
    x = alt.X("taxa:Q", title=titulo_eixo, scale=alt.Scale(domain=[0, max(0.7, df.ic_sup.max(skipna=True))]),
              axis=alt.Axis(labelExpr=PCT, tickCount=6))
    dica = [alt.Tooltip("rotulo:N", title="Nível"), alt.Tooltip("taxa_txt:N", title="Retorno"),
            alt.Tooltip("ic_txt:N", title="IC 95%"), alt.Tooltip("novos_txt:N", title="Novatos"),
            alt.Tooltip("amostra:N", title="Amostra")]
    base = alt.Chart(df)
    barras = base.mark_bar(color=COR, height=14, cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
        y=y, x=x, tooltip=dica,
        opacity=alt.condition("datum.amostra_suficiente", alt.value(1.0), alt.value(0.4)))
    ic = base.mark_rule(color=TINTA_2, strokeWidth=1.5).encode(y=y, x="ic_inf:Q", x2="ic_sup:Q", tooltip=dica)
    oculto = base.transform_filter("datum.suprimido_k").mark_text(align="left", dx=4, color=MUDO, fontSize=11) \
        .encode(y=y, x=alt.value(0), text="status:N")
    ref = alt.Chart(pd.DataFrame({"m": [media]})).mark_rule(color=MUDO, strokeDash=[4, 4]).encode(x="m:Q")
    return _tema((barras + ic + ref + oculto).properties(height=34 * len(df) + 30))
