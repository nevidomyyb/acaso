# ADR-001 — Base analítica em PostgreSQL

**Status:** aceito · 2026-11-15 (decidido em 10/11; escrito depois da construção)

## Contexto
O dashboard nunca lê a base bruta: os números passam por uma base analítica desenhada por nós (enunciado §2.2).
A base é pequena (2.354 usuários; ~2.000 linhas por tabela), mas o SQL de cada indicador precisa ficar visível e
auditável. A infraestrutura de produção fica na AWS, e o `docker compose up` sobe tudo localmente.

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) PostgreSQL (RDS em produção) | SQL padrão; views e funções guardam o SQL dos indicadores no banco; papéis com permissão só de leitura; serviço gerenciado barato (~US$ 14/mês, ADR-006) | Um servidor a mais no compose |
| B) Arquivo DuckDB lido pela API | Sem servidor; o mesmo motor da carga (ADR-010) | Escrita da carga concorre com a leitura da API; sem papéis nem permissões; sem serviço gerenciado na AWS |
| C) Athena sobre Parquet no S3 | Sem servidor; paga por consulta | Segundos por consulta, não milissegundos; cobra a cada carregamento de tela |
| D) Redshift Serverless | Escala para muitos países | Caro e desproporcional para 22 MB |

## Decisão
Opção A. O banco guarda o SQL dos indicadores (views + Wilson + regras de amostra e k) e separa escrita (carga) de
leitura (API, papel `acaso_leitura`), com custo baixo na AWS.

## Consequências
- Migrations versionadas com **Alembic** (decisão de 14/11), escritas à mão: as views entram como migrations, e cada
  mudança de indicador fica no histórico.
- A agregação roda no request, sobre a `primeira_experiencia`: ~15 ms na consulta mais pesada (METODOLOGIA §11).
- A carga substitui o conteúdo numa transação (TRUNCATE + COPY): se ela falha, a tela fica com a carga anterior.
- **Se a base crescer** (outros países, dados diários): views materializadas, atualizadas ao fim da carga; depois,
  partição por país. Redshift ou Athena só se o volume passar do que uma instância RDS atende.
