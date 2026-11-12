# BDR-006 — Período, censura e falhas de coleta

**Status:** aceito · 2026-11-11

## Contexto
A base vai de 09/04/2023 a 29/04/2024. Quem chega na última semana não tem 7 dias observáveis. A base global tem 6 dias com falha de coleta: 13/10/2023 e 18–19/01/2024 com zero conversas; 26/06/2023, 14/10/2023 e 17/01/2024 com menos de 15% do volume normal.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Todo o período; tira do denominador quem não tem 7 dias observáveis ou tem falha de coleta na janela | Taxa sem viés de dado faltante | Coortes perto das falhas ficam menores |
| B) Todo o período, sem exclusões | Mais pessoas | Fim da base e semanas com falha puxam a taxa para baixo |
| C) Só um recorte de N meses | Simples | Descarta dado útil numa base pequena |

## Decisão
Opção A. Falha de coleta = dia com volume **global** abaixo de 15% da mediana. Os feriados ficam em ~20% e não entram.

## Impacto no resultado
- Saem 48 pessoas sem 7 dias observáveis e 87 com falha de coleta na janela. O denominador final tem 2.219 pessoas.
- Taxa total: 28,6% com e sem a exclusão de falhas. O efeito aparece nas coortes de 12–19/06/2023, 02–09/10/2023 e 08–15/01/2024.
- O dashboard marca essas semanas com "coleta incompleta".
- Se a premissa estiver errada (o dia baixo era uso real): perdemos 87 pessoas, sem viés na taxa.
