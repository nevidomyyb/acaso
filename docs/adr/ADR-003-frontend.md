# ADR-003 — Frontend do dashboard

**Status:** aceito · 2026-11-11

## Contexto
O dashboard é lido por pessoas de negócio. Cada número precisa de definição, fonte e IC, com tooltip e aviso de amostra pequena. O backend é uma API Flask (ADR-002). O front só lê a API.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Next.js + Recharts | Cara de produto; stack da implementação de referência do desafio | SSR e rotas de API sem uso aqui; mais horas de construção |
| B) Streamlit consumindo a API, com tema próprio | Mais rápido de construir; tudo em Python; o tema dá identidade visual | Menos controle de layout; um servidor Python a mais |
| C) Vite + React + TypeScript + Recharts (SPA estática) | Cara de produto; arquivos estáticos | Exige escrever os componentes |

## Decisão
Opção B. O prazo é curto e a equipe trabalha em Python. Um tema próprio (`.streamlit/config.toml` + CSS) evita a cara de notebook.

## Consequências
- O Streamlit lê **só a API** (HTTP), nunca o banco. A separação front × backend fica igual à das outras opções.
- Gráficos em Altair (Vega-Lite): faixa de IC, barras de erro e tooltip. A paleta segue a da análise (validada para daltonismo).
- No compose: um container `frontend` (Streamlit). Na AWS: ECS Fargate atrás do ALB, junto da API.
- i18n por dicionário de textos (pré-requisito para outros países).
- Se o cliente pedir um produto mais customizado: migrar para a opção C reaproveitando a API sem mudança.
