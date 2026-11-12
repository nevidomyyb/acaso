# ADR-002 — Backend em Flask + flask-smorest

**Status:** aceito · 2026-11-10

## Contexto
A API entrega indicadores pré-calculados ao dashboard. Ela valida parâmetros e documenta os endpoints.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) FastAPI | OpenAPI nativo, async | Menor familiaridade |
| B) Flask + flask-smorest | Familiaridade; validação e OpenAPI via marshmallow; Blueprints | Workers síncronos |
| C) Django REST Framework | Robusto | Pesado para uma API só de leitura |

## Decisão
Opção B. As consultas são leves, então async não traz ganho. A familiaridade reduz o risco de prazo.

## Consequências
- Gunicorn serve a API. O Swagger fica em `/docs`.
- Toda resposta tem `request_id`, `definicao_versao` e `fonte`.
- Se a API passar a fazer chamadas lentas ou externas: reavaliar FastAPI ou Quart.
