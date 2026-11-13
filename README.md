# Retenção de um assistente de IA — WildChat-1M (Brasil)

**Pergunta:** o que faz uma pessoa que experimentou o assistente voltar a usá-lo em até 7 dias?

> Em construção. Plano: [PROJECT.md](PROJECT.md). Status e decisões: [CLAUDE.md](CLAUDE.md).

## Como subir

```bash
docker compose up        # (em construção) Postgres + carga + API + dashboard
```

O `.env` é opcional. Ele só guarda credenciais AWS para refazer a classificação de tema e recusa (ADR-004). A classificação já vem pronta em `data/enriched/`. Modelo: [.env.example](.env.example).

## Como refazer a base bruta

O recorte do Brasil já está em `data/raw/wildchat_br.parquet`. Para gerar de novo a partir da base pública:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-analysis.txt
.venv/bin/python etl/download.py --dest data/raw/wildchat-1m        # 3,36 GB, confere SHA-256
.venv/bin/python etl/recorte_brasil.py                              # country = 'Brazil'
```

Fonte: [allenai/WildChat-1M](https://huggingface.co/datasets/allenai/WildChat-1M), licença ODC-BY.

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/METODOLOGIA.md](docs/METODOLOGIA.md) | Como cada número é calculado: definições, sensibilidade, IC, código e testes |
| [docs/METODOLOGIA_LABEL.md](docs/METODOLOGIA_LABEL.md) | A rotulagem de tema e recusa: desenho, execução, validação e limites |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Os 6 serviços AWS, local × produção, custo por mês |
| [docs/adr/](docs/adr/) | Decisões de arquitetura |
| [docs/bdr/](docs/bdr/) | Decisões de negócio e definições |
| [infra/aws/iam/](infra/aws/iam/) | Permissões AWS de menor privilégio |
| [infra/aws/ec2/](infra/aws/ec2/) | EC2 de classificação: criar, acompanhar e destruir |
| [docs/USO_DE_IA.md](docs/USO_DE_IA.md) | Log de uso de IA e horas |
| [docs/DUVIDAS.md](docs/DUVIDAS.md) | Dúvidas enviadas e premissas adotadas |
