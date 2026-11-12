# BDR-004 — Retorno em 7 dias

**Status:** aceito · 2026-11-11

## Contexto
A pergunta de negócio é "voltou a usar em até 7 dias?". É preciso definir o que conta como voltar e de onde a janela começa.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Nova sessão (BDR-002) até 7 × 24 h após o início da 1ª | Separa voltar de continuar; não depende do calendário | Depende do gap da sessão |
| B) Qualquer atividade > 1 h após o início da 1ª (referência do incidente) | Simples | Uma sessão longa conta como retorno |
| C) Atividade em outro dia do calendário | Fácil de explicar | Quem chega às 23h50 e volta às 00h10 "voltou"; quem chega às 8h e volta às 18h "não voltou" |

## Decisão
Opção A. Ela mede uma visita nova, e não a hora do dia em que a pessoa chegou.

## Impacto no resultado
| Opção | Retorno 7d | IC 95% | Δ |
|---|---|---|---|
| A (padrão) | 28,6% | 26,8–30,5% | — |
| B | 27,0% | 25,2–28,9% | −1,6 p.p. |
| C | 18,9% | 17,3–20,6% | −9,7 p.p. |

- A janela de 7 dias começa no **início** da 1ª sessão, não no fim. Assim todos têm a mesma janela.
- Se a premissa estiver errada (por exemplo, o cliente usa "outro dia"): a taxa cai cerca de 10 p.p., e o ranking dos fatores precisa ser refeito com a nova régua.
