"""Executor da classificação em CPU (ADR-011). Roda NA EC2, ao lado do llama-server.

Lê o JSONL de entrada ({recordId, body}), envia cada `body` ao endpoint OpenAI-compatível do llama.cpp e grava
uma linha por registro em `saida.jsonl` ({recordId, conteudo, uso, segundos, erro}). É retomável: registros já
presentes na saída são pulados. A cada `--sync-cada` registros, copia a saída para o S3 (`aws s3 cp`).

Só biblioteca padrão: a instância não precisa de pip.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def ler_jsonl(caminho: Path) -> list[dict]:
    """Uma linha por registro, quebrando só em \\n. `str.splitlines()` também quebra em U+2028, que aparece
    dentro do texto de conversas e cortaria o JSON ao meio."""
    return [json.loads(linha) for linha in caminho.read_text().split("\n") if linha.strip()]


def chamar(url: str, body: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def processar(reg: dict, url: str, timeout: int, tentativas: int = 3) -> dict:
    t0 = time.time()
    erro = None
    for i in range(tentativas):
        try:
            r = chamar(url, reg["body"], timeout)
            return {
                "recordId": reg["recordId"],
                "conteudo": r["choices"][0]["message"]["content"],
                "fim": r["choices"][0].get("finish_reason"),
                "uso": r.get("usage", {}),
                "segundos": round(time.time() - t0, 2),
            }
        except Exception as exc:  # o servidor pode estar ocupado; tenta de novo
            erro = f"{type(exc).__name__}: {exc}"[:300]
            time.sleep(2 * (i + 1))
    return {"recordId": reg["recordId"], "erro": erro, "segundos": round(time.time() - t0, 2)}


def sincronizar(saida: Path, destino: str | None) -> None:
    if destino:
        subprocess.run(["aws", "s3", "cp", "--only-show-errors", str(saida), destino], check=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1/chat/completions")
    ap.add_argument("--paralelo", type=int, default=4, help="igual ao --parallel do llama-server")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--s3-saida", help="s3://bucket/prefixo/saida.jsonl")
    ap.add_argument("--sync-cada", type=int, default=100)
    args = ap.parse_args()

    feitos = set()
    if args.saida.exists():
        feitos = {r["recordId"] for r in ler_jsonl(args.saida) if not r.get("erro")}
    pendentes = [r for r in ler_jsonl(args.entrada) if r["recordId"] not in feitos]
    print(f"já feitos: {len(feitos)} | pendentes: {len(pendentes)}", flush=True)

    trava = threading.Lock()
    t0, n = time.time(), 0
    with args.saida.open("a") as f, ThreadPoolExecutor(max_workers=args.paralelo) as pool:
        futuros = [pool.submit(processar, r, args.url, args.timeout) for r in pendentes]
        for fut in as_completed(futuros):
            res = fut.result()
            with trava:
                f.write(json.dumps(res) + "\n")  # ensure_ascii: U+2028 sai escapado, a linha não quebra
                f.flush()
                n += 1
                if n % args.sync_cada == 0:
                    ritmo = (time.time() - t0) / n
                    resto = (len(pendentes) - n) * ritmo / 3600
                    print(f"{n}/{len(pendentes)} | {ritmo:.2f} s/registro | faltam ≈ {resto:.1f} h", flush=True)
                    sincronizar(args.saida, args.s3_saida)
    sincronizar(args.saida, args.s3_saida)
    print(f"fim: {n} registros em {(time.time() - t0) / 60:.1f} min", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
