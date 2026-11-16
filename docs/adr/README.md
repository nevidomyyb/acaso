# ADRs — decisões de arquitetura

Modelo: [_MODELO.md](_MODELO.md). Padrão de escrita: ASD-STE100 adaptado (ver `CLAUDE.md`).

| ADR | Decisão | Status |
|---|---|---|
| [001](ADR-001-base-analitica-postgres.md) | Base analítica em PostgreSQL (RDS em produção), migrations com Alembic | aceito |
| [002](ADR-002-backend-flask-smorest.md) | Backend em Flask + flask-smorest | aceito |
| [003](ADR-003-frontend.md) | Frontend: Streamlit com tema próprio, lendo só a API | aceito |
| [004](ADR-004-classificacao-llm-aberto-ec2.md) | Classificação de tema e recusa com LLM aberto numa EC2 | aceito |
| 005 | Pré-cálculo na carga, sem cache externo | decidido em `PROJECT.md` §6.4; não vira ADR |
| [006](ADR-006-arquitetura-aws.md) | Arquitetura AWS em 6 serviços (Glue Python Shell, não Spark) | aceito |
| [007](ADR-007-privacidade.md) | Privacidade: o que o dashboard mostra e nunca mostra; k-anonimato (k = 20) | aceito |
| 008 | Método estatístico: regressão linear (bruto × ajustado), mês e estado como controles | decidido em `docs/METODOLOGIA.md` §5; não vira ADR |
| 009 | Reconciliação automática + tela de Saúde | **cortado em 13/11** (PROJECT.md §14); fica como proposta no relatório |
| [010](ADR-010-motor-etl-duckdb.md) | Motor de ETL e análise: DuckDB | aceito |
