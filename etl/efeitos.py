"""Efeito de cada fator da 1ª experiência no retorno em 7 dias (PROJECT.md §5.3 a §5.5).

Três contas, todas em pontos percentuais (p.p.). O glossário está em docs/METODOLOGIA.md §5 (notebook 04).
  - Bruto: taxa de retorno do grupo menos a taxa do grupo de referência. Mistura o efeito do fator com o perfil de
    quem tem o fator (seleção).
  - Ajustado: regressão linear do retorno (1 = voltou, 0 = não voltou) com todos os fatores e os controles juntos.
    O coeficiente de um nível já é a diferença em p.p. contra a referência, entre pessoas iguais nos outros
    fatores. IC 95% com erro-padrão robusto (HC1): num resultado 0/1, a variância muda de pessoa para pessoa.
  - Taxa esperada pelo perfil: a taxa que um grupo (ex.: uma semana) teria se cada pessoa voltasse na taxa normal
    do seu perfil. Separa "mudou quem chegou" (perfil) de "mudou o comportamento" (taxa).

O módulo serve ao notebook 04 e à carga (a tabela `resultado_efeitos` do dashboard): a regressão roda no ETL,
nunca no request.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from estatistica import Z95

# coluna -> (nível de referência, rótulo para a tela). A ordem é a ordem de exibição.
FATORES: dict[str, tuple[object, str]] = {
    "recusa_total": (False, "Recusa total na 1ª conversa"),
    "tema_grupo": ("tarefa_conhecimento", "Tema da 1ª conversa"),
    "faixa_horaria": ("tarde", "Horário da estreia"),
    "dispositivo": ("desktop", "Dispositivo"),
    "idioma_3": ("portugues", "Idioma"),
    "resposta_quartil": ("Q2", "Tamanho da 1ª resposta"),
    "familia_modelo": ("gpt-3.5", "Modelo"),
}
# Nome legível de cada nível, para o notebook e para a tela.
ROTULOS: dict[object, str] = {
    True: "Sim", False: "Não",
    "tarefa_conhecimento": "Tarefa (conhecimento, estudo, trabalho)", "saudacao_teste": "Saudação ou teste",
    "programacao_tecnologia": "Programação e tecnologia", "criativo_entretenimento": "Criativo e entretenimento",
    "traducao_reescrita": "Tradução e reescrita", "conselho_pessoal": "Conselho pessoal", "outro": "Outro",
    "madrugada": "Madrugada (0–5h)", "manha": "Manhã (6–11h)", "tarde": "Tarde (12–17h)", "noite": "Noite (18–23h)",
    "desktop": "Desktop", "mobile": "Celular", "portugues": "Português", "ingles": "Inglês",
    "Q1": "1º quartil (curta, ≤ 119 caracteres)", "Q2": "2º quartil", "Q3": "3º quartil", "Q4": "4º quartil (longa)",
    "gpt-3.5": "GPT-3.5", "gpt-4": "GPT-4",
}
# Controles: entram no ajuste para igualar os grupos, mas não viram achado (02_eda, seções 5 e 6).
# O mês como controle faz cada comparação acontecer dentro do mesmo mês (é o que trata o GPT-4 × tempo).
CONTROLES: dict[str, object] = {"estado_grupo": "São Paulo", "mes": "2023-05"}
VOLUME = "respostas_sessao1"  # fora do modelo principal (é consequência da experiência); só na sensibilidade


def preparar(pe: pd.DataFrame) -> pd.DataFrame:
    """Elegíveis da `primeira_experiencia`, com colunas derivadas e categorias com a referência em 1º lugar."""
    df = pe[pe.elegivel].copy()
    df["y"] = df.voltou_7d.astype(int)
    df["resposta_quartil"] = pd.qcut(df.tam_resposta_1, 4, labels=["Q1", "Q2", "Q3", "Q4"])
    df["mes"] = df.coorte_mes.dt.strftime("%Y-%m")
    df[VOLUME] = pd.cut(df.n_respostas_sessao1, [0, 1, 2, 4, 9, 10**6], labels=["1", "2", "3-4", "5-9", "10+"])
    refs = {c: r for c, (r, _) in FATORES.items()} | CONTROLES | {VOLUME: "1"}
    for col, ref in refs.items():
        df[col] = categorizar(df[col], ref)
    for col in ("recusa_regex", "recusa_total_sessao"):  # variantes da recusa (BDR-010), mesma referência
        df[col] = categorizar(df[col], False)
    return df


def categorizar(s: pd.Series, ref: object) -> pd.Series:
    """Categoria com a referência em 1º lugar: a regressão compara cada nível contra ela."""
    niveis = [ref] + sorted((v for v in pd.unique(s) if v != ref), key=str)
    return pd.Categorical(s, categories=niveis)


def formula(fatores: list[str], controles: list[str]) -> str:
    return "y ~ " + " + ".join(fatores + controles)


def ajustar(df: pd.DataFrame, fatores: list[str] | None = None, controles: list[str] | None = None):
    """Regressão linear do retorno (0/1) em todos os fatores e controles, com IC robusto (HC1)."""
    fatores = list(FATORES) if fatores is None else fatores
    controles = list(CONTROLES) if controles is None else controles
    return smf.ols(formula(fatores, controles), data=df).fit(cov_type="HC1")


def coeficiente(res, col: str, nivel: object) -> tuple[float, float, float]:
    """Efeito ajustado do `nivel` contra a referência de `col`, em proporção, com IC 95%."""
    nome = f"{col}[T.{nivel}]"
    lo, hi = res.conf_int().loc[nome]
    return float(res.params[nome]), float(lo), float(hi)


def diferenca_bruta(df: pd.DataFrame, col: str, nivel: object, ref: object) -> tuple[float, float, float]:
    """Taxa do `nivel` menos a taxa da `ref`, sem ajuste, com IC 95%."""
    a, b = df.y[df[col] == nivel], df.y[df[col] == ref]
    d = a.mean() - b.mean()
    ep = np.sqrt(a.mean() * (1 - a.mean()) / len(a) + b.mean() * (1 - b.mean()) / len(b))
    return float(d), float(d - Z95 * ep), float(d + Z95 * ep)


def tabela_efeitos(df: pd.DataFrame, res, fatores: dict[str, tuple[object, str]] | None = None) -> pd.DataFrame:
    """Uma linha por nível (contra a referência): n, bruto e ajustado, em pontos percentuais."""
    linhas = []
    for col, (ref, rotulo) in (FATORES if fatores is None else fatores).items():
        for nivel in df[col].cat.categories:
            if nivel == ref:
                continue
            bruto = diferenca_bruta(df, col, nivel, ref)
            aj = coeficiente(res, col, nivel)
            linhas.append(
                {"fator": col, "rotulo": rotulo, "nivel": nivel, "referencia": ref, "n": int((df[col] == nivel).sum())}
                | dict(zip(("bruto_pp", "bruto_ic_inf", "bruto_ic_sup"), (100 * v for v in bruto), strict=True))
                | dict(zip(("ajustado_pp", "ic_inf", "ic_sup"), (100 * v for v in aj), strict=True))
            )
    return pd.DataFrame(linhas)


def taxa_esperada(grupo: pd.DataFrame, base: pd.DataFrame, cols: list[str]) -> float:
    """Taxa que o `grupo` teria se cada pessoa voltasse na taxa da `base` para o seu perfil (`cols`).

    Perfil sem ninguém na base recebe a taxa média da base.
    """
    taxa = base.groupby(cols, observed=True).y.mean().rename("_taxa")
    return float(grupo.join(taxa, on=cols)["_taxa"].fillna(base.y.mean()).mean())
