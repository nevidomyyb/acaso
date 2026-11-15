"""request_id e log estruturado por requisição (PROJECT §6.4 e §8.1).

Cada requisição gera uma linha JSON em stdout com request_id, rota, parâmetros, status, duração e linhas lidas.
Em produção, o stdout do ECS vai para o CloudWatch Logs, e a meta de p95 < 500 ms sai dessas linhas.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

from flask import Flask, g, request


def iniciar(app: Flask) -> None:
    @app.before_request
    def _inicio() -> None:
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        g.t0 = time.perf_counter()
        g.linhas = 0

    @app.after_request
    def _fim(resp):
        duracao_ms = round((time.perf_counter() - g.t0) * 1000, 1)
        resp.headers["X-Request-ID"] = g.request_id
        resp.headers["Server-Timing"] = f"app;dur={duracao_ms}"
        print(json.dumps({
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "request_id": g.request_id,
            "metodo": request.method,
            "rota": request.path,
            "params": request.args.to_dict(),
            "status": resp.status_code,
            "duracao_ms": duracao_ms,
            "linhas": g.linhas,
            "carga_id": getattr(g, "carga_id", None),
        }, ensure_ascii=False), flush=True)
        return resp
