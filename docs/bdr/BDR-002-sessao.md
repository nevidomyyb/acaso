# BDR-002 — Sessão

**Status:** aceito · 2026-11-11

## Contexto
Retorno exige separar "voltou" de "continuou". Os turnos do usuário não têm horário; só as respostas do assistente têm. 546 conversas duram mais de 1 hora, e a mais longa dura 11 dias: a pessoa deixa a aba aberta e continua outro dia.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Atividade = cada resposta; nova sessão após 30 min sem atividade | Conta quem continua uma conversa antiga | Depende do gap escolhido |
| B) Atividade = só início e fim de cada conversa | Mais simples | Ignora a volta dentro de uma conversa aberta |
| C) Gap de 15 min | — | Corta pausas curtas em sessões novas |
| D) Gap de 60 min | — | Junta visitas diferentes no mesmo período |

## Decisão
Opção A. A distribuição dos intervalos não tem um vale natural entre 15 e 60 minutos (`analysis/01_discovery.ipynb`, seção 8). Por isso o gap segue a convenção de 30 minutos das ferramentas de web analytics.

## Impacto no resultado
| Opção | Retorno 7d | IC 95% | Δ |
|---|---|---|---|
| A (padrão) | 28,6% | 26,8–30,5% | — |
| B | 24,3% | 22,6–26,1% | −4,3 p.p. |
| C | 34,0% | 32,0–36,0% | +5,4 p.p. |
| D | 25,1% | 23,4–27,0% | −3,5 p.p. |

- O gap é a escolha que mais pesa entre as definições técnicas. O dashboard mostra a definição ao lado do número.
- Se a premissa estiver errada: o nível da taxa muda, mas a comparação entre grupos (fatores) usa a mesma régua.
