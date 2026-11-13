"""Efeitos: ajustado = bruto sem outro fator; o ajuste desfaz uma confusão conhecida; taxa esperada pelo perfil."""

from __future__ import annotations

import numpy as np
import pandas as pd
from efeitos import categorizar, coeficiente, diferenca_bruta, tabela_efeitos, taxa_esperada
from statsmodels.formula import api as smf


def _df(x, y, **extra) -> pd.DataFrame:
    return pd.DataFrame({"x": categorizar(pd.Series(x), "a"), "y": y} | extra)


def test_com_um_fator_so_o_ajustado_e_o_bruto():
    # Sem outro fator no modelo, não há o que ajustar: o coeficiente é a diferença de taxas.
    rng = np.random.default_rng(0)
    x = rng.choice(["a", "b"], 800)
    y = (rng.random(800) < np.where(x == "b", 0.4, 0.25)).astype(int)
    df = _df(x, y)
    res = smf.ols("y ~ x", data=df).fit(cov_type="HC1")
    ef, lo, hi = coeficiente(res, "x", "b")
    assert abs(ef - diferenca_bruta(df, "x", "b", "a")[0]) < 1e-9 and lo < ef < hi


def test_ajustado_recupera_o_efeito_com_confusao():
    # z causa x e y; o efeito real de x é +5 p.p. O bruto erra (seleção); o ajustado acerta dentro do IC.
    rng = np.random.default_rng(1)
    n = 6000
    z = rng.random(n) < 0.5
    x = np.where(rng.random(n) < np.where(z, 0.8, 0.2), "b", "a")  # quem tem z escolhe mais o "b"
    y = (rng.random(n) < 0.20 + 0.05 * (x == "b") + 0.30 * z).astype(int)
    df = _df(x, y, z=categorizar(pd.Series(z), False))
    res = smf.ols("y ~ x + z", data=df).fit(cov_type="HC1")
    linha = tabela_efeitos(df, res, {"x": ("a", "X")}).iloc[0]
    assert linha.nivel == "b" and linha.ic_inf < 5 < linha.ic_sup
    assert linha.bruto_pp - 5 > 10  # o bruto soma ~18 p.p. de seleção


def test_taxa_esperada_separa_perfil_de_taxa():
    # Base: perfil A volta 50%, perfil B volta 10% (média 30%).
    base = pd.DataFrame({"p": ["A"] * 100 + ["B"] * 100, "y": [1] * 50 + [0] * 50 + [1] * 10 + [0] * 90})
    so_a = pd.DataFrame({"p": ["A"] * 10})  # perfil diferente da base
    meio = pd.DataFrame({"p": ["A"] * 5 + ["B"] * 5})  # mesmo perfil da base
    novo = pd.DataFrame({"p": ["C"] * 4})  # perfil que a base não tem: recebe a média
    assert taxa_esperada(so_a, base, ["p"]) == 0.5
    assert taxa_esperada(meio, base, ["p"]) == 0.3
    assert taxa_esperada(novo, base, ["p"]) == 0.3
