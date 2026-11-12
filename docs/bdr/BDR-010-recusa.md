# BDR-010 — Recusa na 1ª experiência

**Status:** aceito · 2026-11-12

## Contexto
Uma recusa na estreia pode afastar a pessoa. O LLM marca a recusa em 3 níveis (`nao`, `parcial`, `total`), e um regex PT/EN roda junto como checagem (ADR-011). Na validação manual de 151 conversas, a pessoa marca 16 recusas: 5 totais e 11 parciais. Os dois detectores quase nunca acham a recusa parcial.

## Opções
| Opção | Marcadas que são recusa | Totais achadas | Usuários com recusa | Retorno 7d com × sem (bruto) |
|---|---|---|---|---|
| A) LLM `total`, 1ª conversa | 8 de 9 | 5 de 5 | 106 (4,8%) | 15,1% × 29,3% |
| B) LLM `parcial` ou `total`, 1ª conversa | 9 de 13 | 5 de 5 | 133 (6,0%) | 14,3% × 29,5% |
| C) Regex, 1ª conversa | 8 de 9 | 4 de 5 | 103 (4,6%) | 15,5% × 29,3% |
| D) LLM `total`, qualquer conversa da 1ª sessão | — | — | 133 (6,0%) | 21,1% × 29,1% |

## Decisão
Opção A: o fator é "recebeu recusa total na 1ª conversa da 1ª sessão", pelo LLM. O regex (C) e a sessão inteira (D) entram como sensibilidade.

## Impacto no resultado
- O LLM e o regex dão quase o mesmo retorno no grupo com recusa (15,1% e 15,5%). O fator não depende do detector.
- A opção D mistura engajamento: quem abre mais conversas tem mais chance de levar recusa e volta mais. Os 27 usuários com recusa só numa conversa posterior voltam 44%.
- A diferença bruta (−14 p.p.) não é efeito causal. O notebook 04 ajusta por tema, modelo e outros fatores.
- A recusa parcial fica fora: os dois detectores perdem 7 de 11. O efeito de "qualquer recusa" fica subestimado.
- Se a premissa estiver errada: a precisão sai de só 9 casos (8 de 9, IC 57–98%). Se ela for menor, o grupo com recusa tem pessoas sem recusa, e a diferença encolhe.
- Código: `RECUSA_FATOR` em `etl/definicoes.py`. Regex: `etl/recusa_regex.py`.
