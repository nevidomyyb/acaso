# ADR-011 — Classificação com LLM aberto em CPU numa EC2

**Status:** aceito · 2026-11-12 · substitui o ADR-004 no desafio

## Contexto
A conta AWS é nova. O Bedrock recusa todos os modelos (`Too many tokens per day`, cota 0), e o Support só libera depois de alguns ciclos de faturamento. A cota de GPU é 0 no EC2 e no SageMaker. O enunciado exige que o LLM rode na AWS (§2.2).

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) LLM aberto de 4–8B em CPU, EC2 c7i.4xlarge, llama.cpp | Roda hoje; fica na AWS; mesmo schema do ADR-004 | 4–7 s por conversa; modelo menor que o Haiku |
| B) Embeddings + classificador treinado | Rápido | Exige ~300 rótulos manuais antes |
| C) Palavras-chave + regex | Sem custo; sem LLM | Tema com ruído |
| D) SageMaker | Serviço gerenciado | Sem GPU; endpoint em CPU exige container próprio |

## Decisão
Opção A, com **Qwen3-8B** (Apache 2.0, GGUF Q4_K_M, sem "thinking") e o **prompt v2**. Ela roda hoje e mantém o schema de saída do ADR-004.

## Ajuste (2 rodadas, 40 conversas, referência lida pelo Claude)
| Rodada | Tema | Recusa | Recusas falsas | s/conversa |
|---|---|---|---|---|
| Qwen3-4B, prompt v1 | 36/40 | 38/40 | 2 de 4 | 4,0 |
| Qwen3-4B, prompt v2 | 35/40 | 37/40 | 2 de 4 | 4,0 |
| **Qwen3-8B, prompt v2** | 35/40 | 39/40 | 1 de 3 | 6,5 |

No tema, a diferença é de 1 caso (ruído). O 8B erra só em temas ambíguos e dá menos recusas falsas. A recusa é rara, então cada falso positivo dilui o efeito. A acurácia oficial vem da validação manual, sem estas 40 conversas.

## Execução
- Escopo: as **3.361 conversas da 1ª sessão** de cada usuário (decisão de 12/11), e não as 11.621. A análise de retorno usa só a 1ª sessão.
- Saída JSON forçada pela gramática do llama.cpp, com o schema do ADR-004. Temperatura 0. O prompt v2 = v1 + 2 regras de desempate de tema + 3 casos explícitos de `recusa = nao`.
- O campo `confianca` sai quase constante (0,95). Ele não serve como filtro.
- Versões fixadas: llama.cpp `v0.9.0`; repositório, revisão e SHA-256 de cada modelo em [infra/aws/ec2/classificacao.sh](../../infra/aws/ec2/classificacao.sh).
- Acesso só por SSM, sem porta aberta. Trava de custo: a instância se destrói em 10 h.
- Código: [etl/classificar_cpu.py](../../etl/classificar_cpu.py) e [etl/llm_runner.py](../../etl/llm_runner.py). Infra: [infra/aws/ec2/](../../infra/aws/ec2/).
- Custo: c7i.4xlarge ≈ US$ 0,71/h × 6,6 h ≈ US$ 4,7, pago com os créditos.
- Rodada real (12/11): 3.318 conversas em 5,7 h (6,2 s cada), 0 erros. A instância foi destruída no fim.
- Saída: `data/enriched/temas_v2_qwen3_8b.parquet`.

## Consequências
- O modelo menor erra mais. A validação manual (150 conversas) mede a perda. O dashboard mostra a acurácia ao lado do efeito.
- A EDA de temas cobre só a estreia de cada usuário.
- Em produção, o alvo continua o ADR-004 (Bedrock em batch), quando a conta tiver histórico. Uma troca de modelo gera nova versão do arquivo.
- Se a acurácia ficar abaixo de 70%: o tema sai como fator, e a recusa usa o regex.
