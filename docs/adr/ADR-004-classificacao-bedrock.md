# ADR-004 — Classificação de tema e recusa com Bedrock em batch

**Status:** aceito · 2026-11-11

## Contexto
Tema e recusa da 1ª conversa são fatores candidatos do retorno. A base não tem esses campos. O LLM precisa ficar na AWS. O `docker compose up` precisa subir sem credenciais.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Bedrock Haiku 4.5, batch, resultado versionado | Barato; bom em PT-BR; reprodutível | Job assíncrono; mínimo de 100 registros |
| B) Bedrock em tempo real na tela | Sempre atual | Credencial na tela; custo por acesso; latência |
| C) Palavras-chave e regex | Sem custo | Baixa cobertura de tema |
| D) Amazon Nova Lite/Micro | 15–30× mais barato | Acurácia em PT-BR a medir |

## Decisão
Opção A. O resultado fica em `data/enriched/temas_v{N}.parquet`, e a carga lê esse arquivo. A opção C fica como contingência e como checagem cruzada da recusa.

## Execução
- Entrada: 1ª mensagem do usuário (até 2.000 caracteres) + 1ª resposta (até 1.500 caracteres). Saída: ferramenta forçada com `{motivo, tema, recusa (nao/parcial/total), confianca}`. Temperatura 0. Prompt em `etl/prompts/classificacao_v1.md`.
- Ajuste do prompt: on-demand, amostra de 200. Base inteira: batch.
- Modelo: inference profile `us.anthropic.claude-haiku-4-5-20251001-v1:0`. O batch do Haiku 4.5 não aceita o ID direto do modelo.
- Chave de idempotência: `conversa_id + versao_prompt + modelo`.
- Cliente: boto3 (`invoke_model` e `create_model_invocation_job`). O batch exige o corpo bruto do InvokeModel; usar o mesmo corpo no on-demand garante que o prompt testado é o que roda. O SDK Anthropic atual envia uma versão de API que o Bedrock só aceita do Claude 4.7 em diante.
- Entrada vazia (65 conversas): `saudacao_teste` por regra, sem chamar o LLM.
- Validação: 150 conversas rotuladas à mão. Meta: acurácia ≥ 85%. Máximo de 2 rodadas de ajuste.

## Custo
- Escopo: **todas** as 11.621 conversas do Brasil (decisão de 11/11), para a EDA de temas e para os fatores. Custo estimado: ≈ US$ 9 em batch.
- AWS Budgets fica ativo antes da primeira chamada.
- Permissões: [infra/aws/iam/](../../infra/aws/iam/).

## Consequências
- Erro de classificação vira ruído no efeito do tema. O dashboard mostra a acurácia junto do efeito.
- Mudança de prompt ou modelo gera nova versão do arquivo e reprocessamento explícito.
- Em produção, o Brasil tem ~41 novos usuários por semana, abaixo do mínimo de 100 por job. Acumule 3 semanas por job ou use on-demand no incremental.
