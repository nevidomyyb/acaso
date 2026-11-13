"""Estilo comum dos gráficos dos notebooks (paleta validada para daltonismo; ver skill de dataviz)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "etl"))

BRUTA = str(RAIZ / "data" / "raw" / "wildchat_br.parquet")
VOLUME = str(RAIZ / "data" / "raw" / "wildchat_volume_diario.parquet")

# Paleta categórica (ordem fixa) e tinta
AZUL, LARANJA, AQUA, AMARELO = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
TINTA, TINTA_2, TINTA_MUDA = "#0b0b0b", "#52514e", "#898781"
GRADE, EIXO, FUNDO = "#e1e0d9", "#c3c2b7", "#fcfcfb"
CRITICO = "#d03b3b"


def aplicar() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": FUNDO,
            "axes.facecolor": FUNDO,
            "figure.figsize": (9, 3.6),
            "figure.dpi": 110,
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.edgecolor": EIXO,
            "axes.labelcolor": TINTA_2,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.titlecolor": TINTA,
            "axes.titlelocation": "left",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,  # grade atrás das barras
            "grid.color": GRADE,
            "grid.linewidth": 0.8,
            "xtick.color": TINTA_MUDA,
            "ytick.color": TINTA_MUDA,
            "lines.linewidth": 2,
            "legend.frameon": False,
        }
    )


def nota(ax: plt.Axes, texto: str) -> None:
    """Rodapé com definição e fonte do número (cada gráfico se explica sozinho)."""
    ax.annotate(texto, xy=(0, -0.22), xycoords="axes fraction", fontsize=8, color=TINTA_MUDA, va="top")
