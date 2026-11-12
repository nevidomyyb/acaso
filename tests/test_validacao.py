"""Validação manual: alocação estratificada e acurácia ponderada pela base."""

from __future__ import annotations

import pandas as pd
import pytest
from validacao_classificacao import acuracia_ponderada, alocar


def test_alocar_garante_minimo_e_respeita_total():
    contagens = pd.Series({"grande": 1000, "medio": 200, "raro": 3})
    a = alocar(contagens, n=50, minimo=8)
    assert a["raro"] == 3  # estrato menor que o mínimo entra inteiro
    assert a["medio"] >= 8 and a["grande"] > a["medio"]
    assert abs(int(a.sum()) - 50) <= 1  # arredondamento


def test_acuracia_ponderada_usa_o_peso_da_base():
    # Amostra igual por tema, mas "a" é 90% da base: a acurácia ponderada fica perto da de "a".
    df = pd.DataFrame(
        {"tema_previsto": ["a"] * 10 + ["b"] * 10, "acerto_tema": [True] * 10 + [False] * 10},
    )
    acc, lo, hi = acuracia_ponderada(df, pd.Series({"a": 900, "b": 100}))
    assert acc == pytest.approx(0.9)
    assert lo <= acc <= hi
