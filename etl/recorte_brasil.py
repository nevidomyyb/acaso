"""Gera o recorte Brasil da base bruta (mesmo schema da WildChat-1M, só um subconjunto de linhas).

Uso:
    python etl/recorte_brasil.py --src data/raw/wildchat-1m --out data/raw/wildchat_br.parquet

Critério (BDR-007): conversa com `country = 'Brazil'`. O campo de topo é o país mais comum dos IPs
da conversa. A carga aplica o mesmo filtro de novo, como defesa.

O recorte mantém o schema original (inclusive o texto), porque é a base bruta que a carga lê.
O texto nunca segue para a base analítica.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import duckdb

FILTRO = "country = 'Brazil'"


def recorte_em_dia(src: Path, out: Path) -> bool:
    """True se o recorte, o volume diário e o manifesto existem, o tamanho confere e a revisão da fonte é a atual."""
    man_out, man_src, volume = out.with_suffix(".manifest.json"), src / "manifest.json", out.with_name(
        "wildchat_volume_diario.parquet")
    if not (out.exists() and man_out.exists() and man_src.exists() and volume.exists()):
        return False
    m = json.loads(man_out.read_text())
    fonte = json.loads(man_src.read_text())
    ok = (m.get("tamanho_bytes") == out.stat().st_size and m.get("criterio") == FILTRO
          and (m.get("fonte") or {}).get("revision") == fonte.get("revision"))
    if ok:
        print(f"recorte em dia ({m['conversas']} conversas, revisão {fonte['revision'][:7]}): nada a refazer")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="data/raw/wildchat-1m", type=Path)
    ap.add_argument("--out", default="data/raw/wildchat_br.parquet", type=Path)
    ap.add_argument("--memory-limit", default="4GB")
    ap.add_argument("--se-necessario", action="store_true",
                    help="pula se o recorte já existe e veio da mesma revisão da base (uso no docker compose)")
    args = ap.parse_args()
    if args.se_necessario and recorte_em_dia(args.src, args.out):
        return 0

    src_glob = str(args.src / "*.parquet")
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{args.memory_limit}'")
    con.execute("SET preserve_insertion_order = false")
    con.execute("SET TimeZone = 'UTC'")  # manifesto em UTC, igual ao armazenamento (BDR-005)

    # Ordenação fixa: o arquivo sai igual a cada execução
    args.out.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY (
            SELECT *
            FROM read_parquet('{src_glob}')
            WHERE {FILTRO}
            ORDER BY timestamp, conversation[1].turn_identifier
        ) TO '{args.out}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 20000)
    """)

    # Volume diário GLOBAL (todos os países): revela dias com falha de coleta, que o Brasil sozinho não mostra
    volume = args.out.with_name("wildchat_volume_diario.parquet")
    con.execute(f"""
        COPY (
            SELECT timestamp::DATE AS dia_utc, count(*) AS conversas
            FROM read_parquet('{src_glob}') GROUP BY 1 ORDER BY 1
        ) TO '{volume}' (FORMAT parquet)
    """)

    conversas, hashed_ips, ts_min, ts_max = con.execute(f"""
        SELECT count(*), count(DISTINCT hashed_ip), min(timestamp)::VARCHAR, max(timestamp)::VARCHAR
        FROM read_parquet('{args.out}')
    """).fetchone()

    src_manifest = args.src / "manifest.json"
    manifest = {
        "gerado_por": "etl/recorte_brasil.py",
        "fonte": json.loads(src_manifest.read_text()) if src_manifest.exists() else None,
        "criterio": FILTRO,
        "conversas": conversas,
        "hashed_ips": hashed_ips,
        "ts_min": ts_min,
        "ts_max": ts_max,
        "tamanho_bytes": args.out.stat().st_size,
        "duracao_s": round(time.time() - t0, 1),
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: v for k, v in manifest.items() if k != "fonte"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
