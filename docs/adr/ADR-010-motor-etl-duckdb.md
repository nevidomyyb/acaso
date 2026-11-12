# ADR-010 — Motor de ETL e análise: DuckDB

**Status:** aceito · 2026-11-10

## Contexto
A base bruta tem 837.989 conversas em parquet (3,36 GB), com o texto completo e uma lista de turnos aninhada. A máquina tem ~6 GB de RAM livre. A carga filtra o Brasil, deriva usuário, sessão e retorno, e grava no Postgres.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) pandas | Familiar | Carrega tudo em memória; lógica fora de SQL |
| B) Polars | Rápido; lazy | Lógica em dataframe, não em SQL |
| C) Spark | Escala | Exagero para o volume; complica o compose |
| D) Transformar no Postgres | Um só banco | Importa o texto sensível; lento em varredura |
| E) Polars + Postgres + dbt | Testes e linhagem no dbt | Mais horas de setup; uma etapa a mais |
| F) DuckDB | Lê parquet fora da memória; SQL próximo do Postgres; sem infra | Sem linhagem automática |

## Decisão
Opção F. As definições ficam em SQL, que migra quase direto para os indicadores do Postgres. O risco de prazo é menor que o da opção E.

## Consequências
- Testes de definição em pytest com dados sintéticos substituem os testes do dbt.
- A linhagem fica documentada à mão em `docs/INDICADORES.md`.
- Em produção: Athena sobre o S3 ou o mesmo job DuckDB em ECS Fargate.
- Se o volume crescer (mais países, carga diária): migrar as definições para dbt.
