"""API do dashboard de retenção (ADR-002): Flask + flask-smorest, só leitura da base analítica.

Swagger em /docs; contrato OpenAPI em /openapi.json.
"""

from __future__ import annotations

import os

from flask import Flask
from flask_smorest import Api

from . import banco, observabilidade
from .rotas import blp_fatores, blp_health, blp_kpis, blp_retencao


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        API_TITLE="Retenção do assistente — WildChat-1M (Brasil)",
        API_VERSION="1.0",
        OPENAPI_VERSION="3.0.3",
        OPENAPI_URL_PREFIX="/",
        OPENAPI_JSON_PATH="openapi.json",
        OPENAPI_SWAGGER_UI_PATH="/docs",
        OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/",
        ACASO_DB_URL=os.environ.get("ACASO_DB_URL"),
    )
    app.config.update(config or {})
    app.json.sort_keys = False  # mantém a ordem dos schemas
    banco.iniciar(app)
    observabilidade.iniciar(app)
    api = Api(app)
    for blp in (blp_kpis, blp_retencao, blp_fatores, blp_health):
        api.register_blueprint(blp)
    return app
