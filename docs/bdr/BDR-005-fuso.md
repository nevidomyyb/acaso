# BDR-005 — Fuso e dia

**Status:** aceito · 2026-11-11

## Contexto
A base está em UTC. "Dia", "semana" e "horário" precisam fazer sentido para quem usa o assistente no Brasil.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Armazenar UTC; agrupar em `America/Sao_Paulo` | Semana e horário corretos para a maior parte do país | Amazonas e Acre ficam 1–2 h deslocados |
| B) Tudo em UTC | Simples | Segunda-feira começa às 21h de domingo no Brasil; horário do dia errado em 3 h |

## Decisão
Opção A. O Brasil não tem horário de verão desde 2019, então o deslocamento é fixo.

## Impacto no resultado
- A taxa total não muda: a regra de retorno (BDR-004) não usa calendário.
- A coorte semanal muda nas bordas. Exemplo: semana de 20/11/2023, 65 novos em UTC e 61 em São Paulo.
- O fator "horário da 1ª sessão" usa a hora local. Em UTC, ele ficaria 3 h deslocado.
- Se a premissa estiver errada (usuário do Norte): deslocamento de 1–2 h para poucos usuários. Para outros países, o fuso fica em `dim_pais` (ver ARQUITETURA).
