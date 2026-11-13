# ADR-004 — Classificação de tema e recusa com LLM aberto numa EC2

**Status:** aceito · 2026-11-12

## Contexto
Tema e recusa da 1ª conversa são fatores candidatos do retorno, e a base não tem esses campos. O enunciado exige que o LLM, se usado, rode na AWS (§2.2). A conta AWS é nova: o Bedrock recusa **todos** os modelos por cota 0, e a cota de GPU é 0 no EC2 e no SageMaker. O `docker compose up` precisa subir sem credenciais.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Bedrock, Claude Haiku 4.5 em batch | Barato (≈ US$ 9); bom em PT-BR; serviço gerenciado | **Indisponível na conta:** cota on-demand 0 em todos os modelos (`Too many tokens per day`) e batch negado (`account is not authorized`). O Support libera só "depois de alguns ciclos de faturamento" |
| B) LLM aberto de 4–8B em CPU, EC2 c7i.4xlarge, llama.cpp | Roda hoje; fica na AWS; saída JSON forçada por gramática | 4–7 s por conversa; modelo menor que o Haiku |
| C) Embeddings + classificador treinado | Rápido e barato | Exige ~300 rótulos manuais antes |
| D) Palavras-chave e regex, sem LLM | Sem custo | Baixa cobertura de tema |
| E) SageMaker ou EC2 com GPU | Minutos em vez de horas | Cota de GPU 0 em todas as famílias; endpoint em CPU exige container próprio |

A opção A foi testada com chamada real em 11 e 12/11, nas duas vias e em 9 modelos. Todas falharam. O detalhe está em [docs/RISCOS.md](../RISCOS.md) (risco 11).

## Decisão
Opção B, com **Qwen3-8B** (Apache 2.0, GGUF Q4_K_M, sem "thinking") e o **prompt v2**. A opção D fica como contingência e como checagem cruzada da recusa (BDR-010).

## Ajuste (2 rodadas, 40 conversas, referência lida pelo Claude)
| Rodada | Tema | Recusa | Recusas falsas | s/conversa |
|---|---|---|---|---|
| Qwen3-4B, prompt v1 | 36/40 | 38/40 | 2 de 4 | 4,0 |
| Qwen3-4B, prompt v2 | 35/40 | 37/40 | 2 de 4 | 4,0 |
| **Qwen3-8B, prompt v2** | 35/40 | 39/40 | 1 de 3 | 6,5 |

No tema, a diferença é de 1 caso (ruído). O 8B erra só em temas ambíguos e dá menos recusas falsas.

## Execução
- Escopo: as **3.361 conversas da 1ª sessão** de cada usuário, e não as 11.621. A análise de retorno usa só a 1ª sessão. Em CPU, a base inteira levaria ~20 h, contra ~6 h.
- Saída JSON forçada pela gramática do llama.cpp, a partir do schema de [etl/classificacao.py](../../etl/classificacao.py). Temperatura 0. As 43 conversas de entrada vazia recebem o rótulo por regra, sem chamar o modelo.
- O campo `confianca` sai quase constante (0,95). Ele não serve como filtro.
- Versões fixadas: llama.cpp `v0.9.0`; repositório, revisão e SHA-256 de cada modelo em [infra/aws/ec2/classificacao.sh](../../infra/aws/ec2/classificacao.sh).
- Acesso só por SSM, sem porta aberta. Trava de custo: a instância se destrói em 10 h.
- Rodada real de 12/11: 3.318 conversas em 5,7 h, 6,2 s cada, 0 erros. Instância viva 6,6 h ≈ **US$ 4,70**, pago com os créditos. Saída: `data/enriched/temas_v2_qwen3_8b.parquet`.
- Código: [etl/classificar_cpu.py](../../etl/classificar_cpu.py) (local) e [etl/llm_runner.py](../../etl/llm_runner.py) (na EC2).

## Consequências
- O modelo menor erra mais. A validação manual de 151 conversas mede a perda: **71,4%** de acerto nos 11 temas e **83,8%** em 7 grupos, contra a meta de 85%. Por isso o fator do modelo usa os 7 grupos (BDR-009). O dashboard mostra a acurácia ao lado do efeito.
- A EDA de temas cobre só a estreia de cada usuário.
- Uma troca de prompt ou de modelo gera nova versão do arquivo e reprocessamento explícito.
- Quando a conta tiver histórico de faturamento, reavalie a opção A: ela dispensa a instância e custa ≈ US$ 4/mês no volume de produção (~41 novos usuários por semana). O mínimo de 100 registros por job de batch exige acumular 3 semanas.
