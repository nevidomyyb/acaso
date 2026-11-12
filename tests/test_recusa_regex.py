"""Regex de recusa (checagem cruzada da BDR-010): casos achados na amostra de 12/11."""

from __future__ import annotations

import pytest
from recusa_regex import recusa_regex


@pytest.mark.parametrize(
    "texto",
    [
        "Desculpe, mas não posso ajudar com isso.",
        "I'm sorry, but I can't assist with that.",
        "Infelizmente, eu sou um modelo de linguagem AI e não tenho a capacidade de lembrar eventos.",
        "I am an AI language model and cannot create images like GPT-4.",
        "As an AI, I do not have the ability to browse the internet.",
    ],
)
def test_recusas_detectadas(texto):
    assert recusa_regex(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "Olá! Como posso ajudar você hoje?",
        "As an AI language model, I do not have personal experiences. However, here are some tips.",
        "Claro! Aqui está o código em Python.",
        None,
    ],
)
def test_nao_recusas(texto):
    assert not recusa_regex(texto)
