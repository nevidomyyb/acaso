"""Baixa a base bruta WildChat-1M (Hugging Face, licença ODC-BY) com verificação de SHA-256.

Uso:
    python etl/download.py --dest data/raw/wildchat-1m

- Lista os arquivos parquet via API do Hugging Face e confere o SHA-256 (LFS oid) de cada um.
- Idempotente: arquivo já baixado com checksum correto é pulado. Se o manifesto local existe e todos os
  arquivos conferem, nem a API é consultada.
- Grava um manifesto (manifest.json) com revisão do dataset, arquivos, tamanhos e checksums,
  que entra na rastreabilidade da carga (meta_carga).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

DATASET = "allenai/WildChat-1M"
API_TREE = f"https://huggingface.co/api/datasets/{DATASET}/tree/main/data"
API_INFO = f"https://huggingface.co/api/datasets/{DATASET}"
RESOLVE = f"https://huggingface.co/datasets/{DATASET}/resolve/{{rev}}/{{path}}"
CHUNK = 8 * 1024 * 1024
USER_AGENT = "acaso-retencao-etl/0.1"


def _get_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, expected_size: int) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as out:
        done = 0
        while chunk := resp.read(CHUNK):
            out.write(chunk)
            done += len(chunk)
    if done != expected_size:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{dest.name}: tamanho {done} != esperado {expected_size}")
    tmp.rename(dest)
    print(f"  baixado {dest.name} ({done / 1e6:.0f} MB em {time.time() - t0:.0f}s)", flush=True)


def conferido_localmente(dest: Path) -> bool:
    """True se o manifesto existe e cada arquivo dele está no disco com tamanho e SHA-256 corretos.

    Assim o `docker compose up` com a base já baixada não depende da rede nem da API do Hugging Face.
    """
    manifesto = dest / "manifest.json"
    if not manifesto.exists():
        return False
    m = json.loads(manifesto.read_text())
    for f in m.get("files", []):
        p = dest / f["name"]
        if not p.exists() or p.stat().st_size != f["size"] or sha256_of(p) != f["sha256"]:
            print(f"  diferente do manifesto: {f['name']}", flush=True)
            return False
    print(f"{m['dataset']} @ {m['revision']}: {len(m['files'])} arquivos conferidos pelo manifesto (sem rede)")
    return bool(m.get("files"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default="data/raw/wildchat-1m", type=Path)
    args = ap.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    if conferido_localmente(args.dest):
        return 0

    info = _get_json(API_INFO)
    rev = info["sha"]
    files = [f for f in _get_json(API_TREE) if f["path"].endswith(".parquet")]
    print(f"{DATASET} @ {rev}: {len(files)} arquivos, {sum(f['size'] for f in files) / 1e9:.2f} GB", flush=True)

    manifest = {"dataset": DATASET, "revision": rev, "last_modified": info.get("lastModified"), "files": []}
    for f in sorted(files, key=lambda x: x["path"]):
        name = Path(f["path"]).name
        expected = f["lfs"]["oid"]
        dest = args.dest / name
        if dest.exists() and dest.stat().st_size == f["size"] and sha256_of(dest) == expected:
            print(f"  ok (já existe) {name}", flush=True)
        else:
            download(RESOLVE.format(rev=rev, path=f["path"]), dest, f["size"])
            got = sha256_of(dest)
            if got != expected:
                dest.unlink()
                raise RuntimeError(f"{name}: sha256 {got} != {expected}")
        manifest["files"].append({"name": name, "size": f["size"], "sha256": expected})

    (args.dest / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("download concluído e verificado", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
