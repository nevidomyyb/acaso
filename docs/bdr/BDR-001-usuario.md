# BDR-001 — Usuário

**Status:** aceito · 2026-11-11

## Contexto
A base não tem identificador de usuário. Os sinais disponíveis são `hashed_ip`, user-agent e accept-language. O critério escolhido define quem é "novo" e quem "voltou".

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) `hashed_ip` | Estável no tempo; simples de explicar | Junta pessoas no mesmo IP; separa uma pessoa com IP dinâmico |
| B) `hashed_ip` + user-agent | Separa pessoas num IP compartilhado | Atualização do navegador cria "novo" falso (mecanismo do incidente) |
| C) `hashed_ip` + accept-language | Separa idiomas num mesmo IP | Quase igual a A |
| D) A, sem IPs com > 10 user-agents | Tira IPs compartilhados | Perde dados reais |

## Decisão
Opção A. O IP é o sinal mais estável. O user-agent muda sem que a pessoa mude.

## Impacto no resultado
| Opção | Retorno 7d | IC 95% | Δ |
|---|---|---|---|
| A (padrão) | 28,6% | 26,8–30,5% | — |
| B | 30,8% | 29,1–32,6% | +2,2 p.p. |
| C | 28,6% | 26,9–30,5% | 0,0 p.p. |
| D | 28,5% | 26,7–30,4% | −0,1 p.p. |

- Fonte: `analysis/03_definicoes_sensibilidade.ipynb`.
- Se a premissa estiver errada:
  - **IP compartilhado** junta pessoas e infla o retorno. Há 3 IPs com mais de 10 user-agents (16% das conversas), mas o efeito na taxa é de −0,1 p.p.
  - **IP dinâmico** separa uma pessoa em duas e subestima o retorno. O efeito é de pelo menos 2% dos novos IPs e tende a ser maior no celular (36% das conversas).
- Decisão a escalar ao cliente: login ou ID anônimo persistente no produto.
