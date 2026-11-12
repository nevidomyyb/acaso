# BDR-007 — Filtro Brasil

**Status:** aceito · 2026-11-11

## Contexto
O desafio pede a análise só do Brasil. A base tem dois sinais: o país do IP (`country`) e o idioma da conversa (`language`).

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) `country = 'Brazil'` | Segue a restrição do desafio; regra simples | Base pequena |
| B) `country = 'Brazil'` OU `language = 'Portuguese'` | +1.589 conversas | Inclui outros países lusófonos; foge da restrição |

## Decisão
Opção A. Ela segue a restrição do desafio e não inclui outros países de língua portuguesa.

## Impacto no resultado
- Com A: 11.621 conversas e 2.385 usuários (1,4% da base). Mediana de 41 novos usuários por semana.
- A opção B adicionaria 1.589 conversas de 679 IPs. As maiores origens são Portugal (663), Estados Unidos (143) e Moçambique (96).
- **Atenção:** a base do Brasil é pequena. Os intervalos de confiança semanais ficam largos (cerca de ±14 p.p.). A coorte mensal é a visão principal.
- No Brasil, 2.824 conversas (24%) não estão em português. A opção A mantém essas conversas.
- Se a premissa estiver errada (VPN ou roaming): usuários brasileiros fora do país ficam de fora. O volume medido é pequeno: 34 conversas de 5 IPs com algum turno no Brasil.
