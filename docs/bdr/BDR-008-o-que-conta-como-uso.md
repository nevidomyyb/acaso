# BDR-008 — O que conta como uso

**Status:** aceito · 2026-11-11

## Contexto
O coletor aceitava mensagens vazias. 76 conversas não têm nenhuma mensagem do usuário, e o assistente respondeu "no vazio". Outras 65 têm só a 1ª mensagem vazia.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Conversa com pelo menos 1 mensagem não vazia do usuário | Tira o ruído do coletor | Perde 76 conversas |
| B) Toda conversa | Mais simples | Conta clique acidental como uso |
| C) Também tirar conversas só de saudação ("oi") | Foca em uso com pedido | Saudação é uma 1ª experiência real; vira um fator, não uma exclusão |

## Decisão
Opção A. A saudação sem pedido entra como tema `saudacao_teste` (BDR-009) e é medida como fator.

## Impacto no resultado
| Opção | Retorno 7d | IC 95% | Δ |
|---|---|---|---|
| A (padrão) | 28,6% | 26,8–30,5% | — |
| B | 28,4% | 26,5–30,3% | −0,2 p.p. |

- Se a premissa estiver errada: efeito desprezível na taxa (−0,2 p.p.).
