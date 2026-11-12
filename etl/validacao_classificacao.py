"""Validação manual da classificação de tema e recusa (ADR-011; meta do ADR-004: acurácia ≥ 85%).

Subcomandos:
  amostra  sorteia N conversas estratificadas pelo tema previsto  -> data/work/validacao_{versao}/rotulos.csv
  avaliar  lê o CSV rotulado e mede acurácia (bruta e ponderada), por tema e da recusa

A amostra é estratificada: temas raros ganham um mínimo de casos. Por isso a acurácia geral é PONDERADA pelo
tamanho de cada tema na base (estimador estratificado), e não a média simples da amostra.

O CSV tem texto das conversas: fica em data/work (fora do git) e nunca vai para a base analítica.
Rotule as colunas `tema_humano` e `recusa_humano` com os mesmos valores do prompt (etl/prompts/).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_bedrock import MAX_CHARS_ASSISTENTE, MAX_CHARS_USUARIO, RECUSAS, TEMAS, carregar_entradas, truncar  # noqa: E402
from estatistica import Z95, wilson  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BRUTA = RAIZ / "data" / "raw" / "wildchat_br.parquet"


def alocar(contagens: pd.Series, n: int, minimo: int) -> pd.Series:
    """Mínimo por estrato (ou o estrato inteiro, se menor) e o resto proporcional ao tamanho."""
    base = contagens.clip(upper=minimo)
    resto = n - int(base.sum())
    if resto <= 0:
        return base
    folga = contagens - base
    extra = (folga / folga.sum() * resto).round().astype(int).clip(upper=folga)
    return base + extra


def cmd_amostra(args: argparse.Namespace) -> None:
    pred = pd.read_parquet(args.resultado)
    pred = pred[(pred.fonte == "llm") & pred.erro.isna()]
    # Conversas usadas no ajuste do prompt ficam fora: medir nelas inflaria a acurácia.
    arquivos = (RAIZ / "data" / "work").glob("cpu_*_amostra*/selecao.json")
    ajuste = {c for f in arquivos for c in json.loads(f.read_text())}
    pred = pred[~pred.conversa_id.isin(ajuste)]
    print(f"fora da amostra (usadas no ajuste do prompt): {len(ajuste)}")
    alvo = alocar(pred.tema.value_counts(), args.n, args.minimo)
    partes = [pred[pred.tema == t].sample(int(k), random_state=args.semente) for t, k in alvo.items() if k > 0]
    amostra = pd.concat(partes)
    textos = {e["conversa_id"]: e for e in carregar_entradas(args.bruta)}
    linhas = []
    for _, r in amostra.sample(frac=1, random_state=args.semente).iterrows():  # embaralha: rotule sem ver o estrato
        e = textos[r.conversa_id]
        linhas.append(
            {
                "conversa_id": r.conversa_id,
                "msg_usuario": truncar(e["msg_usuario"], MAX_CHARS_USUARIO),
                "msg_assistente": truncar(e["msg_assistente"], MAX_CHARS_ASSISTENTE),
                "tema_humano": "",
                "recusa_humano": "",
                "tema_previsto": r.tema,
                "recusa_prevista": r.recusa,
            }
        )
    destino = RAIZ / "data" / "work" / f"validacao_{args.versao}" / "rotulos.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(linhas).to_csv(destino, index=False)
    print(f"{len(linhas)} conversas -> {destino}")
    print("por tema previsto:\n" + alvo.to_string())
    print("Dica: rotule antes de olhar as colunas *_previsto (oculte-as na planilha).")


def acuracia_ponderada(df: pd.DataFrame, tamanhos: pd.Series) -> tuple[float, float, float]:
    """Estimador estratificado: Σ W_h · acc_h, com variância Σ W_h² · p(1−p)/n_h."""
    w = tamanhos / tamanhos.sum()
    acc, var = 0.0, 0.0
    for t, g in df.groupby("tema_previsto"):
        p, n = g.acerto_tema.mean(), len(g)
        acc += w.get(t, 0) * p
        var += w.get(t, 0) ** 2 * p * (1 - p) / n
    ep = math.sqrt(var)
    return acc, max(0.0, acc - Z95 * ep), min(1.0, acc + Z95 * ep)


def cmd_avaliar(args: argparse.Namespace) -> None:
    caminho = args.rotulos or RAIZ / "data" / "work" / f"validacao_{args.versao}" / "rotulos.csv"
    rot = pd.read_csv(caminho, dtype=str).fillna("")
    rot = rot[rot.tema_humano.str.strip() != ""].copy()
    invalidos = rot[~rot.tema_humano.isin(TEMAS) | ~rot.recusa_humano.isin(RECUSAS)]
    if len(invalidos):
        raise SystemExit(f"{len(invalidos)} rótulos fora da lista (ex.: {invalidos.iloc[0].conversa_id})")
    rot["acerto_tema"] = rot.tema_humano == rot.tema_previsto
    rot["acerto_recusa"] = rot.recusa_humano == rot.recusa_prevista
    pred = pd.read_parquet(args.resultado)
    tamanhos = pred[(pred.fonte == "llm") & pred.erro.isna()].tema.value_counts()

    n, k = len(rot), int(rot.acerto_tema.sum())
    lo, hi = wilson(k, n)
    acc, alo, ahi = acuracia_ponderada(rot, tamanhos)
    print(f"rotuladas: {n}")
    print(f"tema — acurácia bruta da amostra: {k / n:.1%} (IC {lo:.1%}–{hi:.1%})")
    print(f"tema — acurácia ponderada pela base: {acc:.1%} (IC {alo:.1%}–{ahi:.1%})  <- número a reportar")
    kr = int(rot.acerto_recusa.sum())
    rlo, rhi = wilson(kr, n)
    print(f"recusa — acurácia: {kr / n:.1%} (IC {rlo:.1%}–{rhi:.1%})")
    print("\nprecisão por tema previsto:")
    print(rot.groupby("tema_previsto").acerto_tema.agg(["mean", "size"]).round(2).to_string())
    print("\nmatriz de confusão (linha = humano, coluna = previsto):")
    print(pd.crosstab(rot.tema_humano, rot.tema_previsto).to_string())
    print("\nrecusa (linha = humano, coluna = previsto):")
    print(pd.crosstab(rot.recusa_humano, rot.recusa_prevista).to_string())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versao", default="v2")
    ap.add_argument("--resultado", type=Path, default=RAIZ / "data" / "enriched" / "temas_v2_qwen3_8b.parquet")
    ap.add_argument("--bruta", type=Path, default=BRUTA)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("amostra")
    a.add_argument("--n", type=int, default=150)
    a.add_argument("--minimo", type=int, default=8)
    a.add_argument("--semente", type=int, default=42)
    v = sub.add_parser("avaliar")
    v.add_argument("--rotulos", type=Path, help="CSV rotulado (padrão: data/work/validacao_{versao}/rotulos.csv)")
    args = ap.parse_args()
    {"amostra": cmd_amostra, "avaliar": cmd_avaliar}[args.cmd](args)


if __name__ == "__main__":
    main()
