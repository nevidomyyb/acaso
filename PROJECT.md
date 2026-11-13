# Plano — Desafio Técnico Acaso
## Análise e Dashboard de Retenção de um Assistente de IA (WildChat-1M, Brasil)

> **Prazo de entrega:** segunda **16/11/2026, 23h59** → nathalia.anjos@aca.so e daniele.cardoso@aca.so
> **Prazo para dúvidas:** **quarta 11/11** (mesmos e-mails). Sem resposta a tempo → registrar a premissa e seguir.
> **Dedicação esperada pelo desafio:** ~12h. Este plano prevê ~20h. Escopo reduzido em 13/11 (§14).
> **Depois:** conversa de 60 min com o gestor = 20 min de apresentação + 40 min de entrevista técnica (fluxo de construção, decisões registradas, o que faria diferente).

---

## 0. Pergunta de negócio (nunca perder de vista)

> **O que faz uma pessoa que experimentou o assistente voltar a usá-lo em até 7 dias?**
> Quais fatores têm maior efeito no retorno, **quanto pesa cada um** (com incerteza) e **quanto é causa vs. seleção** (perfil de quem usa)?

- Cliente: empresa dona do assistente, **pessoas de negócio, sem perfil técnico**.
- Resultado chega por **dashboard**, não por notebook. **Cada tela se explica sozinha**: cada número com **definição e fonte**, cada efeito com sua **incerteza**.
- A pessoa da vaga **responde pelos números que o dashboard mostra**.

---

## 1. Critérios de avaliação → onde cada um é atendido

| Critério | O que observam | Onde atendemos |
|---|---|---|
| Análise | Efeitos com incerteza; confusão causa × seleção tratada; explicação do movimento semanal | §5.3, §5.4, §5.5 |
| Discovery e EDA | Padrões e problemas relevantes; definições defensáveis; sugestões saem dos dados | §4, §5.1, §5.2, §5.6 |
| Investigação e sustentação | Seguir o dado até a origem; achar a causa no código; correção que evita recorrência | §8, §9 |
| Dashboard | Não técnico entende sozinho; efeito com incerteza e fonte | §6 |
| Construção e código | Sobe do zero; dados reais; código legível e testado; decisões registradas | §3, §7, §8.3, §10 |
| Clareza e premissas | Documento objetivo; premissas, riscos e escalonamentos explícitos | §4, §11, `docs/RELATORIO.md` |
| Apresentação | Explicar em 20 min e defender escolhas | §16 |
| Uso de IA | IA com critério e conferida | §12 |

---

## 2. Restrições obrigatórias (checklist de "eliminação")

- [ ] `docker compose up` sobe **tudo do zero** (base analítica + carga + backend + frontend).
- [ ] A carga **popula a base analítica a partir da base bruta**.
- [ ] O dashboard **nunca lê a base bruta** — só a base analítica.
- [ ] **Pelo menos 2 telas com dados reais**.
- [ ] Análise somente sobre `country = 'Brazil'` (premissa registrada sobre como aplicar o filtro).
- [ ] **Toda infra e custo do dashboard na AWS**, inclusive o LLM se usado. Para a entrega roda local; **descrever a implantação**.
- [ ] Declarar **o que o dashboard mostra e o que nunca mostra** (dados pessoais).
- [ ] Repositório com instruções + **ADRs e BDRs** (contexto, opções, escolha).
- [ ] Cada premissa registrada **+ o que muda no resultado se estiver errada**.
- [ ] Documento curto com achados e decisões (não um documento longo).
- [ ] Parágrafo final de **uso de IA**: ferramentas, para quê, o que conferiu/corrigiu/descartou, **horas dedicadas**.

---

## 3. Stack e arquitetura

### 3.1 Stack proposta

| Camada | Escolha | Justificativa (vira ADR) |
|---|---|---|
| Base bruta (local) | Parquet do WildChat-1M filtrado para Brasil em `data/raw/` | Reprodutível; em produção = S3 |
| Discovery/análise | Python, DuckDB, pandas, statsmodels, scikit-learn, notebooks | DuckDB lê parquet direto, roda fora da memória e usa SQL próximo do Postgres (ADR-010); statsmodels dá IC pronto |
| Base analítica | PostgreSQL 16 | Domínio; SQL dos indicadores fica explícito; em produção = RDS/Aurora |
| Carga (ETL) | Container Python `etl` que roda e termina no `compose up` | "Carregar a partir da bruta" fica literal |
| Classificação de tema/recusa | **LLM aberto (Qwen3-8B) em CPU numa EC2** com llama.cpp (ADR-004), **pré-calculada** e versionada em `data/enriched/` | Fica na AWS, como o enunciado exige; a conta nova não tem cota no Bedrock nem GPU; o dashboard não depende de LLM em tempo real; o `compose up` roda sem credenciais; custo ≈ US$ 5 para as 3.361 conversas da 1ª sessão |
| Backend | **Flask + flask-smorest** (schemas marshmallow), servido por gunicorn | Familiaridade com Flask; smorest valida entrada/saída pelos schemas e gera OpenAPI/Swagger automaticamente; Blueprints organizam os endpoints (ADR-002) |
| Frontend | **Streamlit com tema próprio, consumindo a API** (ADR-003 aceito em 11/11) | Trade-off tempo × percepção de produto |
| Testes | pytest (ETL, SQL dos indicadores) + test client do Flask (API) | Indicador não muda sem ninguém perceber |
| Deploy (descrito) | **6 serviços:** S3 → carga em **AWS Glue Python Shell** (agendada) → **RDS PostgreSQL** → API e dashboard em **ECS Fargate** atrás de um ALB · **CloudWatch Logs** · **SSM Parameter Store**. Desenho completo em [docs/ARQUITETURA.md](docs/ARQUITETURA.md) (ADR-006) | Tudo AWS. Glue Python Shell, e não Spark: a base é de 22 MB, e o gargalo é agendamento, não processamento |

### 3.2 Estrutura do repositório

Estado em 12/11. **(D5)** = previsto para o Dia 5 do cronograma (§13), e assim por diante.

```
acaso/
├── README.md                   # como subir, como refazer a base bruta, índice dos documentos
├── PROJECT.md                  # este plano
├── CLAUDE.md                   # memória do projeto: decisões aceitas, fatos dos dados, status
├── requirements-analysis.txt   # dependências da análise, com versão fixada
├── ruff.toml · pytest.ini      # lint (linha de 120) e testes
├── .env.example                # modelo do .env: credenciais AWS e bucket do projeto
├── docker-compose.yml          # (D5) Postgres + carga + API + dashboard
│
├── data/
│   ├── raw/
│   │   ├── wildchat-1m/        # base pública completa, 3,36 GB (fora do git)
│   │   ├── wildchat_br.parquet # recorte Brasil, 22 MB (+ manifesto): a base bruta que a carga lê
│   │   └── wildchat_volume_diario.parquet   # volume diário global → detecta falha de coleta
│   ├── enriched/               # tema e recusa classificados pelo LLM, versionados no git
│   └── work/                   # intermediários, entrada/saída da EC2 e rótulos manuais (fora do git)
│
├── etl/
│   ├── download.py             # baixa a WildChat-1M e confere o SHA-256 de cada parquet
│   ├── recorte_brasil.py       # gera o recorte Brasil e o volume diário global
│   ├── definicoes.py           # FONTE ÚNICA das definições (BDR-001 a 008):
│   │                           #   conversas → eventos → sessões → usuários; `elegiveis()` = denominador
│   ├── estatistica.py          # intervalo de confiança de Wilson
│   ├── recusa_regex.py         # detecta recusa por regex PT/EN: checagem cruzada e contingência
│   ├── classificacao.py        # taxonomia, entrada, schema e validação da classificação (ADR-004)
│   ├── classificar_cpu.py      # prepara, envia e coleta a classificação da EC2 (local)
│   ├── llm_runner.py           # executor que roda NA EC2: chama o llama-server, retomável
│   ├── validacao_classificacao.py # amostra de rótulo manual e acurácia ponderada
│   ├── prompts/
│   │   ├── classificacao_v1.md # prompt de classificação, versionado
│   │   └── classificacao_v2.md # v1 + 2 regras de desempate e 3 casos de `recusa = nao`
│   ├── primeira_experiencia.py # (D3) features da 1ª sessão, 1 linha por usuário
│   └── carga.py                # (D5) popula o Postgres a partir da base bruta (idempotente)
│
├── analysis/                   # fonte em .py (jupytext, formato percent); o .ipynb é gerado
│   ├── estilo.py               # paleta dos gráficos e rodapé com a fonte de cada número
│   ├── 00_contagens_iniciais.py        # script: contagens do recorte e teste do incidente
│   ├── 01_discovery.py                 # qualidade dos dados: 10 problemas e tratamento (§5.1)
│   ├── 03_definicoes_sensibilidade.py  # taxa padrão, funil e sensibilidade das definições (§4)
│   ├── 02_eda.py                       # (D3) padrões da 1ª experiência (§5.2)
│   └── 04_efeitos_e_confusao.py        # (D4) logística, efeito marginal, IPW e mês atípico (§5.3 a §5.5)
│
├── tests/
│   ├── conftest.py             # base sintética em memória, com retorno conhecido
│   ├── test_definicoes.py      # testes das definições (pega mudança silenciosa)
│   ├── test_classificar_cpu.py # seleção, prompt, schema e leitura da saída do modelo
│   ├── test_recusa_regex.py    # recusas e não recusas conhecidas
│   └── test_validacao.py       # alocação estratificada e acurácia ponderada
│
├── infra/aws/iam/              # políticas de menor privilégio (S3)
├── infra/aws/ec2/              # cria, acompanha e destrói a EC2 de classificação (acesso só por SSM)
│
├── db/                         # (D5) migrations do schema + SQL de cada indicador
├── backend/                    # (D5) Flask + flask-smorest: resources, schemas, queries, observabilidade
├── frontend/                   # (D5) Streamlit com tema próprio, lendo só a API
│
└── docs/
    ├── desafio/enunciado.txt   # texto do enunciado, para busca
    ├── adr/                    # ADR-002, 003, 004, 010 (+ modelo e índice)
    ├── bdr/                    # BDR-001 a 008 (+ modelo e índice)
    ├── DUVIDAS.md              # dúvidas e a premissa de cada uma
    ├── RISCOS.md               # riscos e decisões a escalar (§11)
    ├── USO_DE_IA.md            # log contínuo e parágrafo final (§12)
    ├── METODOLOGIA.md          # origem de cada número + indicadores do dashboard (§6.2)
    ├── METODOLOGIA_LABEL.md    # a rotulagem de tema e recusa
    ├── ARQUITETURA.md          # 6 serviços AWS, local × produção, custo
    ├── RELATORIO.md            # (D6) documento curto: achados e decisões
    └── INCIDENTE.md            # (D6) resposta da §4.2 + o que registrar em cada camada
```

### 3.3 Modelo da base analítica (rascunho)

- `dim_usuario` — `usuario_id`, `definicao_versao`, `primeira_vez_utc`, `estado_agrupado` (menos de 20 usuários → "outros"), `idioma_3_niveis` (PT, EN, outro), `dispositivo` (mobile ou desktop, derivado do UA).
- `fato_conversa` — `conversa_id`, `usuario_id`, `inicio_utc`, `fim_utc`, `modelo`, `turnos`, `idioma`, `tema`, `recusa`, `tam_resposta_media`, `redacted`, `sessao_id`. Sem `toxic`: a base pública removeu as conversas tóxicas, e o campo é 0 em todo o Brasil.
- `fato_sessao` — `sessao_id`, `usuario_id`, `inicio`, `fim`, `n_conversas`.
- `primeira_experiencia` — 1 linha por usuário com **todas as features** da 1ª sessão + `voltou_7d` + `observavel_7d` (censura).
- `agg_coorte` — pré-calculada (granularidade `mes` ou `semana`, perfil, novos, voltaram, taxa, IC, `amostra_suficiente`). A visão principal é **mensal**, porque o IC semanal é de ±15 p.p. (decisão de 11/11).
- `resultado_efeitos` — fator, nível, efeito, IC inferior/superior, método, n, versão do modelo.
- `meta_carga` — execução, linhas lidas/gravadas/rejeitadas, checksum, duração, versão das definições.

**Nada de texto das conversas, `hashed_ip` ou user-agent completo na base que o dashboard lê.** Todo recorte exibido respeita k-anonimato, com k = 20.

---

## 4. Definições e premissas (viram BDRs)

Para cada uma: escolha principal + alternativas testadas + **quanto a taxa de retorno muda** (tabela de sensibilidade).

| # | Definição | Escolha inicial | Alternativas na sensibilidade | Risco se errada |
|---|---|---|---|---|
| BDR-001 | **Usuário** | `hashed_ip` (**aceito**) | `hashed_ip + user-agent` (+2,2 p.p.); `hashed_ip + accept-language` (−0,1) | IP compartilhado (empresa, faculdade) junta pessoas → infla o retorno; IP dinâmico separa uma pessoa → reduz o retorno; o UA muda em atualização de navegador → "novos" falsos (**é o incidente!**) |
| BDR-002 | **Sessão** | atividade = **cada resposta do assistente**; gap de 30 min (**aceito**) | gap de 15 min (+5,4 p.p.); gap de 60 min (−3,5); atividade por conversa (−4,3) | Muda o que conta como "voltar" |
| BDR-003 | **Primeira experiência** | 1ª sessão do usuário na base, **sem aquecimento** (**aceito**: a base começa em 09/04/2023) | aquecimento de 2 semanas (−0,4 p.p.); de 4 semanas (−0,8) | Usuário antigo tratado como novo |
| BDR-004 | **Retorno em 7 dias** | nova sessão até 7×24h depois do início da 1ª (**aceito**) | retorno só depois de 1h (−1,6 p.p.); dia-calendário seguinte (−9,7) | A taxa muda até 9,7 p.p.; justificar |
| BDR-005 | **Fuso / dia** | agrupa em `America/Sao_Paulo`; armazena tudo em UTC (**aceito**) | UTC (≤ 0,2 p.p.) | Coortes deslocadas |
| BDR-006 | **Período** | todo o período; tira 48 censurados e 87 usuários com falha de coleta na janela (**aceito**; falha = volume global < 15% da mediana) | manter os censurados; limiar de 25% (marca feriados como falha) | Taxa baixa no fim da base; coortes vizinhas subestimadas |
| BDR-007 | **Filtro Brasil** | conversa com `country='Brazil'` (**aceito**) | `OR language='Portuguese'` (rejeitada: traz outros países lusófonos) | VPN e roaming; base pequena |
| BDR-008 | **O que conta como uso** | conversa com ≥ 1 mensagem não vazia (**aceito**; 76 conversas saem) | manter as vazias (≤ 0,2 p.p.) | Ruído de "testes" |
| BDR-009 | **Tema** | 11 temas do prompt v2 agrupados em **7 grupos**; tema da 1ª conversa da 1ª sessão (aceito 12/11; acerto 83,8%) | 11 temas (71,4%) | Tema ambíguo |
| BDR-010 | **Recusa** | recusa **total** pelo LLM na 1ª conversa (aceito 12/11; 8 de 9 corretas) | regex; sessão inteira | Subestimar as recusas parciais |

**Resultado com as definições aceitas:** retorno em 7 dias de **28,6%** (IC 26,8–30,5%), com denominador de 2.219 usuários e 635 retornos. A tabela completa de sensibilidade está em `analysis/03_definicoes_sensibilidade.ipynb`, e cada decisão em `docs/bdr/`. A versão das definições fica em `etl/definicoes.py` (`VERSAO_DEFINICOES`).

**Atenção:** o `timestamp` de topo é o horário do **último** turno. Os turnos do usuário não têm timestamp (0 de 26.579). Por isso o início da conversa é o timestamp da **1ª resposta do assistente**.

---

## 5. Análise

### 5.1 Discovery e qualidade dos dados (registrar cada problema + tratamento)

**Feito em 11/11** (`analysis/01_discovery.ipynb`): 10 problemas, cada um com tratamento. Os números estão em `CLAUDE.md`. Itens checados:
- `conversation_hash` **não é único** → duplicatas reais vs. conversas idênticas ("oi") de pessoas diferentes; definir chave (`turn_identifier` do 1º turno?).
- Conversas que **atravessam dias** (timestamp do último turno ≠ início).
- Timestamps fora de ordem, nulos, futuros; buracos na série (dias sem dados = coleta, não comportamento).
- IPs com volume absurdo (bots, IPs compartilhados, scripts) → regra de exclusão/flag.
- User-agents vazios, de bots, de bibliotecas (python-requests etc.).
- Idioma inconsistente com país; `state` nulo.
- Conversas `redacted`/`toxic` e o que fazer com elas.
- Turnos vazios, mensagens truncadas.

### 5.2 EDA (mostrar só gráficos que levaram a conclusão)
- Uso no tempo (diário/semanal), novos vs. recorrentes, anomalias/picos.
- Por modelo (GPT-3.5 × GPT-4), idioma, tema, tamanho de conversa, horário/dia da semana.
- Concentração: % de conversas vindas do top 1% de usuários.
- Curva de retenção (D1, D7, D30) por coorte.

### 5.3 Efeito de cada fator no retorno em 7 dias (com IC, ordenado)
Fatores da 1ª experiência: modelo, tema, nº de turnos, tamanho da resposta, recusa, horário local, dia da semana, idioma em 3 níveis, `redacted`, dispositivo (mobile ou desktop pelo UA) e estado agrupado. O fator `toxic` sai da lista: a base pública removeu as conversas tóxicas, e o campo é 0 em todo o Brasil.
- **Regressão logística multivariada** → apresentar como **diferença em pontos percentuais** (efeito marginal médio) com **IC 95%** (mais fácil para não técnico que odds ratio).
- Bootstrap como checagem do IC.
- Gráfico final: **forest plot** ordenado pelo tamanho do efeito.

### 5.4 Confusão: causa × seleção
- Confundidores possíveis: quem escolhe GPT-4 já é mais engajado; horário reflete perfil (estudante × trabalhador); tema reflete intenção prévia; dispositivo; estado.
- **Tratamento:** controle por perfil na regressão + **propensity score** (pareamento ou IPW) para os fatores principais (ex.: GPT-4), checando balanceamento (SMD < 0,1).
- Comparar efeito **bruto × ajustado** → "quanto era seleção".
- **O que prova e o que não prova:** não é experimento; viés por variáveis não observadas permanece; sugerir **teste A/B** para confirmar os efeitos principais.

### 5.5 Semana atípica
- Encontrar uma semana em que o retorno subiu/caiu de forma relevante (fora do IC).
- **Decomposição mix × taxa:** mudou o **perfil** de quem chegou ou mudou a **taxa dentro de cada perfil**?
- Cruzar com eventos de dados (mudança de modelo disponível, pico de novos, falha de coleta).

### 5.6 Saídas para o cliente
- **3 achados → 3 decisões** (ex.: "recusas na 1ª conversa reduzem X p.p. o retorno → revisar política de recusa em temas Y").
- O que os dados **permitem** e **não permitem** medir; **dados que faltam** (avaliação do usuário, login/ID, origem do tráfego, satisfação, eventos de UI).
- Sugestões para o **assistente** (onde falha, que temas/respostas afastam).
- Sugestões para o **dashboard** (indicadores que só surgiram depois de ver os dados).

---

## 6. Dashboard

### 6.1 Telas (mínimo exigido: 2; planejadas: 2)
Cada tela: **a pergunta que responde no título**, definição e fonte de cada número (tooltip/rodapé), IC em todo efeito, aviso quando **n é pequeno demais**.

| Tela | Pergunta | Gráficos (e por quê) |
|---|---|---|
| 1. Visão geral de retenção | "Quantos experimentam e quantos voltam, ao longo do tempo?" | KPIs (novos, % retorno 7d com IC); **linha** de retorno **mensal** com faixa de IC; barras de novos por mês; coorte semanal como detalhe |
| 2. O que faz voltar | "Quais fatores da 1ª experiência mais pesam no retorno?" | **Forest plot** (efeito ajustado em p.p. ± IC, ordenado); toggle bruto × ajustado (mostra seleção); texto curto "o que isso prova / não prova"; **segundo bloco:** barras de retorno por tema e por modelo, com IC |

**Base pequena demais:** se o IC passar de ±10 p.p. (cerca de 80 usuários), mostre o número esmaecido, com o aviso "amostra insuficiente". Nunca esconda o número sem aviso. Motivo da regra: o IC da coorte semanal é de ±15 p.p., e o da mensal, de ±7 p.p.

### 6.2 Indicadores (em [docs/METODOLOGIA.md](docs/METODOLOGIA.md), §11)
Para cada um: **definição, fórmula, numerador, denominador, período de referência, SQL e regra de amostra mínima**.
- Novos usuários (por mês; semana como detalhe)
- Taxa de retorno em 7 dias (+ IC Wilson)
- Efeito ajustado por fator (p.p. + IC)
- % de 1ª conversa com recusa
- Mix de temas na 1ª conversa

### 6.3 Endpoints (Flask + flask-smorest)
Cada recurso é um `Blueprint` do smorest, com `@blp.arguments(SchemaEntrada, location="query")` e `@blp.response(200, SchemaSaida)`. A documentação Swagger fica em `/docs` (gerada pelo smorest) e entra no `docs/ARQUITETURA.md`.

| Endpoint | Entrada | Saída |
|---|---|---|
| `GET /api/kpis` | `inicio`, `fim`, `pais` | novos, retorno 7d, IC, n, data da última carga |
| `GET /api/retencao/coortes` | `inicio`, `fim`, `pais`, `granularidade=mes\|semana`, `dimensao?` | lista por coorte ou por nível da dimensão: novos, voltaram_7d, taxa, IC, `amostra_suficiente` |
| `GET /api/fatores/efeitos` | `pais`, `ajuste=bruto\|ajustado` | fator, nível, efeito_pp, ic_inf, ic_sup, n, método |
| `GET /api/health` | — | status da API e do banco |

Todo response com `request_id`, `definicao_versao` e `fonte` (campos comuns num schema base `MetaSchema`).

### 6.4 Performance
- **Pré-calculado na carga:** `primeira_experiencia`, `agg_coorte`, `resultado_efeitos` (o modelo estatístico roda no ETL, não no request).
- **Sem cache externo.** As tabelas chegam prontas da carga, e cada endpoint é um `SELECT` sobre poucos milhares de linhas. Um cache em memória do processo entra só se a medição acusar necessidade. Motivo do corte: Redis e ElastiCache seriam um serviço a mais para um ganho que a medição não pede.
- **Medição:** hooks `before_request`/`after_request` do Flask que geram `request_id` e logam `duracao_ms` por endpoint; meta p95 < 500 ms; em produção, CloudWatch.

### 6.5 Outros países (seção do documento)
- Coluna `pais` em todas as tabelas e parâmetro em todos os endpoints: a abertura não exige mudança de schema.
- **Fuso por país:** uma tabela `dim_pais` com o timezone; a coorte é calculada no fuso local, e o armazenamento fica em UTC.
- **Comparação entre países só com as mesmas definições e com IC.** A definição de usuário por IP se comporta de forma diferente em cada país, por causa do NAT das operadoras.

### 6.6 Privacidade — mostra × nunca mostra
- **Mostra:** contagens agregadas, taxas, efeitos, distribuição por tema/modelo/estado com n mínimo.
- **Nunca mostra:** texto das conversas, hashed_ip, user-agent, qualquer identificador de usuário, recortes com n < k (k-anonimato, ex.: k = 20), conversas `redacted`.
- Texto das conversas só é processado na carga (classificação) e não vai para a base que o dashboard lê.

---

## 7. Arquitetura → [docs/ARQUITETURA.md](docs/ARQUITETURA.md)

Escrito em 13/11, com **6 serviços AWS**: S3, Glue Python Shell, RDS PostgreSQL, ECS Fargate, CloudWatch Logs e
SSM Parameter Store. O documento traz o diagrama, o papel de cada serviço, a tabela local × produção, o custo
por mês e o que foi deliberadamente deixado de fora. A decisão fica no ADR-006.

---

## 8. Sustentação (§4.1 do desafio)

### 8.1 O que registrar em cada camada
| Camada | O que registrar |
|---|---|
| Carga | id da execução, arquivo/partição lida, linhas lidas/gravadas/rejeitadas por motivo, checksum, duração, versão das definições, versão do prompt/modelo de classificação |
| Base analítica | `meta_carga`, contagens por dia/semana, chaves duplicadas, versão do schema (migrations) |
| Backend | `request_id`, endpoint, params, duração, nº de linhas, versão da carga usada, erros |
| Tela | qual endpoint/`request_id` gerou cada número, versão exibida no rodapé ("dados até dd/mm, carga #N") |

### 8.2 Detectar divergência antes do cliente
- **Reconciliação pós-carga (proposta, não construída — ver §14):** recalcular os KPIs direto da bruta, por um caminho independente da carga, e comparar com a base analítica; diferença acima da tolerância gera alerta.
- Checagens de anomalia: novos da semana fora de ±3σ, razão `usuario_id / hashed_ip` mudando, explosão de user-agents novos.
- **Construído na entrega:** `meta_carga` com linhas lidas, gravadas e rejeitadas por motivo, e o teste de regressão do incidente (§9).

### 8.3 Testes e caminho até produção
- **Testes de definição** (pytest): dataset sintético pequeno com resposta conhecida → `retorno_7d` precisa dar exatamente X (pega mudança silenciosa de definição).
- Testes da carga (idempotência: rodar 2× não duplica; conversa que atravessa dia).
- Testes de contrato da API: test client do Flask valida cada resposta contra o schema marshmallow + snapshot do OpenAPI gerado pelo smorest (mudança de contrato aparece no PR).
- **Snapshot dos indicadores**: mudança de valor acima da tolerância exige aprovação explícita.
- **Caminho:** branch → PR com CI (testes + lint) → ambiente de homologação com cópia da base → migrations versionadas (Alembic/Flyway) → deploy em produção (ECS) → reconciliação pós-deploy.

---

## 9. Investigação do incidente (§4.2) → `docs/INCIDENTE.md`

**Fatos:** semana 20/11/2023: dashboard 2.034 novos / 366 voltaram (18%) × relatório por `hashed_ip`: 1.172 / 352 (30%). Semanas anteriores: dashboard ~5% acima do relatório. **Retornos estáveis, denominador quase dobra** → o problema está em **quem é contado como novo**.

**Checado em 11/11:** esses números não aparecem na base pública (na semana de 20/11 o Brasil tem 61 novos; o mundo, 5.355). Logo, são ilustrativos. A entrega demonstra o **mecanismo** com dados reais: user-agents distintos por IP por semana, e quanto das chaves novas pertence a um `hashed_ip` que já existia.

Responder os 5 itens:
1. **Por onde começar e por quê:** comparar o resultado do endpoint com o relatório por camada — denominador vs. numerador; confirmar que a tela só exibe o que a API devolveu (resposta do monitoramento já confirma); descer para a base analítica e a carga.
2. **Camada da falha + evidências + consulta de confirmação.** Hipótese principal: **carga** — `usuario_id = sha256(hashed_ip | user-agent)` → mudança de user-agent (ex.: atualização de navegador) faz pessoas antigas aparecerem como novas. Confirmar: na bruta, para os "novos" da semana 20/11, quantos `hashed_ip` já existiam antes com outro user-agent; distribuição de user-agents/versões novas naquela semana. Outras hipóteses a checar e descartar com dados:
   - `ultimo_turno` (último turno) usado como "primeira vez";
   - `ON CONFLICT (conversa_id) DO NOTHING` + carga diária → conversa que continua no dia seguinte não atualiza; `turn_identifier` do 1º turno como chave;
   - possível recarga/backfill duplicado naquela semana;
   - `date_trunc('week')` em UTC; janela "> 1 hora";
   - o `EXISTS` do retorno não filtra `pais`: um retorno de fora do Brasil conta como retorno.
3. **Trecho e correção:** chave de usuário na carga (alinhada à BDR-001) + reprocessamento; corrigir também os pontos secundários encontrados.
4. **Além do código:** reprocessar o histórico, recalcular agregados, invalidar cache, revisar outros indicadores afetados, registrar postmortem, adicionar teste de regressão + reconciliação automática + alerta de razão usuários/IP.
5. **Comunicação com a gerente de produto:** *durante* — "o número está em investigação, indícios de que é um problema de contagem e não de comportamento; previsão de retorno X"; marcar o número como "em revisão" na tela. *Depois* — causa em linguagem simples, número corrigido, o que foi feito para não repetir.

---

## 10. ADRs e BDRs a escrever

Formato de cada um (meia página):
```
# ADR-00X — Título
Status: aceito | Data
Contexto: ...
Opções consideradas: A / B / C (prós e contras)
Decisão: ... porque ...
Consequências / o que muda se a premissa estiver errada: ...
```

**ADRs:**

| ADR | Decisão | Status |
|---|---|---|
| 001 | Base analítica em PostgreSQL | a escrever (D5), meia página |
| 002 | **Backend em Flask + flask-smorest** (vs. FastAPI, Django REST) — familiaridade do time, OpenAPI automático pelos schemas marshmallow, Blueprints | **aceito** |
| 003 | Frontend: Streamlit com tema, consumindo a API | **aceito (11/11)** |
| 004 | **Classificação com LLM aberto (Qwen3-8B) numa EC2 só com CPU**, pré-calculada e versionada; validação com amostra manual (§12.1). Bedrock avaliado e descartado: a conta nova tem cota 0 em todos os modelos | **aceito (12/11)** |
| 005 | Pré-cálculo na carga, sem cache externo | **não vira ADR.** Decisão registrada na §6.4 |
| 006 | **Arquitetura AWS em 6 serviços: S3, Glue Python Shell, RDS, ECS Fargate, CloudWatch, Parameter Store** (vs. Glue Spark, Step Functions, EventBridge, ElastiCache, CloudFront) | **aceito (13/11)** |
| 007 | Privacidade: o que o dashboard mostra e nunca mostra; k-anonimato | a escrever (D5), meia página |
| 008 | Método estatístico: logística + efeito marginal + IPW | **não vira ADR.** Decisão registrada em `docs/METODOLOGIA.md` |
| 010 | **Motor de análise/ETL local: DuckDB** (vs. pandas puro, Polars, Spark, carregar tudo no Postgres, **Polars + Postgres + dbt**) — lê parquet direto, processa fora da memória, SQL reaproveitável; dbt avaliado e adiado por risco de prazo (texto completo abaixo) | **aceito** |

Exemplo preenchido (modelo para os demais):
```
# ADR-002 — Framework do backend
Status: aceito | 2026-11-10
Contexto: a API serve indicadores pré-calculados para o dashboard; precisa validar
parâmetros, documentar endpoints (pedido do desafio) e ser simples de manter.
Opções consideradas:
  A) FastAPI — OpenAPI nativo, async; menor familiaridade do time.
  B) Flask + flask-smorest — familiaridade, validação e OpenAPI via marshmallow, Blueprints.
  C) Django REST Framework — robusto, mas pesado para uma API só de leitura.
Decisão: B. As consultas são leves (dados pré-calculados), então async não traz ganho
relevante; a familiaridade reduz risco no prazo e o smorest cobre validação e documentação.
Consequências: servir com gunicorn (workers síncronos); se a API crescer para muitas
chamadas lentas/externas, reavaliar async (ex.: FastAPI ou Quart).
```

ADR-010 completo (decisão com alternativa forte rejeitada — bom ponto para a entrevista):
```
# ADR-010 — Motor de análise e transformação (ETL local)
Status: aceito | 2026-11-10
Contexto: a base bruta (WildChat-1M) vem em parquet, tem ~840 mil conversas com o
texto completo (vários GB) e uma coluna aninhada (conversation = lista de turnos).
É preciso filtrar o Brasil, extrair o timestamp do 1º turno, derivar usuário/sessão/
retorno e popular a base analítica (Postgres) dentro do prazo do desafio (~1 semana).
Opções consideradas:
  A) pandas puro — familiar; carrega tudo em memória (risco de estourar RAM com o texto);
     lógica em dataframe, não reaproveitável como SQL dos indicadores.
  B) Polars — rápido e lazy (scan_parquet), resolve memória; lógica fica em código de
     dataframe, não em SQL.
  C) Spark — escala, mas é exagero para o volume e complica o docker compose.
  D) Carregar a bruta no Postgres e transformar lá — exige importar o texto inteiro;
     Postgres é orientado a linha e mais lento para varreduras analíticas; texto
     sensível passaria a morar no banco.
  E) Polars + Postgres + dbt — Polars extrai; dbt organiza as definições em models SQL
     com unit tests, testes de qualidade e linhagem (dbt docs). Melhor aderência aos
     critérios de sustentação/documentação, porém: experiência do autor com dbt é
     intermediária, adiciona uma etapa ao compose e consome horas de setup num prazo curto.
  F) DuckDB — lê parquet direto e fora da memória, UNNEST resolve a lista de turnos,
     dialeto SQL próximo do Postgres; zero infraestrutura.
Decisão: F (DuckDB). Entrega o mesmo ganho de memória do Polars e mantém as definições
em SQL que migra quase direto para os indicadores do Postgres, com risco de prazo menor
que E. Os ganhos que o dbt traria são cobertos de forma mais simples: testes de
definição em pytest com dataset sintético, SQL dos indicadores versionado em
db/views/ e docs/METODOLOGIA.md §11 com a origem de cada número.
Consequências:
  - Sem linhagem automática: documentada à mão no METODOLOGIA.md e no diagrama.
  - Em produção, o mesmo job DuckDB roda num Glue Python Shell (ADR-006). Athena
    entra só se a base crescer muito.
  - Evolução recomendada (registrar em "o que faria diferente"): migrar as definições
    para dbt (dbt-postgres ou dbt-duckdb) quando houver mais indicadores, mais pessoas
    mantendo ou outros países — o SQL em DuckDB facilita essa migração.
  - Revisitar se o volume crescer além de uma máquina (outros países, dados diários).
```

**BDRs:** 001–010 da §4.

---

## 11. Riscos e decisões em aberto (§4.3) → `docs/RISCOS.md`

A lista viva está em `docs/RISCOS.md`: 11 riscos, cada um com efeito no resultado, mitigação e a quem escalar.

- Definição de usuário por IP é frágil (NAT, IP dinâmico, VPN) → **decisão do cliente** sobre aceitar a margem ou implantar login/ID.
- Efeitos são observacionais → decisão de investir em **teste A/B** antes de mudanças grandes.
- Classificação por LLM tem erro → aceitar a acurácia medida?
- Dados pessoais no texto → política de retenção e quem acessa a base bruta (**jurídico/cliente**).
- Base pública ≠ produto do cliente (período 2023–2024, GPT-3.5/4) → validade externa.
- Custo AWS: classificação em ≈ US$ 5 no desafio e ≈ US$ 4/mês em produção (§12.1); RDS e Fargate à parte → orçamento aprovado pelo cliente e alerta de gasto.
- Escopo de outros países → priorização.

**Riscos que surgiram na execução:**
- **A conta AWS não libera nenhum modelo do Bedrock** (11 e 12/11): a cota on-demand é 0 em todos e o batch responde "account is not authorized". O Support confirmou que a liberação leva alguns ciclos de faturamento. A classificação roda num LLM aberto em CPU (ADR-004), e a contingência por palavras-chave e regex fica de reserva.
- **A base pública não tem conversas tóxicas** (removidas em 2024) → o fator toxicidade não é mensurável. Um retorno tóxico desaparece, e o retorno fica subestimado.
- **Base pequena:** 2.219 usuários, cerca de 39 por semana → IC semanal de ±15 p.p. Efeitos pequenos não aparecem.
- **Modelo confundido com o tempo:** não há GPT-4 no Brasil de 24/06 a 07/11/2023 → compare modelos só nos períodos com os dois.

---

## 12. Uso de IA → `docs/USO_DE_IA.md`
**Manter log desde o Dia 1** (data · ferramenta · para quê · o que conferi/corrigi/descartei):
- Claude Code: código do ETL, API, front, testes.
- Claude (chat): planejamento, revisão de texto.
- LLM aberto (Qwen3-8B em CPU, numa EC2): classificação de tema/recusa (desenho e custo em §12.1).
- **Conferência:** amostra estratificada de ~150 conversas rotuladas manualmente → acurácia/concordância por tema (matriz de confusão); comparar números da análise com consultas SQL independentes; revisar todo SQL gerado.
- Horas por dia (para o total final).

**Contingência (só se a EC2 falhar):** classificador por palavras-chave PT/EN para tema e regex para recusa, validado na mesma amostra. Com o LLM, o regex de recusa roda junto como checagem cruzada.

### 12.1 Classificação de tema e recusa — desenho e custo

**Desenho** (ADR-004)
- **Modelo:** Qwen3-8B Q4_K_M (Apache 2.0) com llama.cpp v0.9.0, numa EC2 c7i.4xlarge só com CPU. Acesso só por SSM, sem porta aberta.
- **O que classificar:** as **3.361 conversas da 1ª sessão** de cada usuário. A análise de retorno usa só a 1ª sessão; em CPU, a base inteira levaria ~20 h, contra ~6 h.
- **Entrada enxuta:** instrução fixa (taxonomia e formato) + 1ª mensagem do usuário (até 2.000 caracteres) + 1ª resposta do assistente (até 1.500). Medido: ≈ 1.355 tokens de entrada por conversa.
- **Saída curta (~54 tokens):** JSON forçado pela gramática do llama.cpp, com `motivo` (até 12 palavras), `tema` (11 valores), `recusa` (`nao`, `parcial` ou `total`) e `confianca`. Temperatura 0. As 43 conversas de entrada vazia recebem o rótulo por regra, sem chamar o modelo.
- **Idempotência:** chave = `conversa_id + versao_prompt + modelo`; saída em `data/enriched/temas_v2_qwen3_8b.parquet`, versionada no repo (o `compose up` não chama LLM).
- **Validação:** 151 conversas rotuladas à mão, estratificadas por tema previsto; meta ≥ 85%; no máximo 2 rodadas de ajuste. Medido: **71,4%** nos 11 temas e **83,8%** em 7 grupos (BDR-009). A recusa do LLM roda contra o regex.
- **Privacidade:** o texto vai só para a instância do projeto e nunca para a base analítica. Nada sai da conta AWS.
- **Controle de gasto:** **AWS Budgets** mensal de US$ 20, e a instância se destrói em 10 h.

**Custo medido (12/11)**

| Item | Valor |
|---|---|
| c7i.4xlarge on-demand (us-east-1) | US$ 0,714/h |
| Instância viva (compilação, 2 rodadas de ajuste e rodada completa) | 6,6 h |
| Ritmo com 4 slots paralelos | 6,2 s por conversa |
| S3 (entrada, saída e sincronização) | < US$ 1 |
| **Total** | **≈ US$ 4,70** |

A conta tem US$ 146,34 em créditos AWS, com validade até 19/12/2026. O custo do desafio sai desses créditos.

**Em produção (para o documento):** o Brasil tem ~41 novos usuários por semana. Duas vias: uma EC2 spot por algumas horas por mês (≈ US$ 1/mês), ou o Bedrock em batch quando a conta tiver histórico de faturamento (≈ US$ 4/mês, sem instância para manter). O batch exige no mínimo 100 registros por job, então acumule 3 semanas.

---

## 13. Cronograma

| Dia | Foco | Tarefas | Entregável | h |
|---|---|---|---|---|
| **Ter 10/11** ✅ | Setup + dados | Repo e estrutura; download da WildChat-1M com SHA-256; recorte Brasil com DuckDB; contagens iniciais (N real → custo da classificação); ADR-002, 004 e 010; dúvidas rascunhadas | Parquet BR + primeiros números | 2 |
| **Qua 11/11** ✅ | Discovery | Qualidade dos dados (§5.1); `etl/definicoes.py` + 10 testes; sensibilidade (§4); BDR-001 a 008; ADR-003; IAM e classificador prontos | `01_discovery`, `03_definicoes`, ADR/BDR | 3 |
| **Qui 12/11** | Features + EDA | Classificação das 3.361 conversas da 1ª sessão na EC2 (ADR-004) e validação manual (BDR-009, BDR-010); tabela `primeira_experiencia`; EDA (§5.2) | `temas_v2_qwen3_8b.parquet`, `primeira_experiencia`, `02_eda` | 3 |
| **Sex 13/11** | Features + análise | `primeira_experiencia.py`; EDA (§5.2); logística + efeitos marginais com IC; IPW; bruto × ajustado; mês atípico dentro do mesmo notebook; 3 achados. Escopo cortado e `ARQUITETURA.md` escritos | `primeira_experiencia`, `02_eda`, `04_efeitos` | 4 |
| **Sáb 14/11** | Construção | Migrations + carga idempotente + pré-cálculos; Flask-smorest + 4 endpoints; **2 telas**; `docker compose up` do zero | Dashboard funcionando com dados reais | 5 |
| **Dom 15/11** | Sustentação + docs | Incidente §4.2 com teste de regressão; `INCIDENTE.md` (inclui o que registrar em cada camada); ADR-001 e ADR-007; indicadores no METODOLOGIA §11; `RELATORIO.md` | `docs/` completo + testes passando | 3 |
| **Seg 16/11** | Revisão + envio | Clonar em pasta limpa e rodar `docker compose up`; revisar o `RELATORIO.md` (curto!); fechar parágrafo de IA + horas; **enviar até ~20h** | E-mail enviado | 1–2 |

**Se atrasar, cortar nesta ordem:** o 2º bloco da tela 2 → IPW (ficar só no bruto × ajustado por logística) → ADR-001 e ADR-007 (virar seção do RELATORIO).
**Já cortado em 13/11:** tela de Saúde e reconciliação automática, tela 3, cache em Redis, 2 endpoints, `INDICADORES.md`, `MONITORAMENTO.md` e 3 ADRs (§14).
**Nunca cortar:** `compose up` do zero, 2 telas com IC, efeitos ajustados com IC, incidente, ADR/BDR, parágrafo de IA.

---

## 14. Escopo cortado em 13/11

O plano previa ~20 h e o item "a mais". No dia 13/11 a análise ainda não estava pronta. Por isso o escopo caiu
para o que o enunciado exige, mais um extra barato. **Nenhum requisito obrigatório foi tocado.**

| Corte | O que ficou no lugar | Ganho |
|---|---|---|
| Tela de Saúde dos dados e reconciliação automática (`etl/qualidade.py`, `meta_reconciliacao`, ADR-009) | Um parágrafo no `RELATORIO.md` e a §8.2 deste plano: o mecanismo que teria evitado o incidente, descrito. A carga ainda grava `meta_carga` com linhas rejeitadas | ~3 h |
| Tela 3 (explorar coortes) | Um segundo bloco na tela 2: retorno por tema e por modelo, com IC | ~1 h |
| Cache em Redis e ElastiCache | Nada. As tabelas vêm prontas da carga (§6.4) | ~1 h |
| `GET /api/perfis` e `GET /api/saude` | O parâmetro `dimensao` no endpoint de coortes | ~1 h |
| `docs/INDICADORES.md` e `docs/MONITORAMENTO.md` | Uma seção no `METODOLOGIA.md` e uma no `INCIDENTE.md` | ~1 h |
| ADR-005, ADR-008 e ADR-009 | As decisões ficam na §6.4 e no `METODOLOGIA.md`, citadas na tabela da §10 | ~1 h |
| Notebook `05_semana_atipica` | Uma seção do `04_efeitos_e_confusao` | ~0,5 h |

**O extra que fica:** a análise de sensibilidade das definições (§4), já pronta e com 14 execuções do pipeline.
Ela responde à pergunta mais difícil da defesa ("e se você tivesse escolhido diferente?") e não custa mais nada.

**Nunca cortar:** `docker compose up` do zero sem credenciais; carga a partir da bruta; o dashboard nunca lê a
bruta; 2 telas com dados reais e IC; só Brasil; infra e custo na AWS descritos; privacidade declarada; ADRs e
BDRs; cada premissa com o que muda se estiver errada; documento curto de achados; parágrafo de uso de IA com
horas; a investigação do incidente.

---

## 15. Dúvidas (prazo: quarta 11/11)

**O prazo venceu em 11/11.** O rascunho está em `docs/DUVIDAS.md`, com a premissa de cada item. Sem resposta, cada premissa vale e fica registrada no BDR correspondente.

1. Para rodar localmente, podemos entregar a classificação por LLM pré-calculada no repositório, ou o `docker compose up` deve chamar o LLM?
2. Há preferência de stack para o frontend ou é livre?
3. O filtro `country = 'Brazil'` vale por conversa, ou devemos considerar o usuário brasileiro se a maioria das conversas dele for do Brasil?
4. Podemos versionar no repositório um recorte da base bruta (só Brasil), para a carga rodar sem baixar a base inteira?

---

## 16. Preparação da apresentação (depois da entrega)
- 20 min: problema → definições (e sensibilidade) → 3 achados com decisões → dashboard ao vivo → incidente → o que faria diferente.
- Em "o que faria diferente": citar a migração das definições para dbt (ADR-010) quando o projeto crescer.
- Ensaiar a defesa de: definição de usuário, retorno, método de confusão, por que Postgres/Flask-smorest/DuckDB/frontend, custo da classificação, validação do LLM, o que a análise **não** prova.
- Simulação da entrevista técnica (40 min) comigo.

---

## Definition of Done (checklist final)
- [ ] `git clone` + `docker compose up` em pasta limpa → telas com dados reais
- [ ] ≥2 telas; cada número com definição, fonte e IC; aviso de amostra pequena
- [ ] Efeitos ordenados com IC; bruto × ajustado; o que prova / não prova
- [ ] Semana atípica com decomposição mix × taxa
- [ ] 3 achados → 3 decisões
- [ ] Qualidade de dados: problemas + tratamentos
- [ ] Sensibilidade das definições
- [ ] Indicadores documentados com SQL
- [ ] Arquitetura com diagrama, AWS, endpoints, cache, outros países
- [ ] Privacidade: mostra × nunca mostra
- [ ] Monitoramento, testes, caminho até produção
- [ ] Incidente: 5 itens respondidos com consulta e correção
- [ ] Riscos e decisões a escalar
- [ ] ADRs + BDRs
- [ ] Parágrafo de IA + horas
- [ ] "A mais" funcionando (ou documentado, se cortado)
- [ ] E-mail enviado para as duas pessoas