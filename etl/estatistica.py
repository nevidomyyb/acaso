"""Funções estatísticas usadas na carga, na análise e na API."""

from __future__ import annotations

import math

Z95 = 1.959963984540054


def wilson(sucessos: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Intervalo de confiança de Wilson para uma proporção. Bom com n pequeno e taxa perto de 0 ou 1."""
    if n == 0:
        return (math.nan, math.nan)
    p = sucessos / n
    den = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / den
    margem = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return (max(0.0, centro - margem), min(1.0, centro + margem))
