# Uso de IA

Log de cada sessão. No fim, o parágrafo pedido no desafio.

## Log

| Data | Ferramenta | Para quê | O que conferi, corrigi ou descartei | Horas (pessoa) |
|---|---|---|---|---|
| 10/11 | Claude (chat) | Plano (PROJECT.md): critérios, definições, cronograma, custo do Bedrock | Revisei o plano. As decisões de stack são minhas. | _preencher_ |
| 10/11 | Claude Code | Estrutura do repo, download com SHA-256, memória do projeto, recorte Brasil, contagens | SHA-256 dos 14 parquets = hash do Hugging Face. Corrigi a sintaxe de lambda do DuckDB 2.0. Conferi o schema no dataset card e por consulta. | _preencher_ |
| 11/11 | Claude Code | Políticas IAM, `.env`, padrão de escrita, ADRs reescritos, BDR-007 | Conferi as políticas na documentação da AWS (batch-iam-sr, batch-inference-permissions). Conferi o mínimo de 100 registros por job no Service Quotas. Conferi os números do BDR-007 por consulta. | _preencher_ |
| 11/11 | Claude Code | Classificador Bedrock (prompt v1, regex de recusa), módulo de definições, 10 testes, notebooks 01 e 03, BDR-001 a 006 e 008, ADR-003 (proposta), RISCOS | Taxonomia desenhada a partir das mensagens mais frequentes, não da memória do modelo. Corrigi: limiar de falha de coleta (25% marcava feriados; passou a 15%); números do texto sincronizados com a execução final; rótulos sobrepostos nos gráficos. Conferi duas premissas por consulta antes de codificar (timestamp de topo = máximo dos turnos; nenhum turno fora de ordem). Teste do Bedrock parou no formulário de caso de uso da conta. | _preencher_ |

## Como a IA é conferida
- Leio todo SQL gerado antes do commit. Refaço os números da análise por uma consulta independente.
- Classificação no Bedrock: valido em 150 conversas rotuladas à mão. Meta: acurácia ≥ 85%. O regex de recusa roda junto como checagem cruzada.
- Fatos sobre a base vêm do dataset card e de consultas na base, não da memória do modelo.

## Parágrafo final
_(escrever no Dia 7: ferramentas, para quê, o que conferi, corrigi ou descartei, total de horas)_
