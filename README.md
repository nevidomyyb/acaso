# Retenção de um assistente de IA — WildChat-1M (Brasil)

**Pergunta:** o que faz uma pessoa que experimentou o assistente voltar a usá-lo em até 7 dias?

> Plano: [PROJECT.md](PROJECT.md). Status e decisões: [CLAUDE.md](CLAUDE.md).

## Como subir

Requisito: Docker com Compose v2 e cerca de 4 GB de memória para os containers. Clone o repositório numa pasta
que o Docker compartilha com os containers: Colima e Docker Desktop compartilham a pasta pessoal (`/Users/...`)
por padrão, mas não `/tmp`. Fora dela, o volume `./data` aparece vazio, e a etapa `classificacao` para com
"falta a classificação".

```bash
docker compose up            # ou: docker-compose up
```

| Endereço | O que é |
|---|---|
| http://localhost:8501 | Dashboard (2 telas) |
| http://localhost:8000/docs | API: Swagger (OpenAPI em `/openapi.json`) |
| `localhost:5433` | Postgres da base analítica (só na máquina local) |

O 1º `up` baixa a base pública (3,36 GB, com SHA-256 conferido) e leva alguns minutos. Os seguintes reaproveitam
`./data` e não usam a rede. Não precisa de `.env` nem de credenciais AWS.

| Ordem | Serviço | O que faz | Termina? |
|---|---|---|---|
| 1 | `bruta` | Baixa a WildChat-1M e gera o recorte Brasil (`data/raw/`). Pula o que já confere | sim |
| 2 | `classificacao` | Confere o tema e a recusa em `data/enriched/`. Se o arquivo faltar, refaz na EC2 (veja abaixo) | sim |
| 3 | `carga` | Aplica as migrations (Alembic) e popula a base analítica **a partir da base bruta** | sim |
| 4 | `postgres` | Base analítica: 3 tabelas + views dos indicadores | não |
| 5 | `api` | Flask + flask-smorest, papel só de leitura no banco | não |
| 6 | `dashboard` | Streamlit; só fala com a API | não |

**O que o dashboard mostra:** contagens, taxas, IC e efeitos agregados. **Nunca mostra:** texto das conversas,
IP, navegador, identificador de pessoa ou grupo com menos de 20 pessoas. A base analítica não guarda nenhum
desses dados.

## Testes

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-analysis.txt
.venv/bin/python -m pytest -q                       # sem banco: os testes de banco são pulados
docker compose up -d postgres                       # com banco: carga real, API e regras dos indicadores
ACASO_DB_URL_TESTE=postgresql://acaso:acaso_local@localhost:5433/acaso .venv/bin/python -m pytest -q
```

## Credenciais AWS (opcional)

Se `data/enriched/temas_v2_qwen3_8b.parquet` existe, o compose não usa a AWS. Se o arquivo não existe, o compose
cria a EC2 de classificação, roda o Qwen3-8B (≈ 6 h, ≈ US$ 5) e apaga a EC2 no fim. Para isso, ele precisa de um
usuário IAM com menor privilégio:

| Item | Valor |
|---|---|
| Usuário | `acaso-operador`, sem acesso ao console |
| Política anexada | `acaso-operador` (gerenciada): [infra/aws/iam/usuario-acaso-operador.json](infra/aws/iam/usuario-acaso-operador.json) |
| Limite das roles que ele cria | `acaso-limite`: [infra/aws/iam/limite-acaso.json](infra/aws/iam/limite-acaso.json) |
| Região | `us-east-1` |
| Bucket | um bucket S3 do projeto, com acesso público bloqueado |

Preencha no `.env`: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION=us-east-1` e
`ACASO_S3_BUCKET`. O passo a passo da criação, e o que o usuário pode e não pode fazer, estão em
[infra/aws/iam/README.md](infra/aws/iam/README.md).

## Como refazer a base bruta

O compose faz isso sozinho (serviço `bruta`). Para gerar fora do Docker:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-analysis.txt
.venv/bin/python etl/download.py --dest data/raw/wildchat-1m        # 3,36 GB, confere SHA-256
.venv/bin/python etl/recorte_brasil.py                              # country = 'Brazil'
```

Fonte: [allenai/WildChat-1M](https://huggingface.co/datasets/allenai/WildChat-1M), licença ODC-BY.

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/METODOLOGIA.md](docs/METODOLOGIA.md) | Como cada número é calculado: definições, sensibilidade, IC, código e testes; §11 = indicadores e SQL |
| [docs/METODOLOGIA_LABEL.md](docs/METODOLOGIA_LABEL.md) | A rotulagem de tema e recusa: desenho, execução, validação e limites |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Os 6 serviços AWS, local × produção, custo por mês |
| [docs/adr/](docs/adr/) | Decisões de arquitetura |
| [docs/bdr/](docs/bdr/) | Decisões de negócio e definições |
| [infra/aws/iam/](infra/aws/iam/) | Permissões AWS de menor privilégio |
| [infra/aws/ec2/](infra/aws/ec2/) | EC2 de classificação: criar, acompanhar e destruir |
| [docs/USO_DE_IA.md](docs/USO_DE_IA.md) | Log de uso de IA e horas |
| [docs/DUVIDAS.md](docs/DUVIDAS.md) | Dúvidas enviadas e premissas adotadas |
