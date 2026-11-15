"""Cliente da API. O dashboard só fala com a API, nunca com o banco (regra 2).

Cache: cada resposta fica 5 min na memória do processo do dashboard (st.cache_data). A carga roda uma vez por
dia em produção; 5 min é o atraso máximo entre uma carga nova e a tela.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")
CACHE_S = 300


@dataclass
class Resposta:
    dados: dict
    rota: str
    request_id: str


class ApiIndisponivel(Exception):
    pass


@st.cache_data(ttl=CACHE_S, show_spinner=False)
def _get(rota: str, params: tuple) -> tuple[dict, str]:
    try:
        r = requests.get(f"{API_URL}{rota}", params=dict(params), timeout=15)
    except requests.RequestException as e:
        raise ApiIndisponivel(f"API fora do ar ({API_URL}): {type(e).__name__}") from e
    if r.status_code != 200:
        raise ApiIndisponivel(f"{rota} respondeu {r.status_code}: {r.text[:200]}")
    return r.json(), r.headers.get("X-Request-ID", "")


def get(rota: str, **params) -> Resposta:
    limpos = tuple(sorted((k, str(v)) for k, v in params.items() if v is not None))
    dados, rid = _get(rota, limpos)
    return Resposta(dados, rota, rid)
