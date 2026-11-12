# BDRs — decisões de negócio e definições

Modelo: [_MODELO.md](_MODELO.md). Padrão de escrita: ASD-STE100 adaptado (ver `CLAUDE.md`).
Cada BDR mostra quanto o resultado muda com cada opção.

| BDR | Definição | Status |
|---|---|---|
| [001](BDR-001-usuario.md) | Usuário | aceito |
| [002](BDR-002-sessao.md) | Sessão | aceito |
| [003](BDR-003-primeira-experiencia.md) | Primeira experiência | aceito |
| [004](BDR-004-retorno-7-dias.md) | Retorno em 7 dias | aceito |
| [005](BDR-005-fuso.md) | Fuso e dia | aceito |
| [006](BDR-006-periodo-e-censura.md) | Período e censura | aceito |
| [007](BDR-007-filtro-brasil.md) | Filtro Brasil | aceito |
| [008](BDR-008-o-que-conta-como-uso.md) | O que conta como uso | aceito |
| [009](BDR-009-tema.md) | Tema (7 grupos, 1ª conversa) | aceito |
| [010](BDR-010-recusa.md) | Recusa (total pelo LLM, 1ª conversa) | aceito |

Sensibilidade completa: `analysis/03_definicoes_sensibilidade.ipynb` (executado, com as saídas). Código das definições: `etl/definicoes.py`; testes: `tests/test_definicoes.py`.
