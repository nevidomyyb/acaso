# ADR-006 — Arquitetura AWS em 6 serviços

**Status:** aceito · 2026-11-13

## Contexto
O enunciado exige toda a infraestrutura e todo o custo do dashboard na AWS, com a implantação descrita (§2.2). A
base tem 22 MB e ~2.200 usuários. O público é interno e pequeno. A pessoa que vai operar não é especialista em
AWS, e a entrega tem prazo de 3 dias.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) **6 serviços: S3 + Glue Python Shell + RDS + ECS Fargate + CloudWatch + Parameter Store** | Uma peça por função; agendamento gerenciado sem servidor; o mesmo script roda local e em produção | O runtime do Python Shell fica atrás do Python local; gravar no RDS exige uma Glue Connection na VPC |
| B) Glue ETL (Spark) para as transformações | Escala sem limite prático | Cluster Spark para 22 MB; custo e complexidade sem retorno |
| C) ETL em ECS Fargate agendado, sem Glue | Roda a imagem idêntica à do compose | Mais uma imagem e um agendador (EventBridge) para manter |
| D) Desenho completo: Step Functions, EventBridge, ElastiCache, CloudFront, Secrets Manager | Pronto para crescer | 10 serviços para 1 job e 2 telas; mais superfície do que o problema pede |
| E) Tudo em Lambda | Sem servidor e barato | Limite de 15 min e de 10 GB; empacotar DuckDB e statsmodels dá atrito |

## Decisão
Opção A. O gargalo do projeto é agendamento e observabilidade, não processamento. Por isso o Glue entra no tipo
**Python Shell**, e não Spark.

## Consequências
- O desenho tem uma peça por função, e cada peça se explica em uma frase. Isso é defensável numa entrevista.
- Custo de ordem de grandeza: **≈ US$ 70/mês**, com o Fargate e o ALB como itens maiores. Desligar a tarefa fora
  do horário comercial corta quase metade.
- A carga continua um script Python simples. Trocar o Glue por uma tarefa do Fargate (opção C) depois custa
  pouco, porque nada no código depende do Glue.
- Sem cache externo: as tabelas chegam prontas da carga. Se a medição de p95 pedir, entra um cache em memória
  antes de um serviço novo.
- Step Functions, ElastiCache, CloudFront, Secrets Manager e Multi-AZ ficam de fora até um número justificar:
  volume de dados, número de pessoas na tela ou acordo de disponibilidade.
- Detalhe do desenho, custo e implantação: [../ARQUITETURA.md](../ARQUITETURA.md).
