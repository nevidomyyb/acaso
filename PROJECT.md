# Plano — Desafio Técnico Acaso
## Análise e Dashboard de Retenção de um Assistente de IA (WildChat-1M, Brasil)

> **Prazo de entrega:** segunda **16/11/2026, 23h59** → nathalia.anjos@aca.so e daniele.cardoso@aca.so
> **Prazo para dúvidas:** **quarta 11/11** (mesmos e-mails). Sem resposta a tempo → registrar a premissa e seguir.
> **Dedicação esperada:** ~12h (plano abaixo: ~16–18h, incluindo o item "a mais").
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
| Apresentação | Explicar em 20 min e defender escolhas | §14 |
| Uso de IA | IA com critério e conferida | §12 |

---

## 2. Restrições obrigatórias (checklist de "eliminação")

- [ ] `docker compose up` sobe **tudo do zero** (base analítica + carga + backend + frontend).
- [ ] A carga **popula a base analítica a partir da base bruta**.
- [ ] O dashboard **nunca lê a base bruta** — só a base analítica.
- [ ] **Pelo menos 2 telas com dados reais**.
- [ ] Análise somente sobre `country = 'Brazil'` (premissa registrada sobre como aplicar o filtro).
- [ ] **Toda infra e custo do dashboard na AWS**, inclusive o LLM se usado (→ **Amazon Bedrock**). Para a entrega roda local; **descrever a implantação**.
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
| Classificação de tema/recusa | **Amazon Bedrock — Claude Haiku 4.5 via Batch Inference** (decidido), **pré-calculada** e versionada em `data/enriched/` | Fica na AWS; dashboard não depende de LLM em tempo real; `compose up` roda sem credenciais; custo estimado ~US$ 25–45 (§12.1) |
| Backend | **Flask + flask-smorest** (schemas marshmallow), servido por gunicorn | Familiaridade com Flask; smorest valida entrada/saída pelos schemas e gera OpenAPI/Swagger automaticamente; Blueprints organizam os endpoints (ADR-002) |
| Cache da API | Flask-Caching (Redis local; ElastiCache em produção) | Invalidação por versão da carga (§6.4) |
| Frontend | **Streamlit com tema próprio, consumindo a API** (ADR-003 aceito em 11/11) | Trade-off tempo × percepção de produto |
| Testes | pytest (ETL, SQL dos indicadores) + test client do Flask (API) | Indicador não muda sem ninguém perceber |
| Deploy (descrito) | S3 → ETL em ECS Fargate/Step Functions (agendado via EventBridge) → classificação via Bedrock Batch → RDS → API Flask (gunicorn) em ECS Fargate atrás de ALB → front em CloudFront (+S3 ou Fargate) · Bedrock · CloudWatch · Secrets Manager | Tudo AWS |

### 3.2 Estrutura do repositório

```
acaso-retencao/
├── README.md                  # como subir, o que cada tela mostra, links pros docs
├── docker-compose.yml
├── .env.example
├── data/
│   ├── raw/                   # recorte Brasil (ou script que baixa)
│   └── enriched/              # tema/recusa classificados (Bedrock) + amostra validada
├── etl/
│   ├── extract.py             # lê bruto
│   ├── transform.py           # usuário, sessão, 1ª experiência, retorno, features
│   ├── load.py                # grava base analítica (idempotente)
│   ├── classify_bedrock.py    # monta JSONL, dispara Batch Inference, lê resultado (modo reprocessar)
│   ├── prompts/               # prompt de classificação versionado (v1, v2...)
│   └── quality_checks.py      # checagens de qualidade + reconciliação
├── db/
│   ├── migrations/            # schema versionado
│   └── views/                 # SQL de cada indicador
├── analysis/
│   ├── 01_discovery.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_definicoes_sensibilidade.ipynb
│   ├── 04_efeitos_e_confusao.ipynb
│   └── 05_semana_atipica.ipynb
├── backend/                   # Flask + flask-smorest
│   ├── app/__init__.py        # create_app(), Api(), registro dos Blueprints
│   ├── app/resources/         # Blueprints: kpis, coortes, fatores, perfis, saude
│   ├── app/schemas/           # schemas marshmallow (entrada e saída)
│   ├── app/queries/           # SQL dos indicadores (mesmo SQL de docs/INDICADORES.md)
│   └── app/observability.py   # request_id, duração, logs estruturados
├── frontend/
├── tests/
└── docs/
    ├── RELATORIO.md           # documento curto: achados + decisões
    ├── ARQUITETURA.md         # diagrama + componentes AWS + endpoints + modelo
    ├── INDICADORES.md         # definição, fórmula, denominador, período, SQL
    ├── INCIDENTE.md           # resposta da §4.2
    ├── MONITORAMENTO.md
    ├── RISCOS.md
    ├── USO_DE_IA.md           # log contínuo + parágrafo final
    ├── adr/                   # ADR-001...
    └── bdr/                   # BDR-001...
```

### 3.3 Modelo da base analítica (rascunho)

- `dim_usuario` — `usuario_id`, `definicao_versao`, `primeira_vez_utc`, `estado`, `idioma_principal`, `dispositivo/navegador (derivado do UA)`.
- `fato_conversa` — `conversa_id`, `usuario_id`, `inicio_utc`, `fim_utc`, `modelo`, `turnos`, `idioma`, `tema`, `recusa`, `tam_resposta_media`, `toxic`, `redacted`, `sessao_id`.
- `fato_sessao` — `sessao_id`, `usuario_id`, `inicio`, `fim`, `n_conversas`.
- `primeira_experiencia` — 1 linha por usuário com **todas as features** da 1ª sessão + `voltou_7d` + `observavel_7d` (censura).
- `agg_coorte_semanal` — pré-calculada (semana, perfil, novos, voltaram, taxa, IC).
- `resultado_efeitos` — fator, nível, efeito, IC inferior/superior, método, n, versão do modelo.
- `meta_carga` — execução, linhas lidas/gravadas/rejeitadas, checksum, duração, versão das definições.
- `meta_reconciliacao` — indicador, valor no dashboard, valor recalculado da bruta, diferença, status ("a mais").

**Nada de texto das conversas, hashed_ip ou user-agent completo na base que o dashboard lê.**

---

## 4. Definições e premissas (viram BDRs)

Para cada uma: escolha principal + alternativas testadas + **quanto a taxa de retorno muda** (tabela de sensibilidade).

| # | Definição | Escolha inicial | Alternativas na sensibilidade | Risco se errada |
|---|---|---|---|---|
| BDR-001 | **Usuário** | `hashed_ip` | `hashed_ip + user-agent`; `hashed_ip + accept-language` | IP compartilhado (empresa/faculdade) junta pessoas → infla retorno; IP dinâmico separa uma pessoa → reduz retorno; UA muda em atualização de navegador → "novos" falsos (**é o incidente!**) |
| BDR-002 | **Sessão** | conversas do mesmo usuário com intervalo < 30 min | 15 min, 60 min | Muda o que conta como "voltar" |
| BDR-003 | **Primeira experiência** | primeira sessão do usuário na base (excluir quem já aparece nas 2 primeiras semanas → janela de "aquecimento" para não pegar usuário antigo como novo) | sem aquecimento; aquecimento de 4 semanas | Usuário antigo tratado como novo |
| BDR-004 | **Retorno em 7 dias** | nova sessão iniciada após o fim da 1ª sessão e até 7×24h depois do início dela | ≥1h depois; dia-calendário seguinte | Taxa muda bastante; justificar |
| BDR-005 | **Fuso / dia** | `America/Sao_Paulo` para dia/semana; armazenar tudo em UTC | UTC | Coortes semanais deslocadas |
| BDR-006 | **Período** | todo o período da base, **excluindo** usuários sem 7 dias observáveis (censura à direita) e semanas iniciais de aquecimento | recorte de N meses | Taxa artificialmente baixa no fim |
| BDR-007 | **Filtro Brasil** | conversa com `country='Brazil'` (**aceito 11/11**, ver `docs/bdr/BDR-007`) | `OR language='Portuguese'` (rejeitada: traz outros países lusófonos) | VPN/roaming; base pequena |
| BDR-008 | **O que conta como uso** | conversa com ≥1 turno de usuário não vazio | excluir conversas só com saudação | Ruído de "testes" |
| BDR-009 | **Tema** | taxonomia fechada de ~8–10 temas (estudo/escola, trabalho/escrita profissional, programação, tradução, criativo/ficção, conselhos pessoais, conhecimento geral, roleplay/entretenimento, outro) | — | Tema ambíguo |
| BDR-010 | **Recusa** | assistente recusa/evita a tarefa (regex PT/EN + LLM) | só regex | Subestimar recusas |

**Atenção:** `timestamp` = horário do **último** turno. Para início da conversa usar o timestamp do **primeiro turno** dentro de `conversation`.

---

## 5. Análise

### 5.1 Discovery e qualidade dos dados (registrar cada problema + tratamento)
Checar e quantificar:
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
Fatores da 1ª experiência: modelo, tema, nº de turnos, tamanho e qualidade da resposta (proxy: tamanho, recusa, erro, resposta truncada), recusa, horário, dia da semana, idioma, toxic/redacted, dispositivo (mobile/desktop pelo UA).
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

### 6.1 Telas (mínimo 2; planejadas 3 + 1 "a mais")
Cada tela: **a pergunta que responde no título**, definição e fonte de cada número (tooltip/rodapé), IC em todo efeito, aviso quando **n é pequeno demais**.

| Tela | Pergunta | Gráficos (e por quê) |
|---|---|---|
| 1. Visão geral de retenção | "Quantos experimentam e quantos voltam, ao longo do tempo?" | KPIs (novos, % retorno 7d com IC); **linha** de retorno semanal com faixa de IC (tendência no tempo); barras de novos por semana |
| 2. O que faz voltar | "Quais fatores da 1ª experiência mais pesam no retorno?" | **Forest plot** (efeito ajustado em p.p. ± IC, ordenado); toggle bruto × ajustado (mostra seleção); texto curto "o que isso prova / não prova" |
| 3. Explorar coortes/perfis | "Para quem o assistente funciona melhor?" | Barras de retorno por tema/modelo/horário com IC; filtro por período |
| 4. **Saúde dos dados ("a mais")** | "Os números deste dashboard batem com a base?" | Status por indicador, última carga, linhas rejeitadas, diferença dashboard × recálculo da bruta |

**Base pequena demais:** se n < limiar (ex.: 100 usuários ou IC > ±10 p.p.), mostrar o número esmaecido com "amostra insuficiente" em vez de esconder silenciosamente.

### 6.2 Indicadores (em `docs/INDICADORES.md`)
Para cada um: **definição, fórmula, numerador, denominador, período de referência, SQL, regra de amostra mínima**.
- Novos usuários (semana)
- Taxa de retorno em 7 dias (+ IC Wilson)
- Efeito ajustado por fator (p.p. + IC)
- % de 1ª conversa com recusa
- Mix de temas na 1ª conversa

### 6.3 Endpoints (Flask + flask-smorest)
Cada recurso é um `Blueprint` do smorest, com `@blp.arguments(SchemaEntrada, location="query")` e `@blp.response(200, SchemaSaida)`. A documentação Swagger fica em `/docs` (gerada pelo smorest) e entra no `docs/ARQUITETURA.md`.

| Endpoint | Entrada | Saída |
|---|---|---|
| `GET /api/kpis` | `inicio`, `fim`, `pais` | novos, retorno 7d, IC, n, data da última carga |
| `GET /api/retencao/coortes` | `inicio`, `fim`, `pais`, `dimensao?` | lista por semana: novos, voltaram_7d, taxa, IC, `amostra_suficiente` |
| `GET /api/fatores/efeitos` | `pais`, `ajuste=bruto|ajustado` | fator, nível, efeito_pp, ic_inf, ic_sup, n, método |
| `GET /api/perfis` | `dimensao`, `inicio`, `fim` | retorno por nível da dimensão + IC |
| `GET /api/saude` ("a mais") | — | últimas cargas, checagens, reconciliação |
| `GET /api/health` | — | status da API e do banco |

Todo response com `request_id`, `definicao_versao` e `fonte` (campos comuns num schema base `MetaSchema`).

### 6.4 Performance
- **Pré-calculado na carga:** `primeira_experiencia`, `agg_coorte_semanal`, `resultado_efeitos` (o modelo estatístico roda no ETL, não no request).
- **Cache:** Flask-Caching com Redis (produção: ElastiCache), chave = endpoint + params + `versao_carga`; **expira quando há nova carga** (invalidação por versão) + TTL de segurança de 24h.
- **Medição:** hooks `before_request`/`after_request` do Flask que geram `request_id` e logam `duracao_ms` por endpoint; meta p95 < 500 ms; em produção, CloudWatch.

### 6.5 Outros países (seção do documento)
- Coluna `pais` em todas as tabelas e parâmetro em todos os endpoints.
- **Fuso por país** (tabela `dim_pais` com timezone; coorte calculada no fuso local, armazenamento em UTC).
- **Idioma da interface** (i18n no front; textos de definição traduzidos).
- **Comparação entre países:** só com mesmas definições e IC; alerta quando a base de um país é pequena; atenção ao fato de que a definição de usuário (IP) se comporta diferente por país (NAT de operadora).

### 6.6 Privacidade — mostra × nunca mostra
- **Mostra:** contagens agregadas, taxas, efeitos, distribuição por tema/modelo/estado com n mínimo.
- **Nunca mostra:** texto das conversas, hashed_ip, user-agent, qualquer identificador de usuário, recortes com n < k (k-anonimato, ex.: k = 20), conversas `redacted`.
- Texto das conversas só é processado na carga (classificação) e não vai para a base que o dashboard lê.

---

## 7. Arquitetura (em `docs/ARQUITETURA.md`)
- **Diagrama** (Mermaid) do fluxo: base bruta → carga/enriquecimento (Bedrock) → base analítica → API → tela.
- Componentes AWS e porquê de cada um; versão local × produção.
- Modelo da base analítica (§3.3).
- Endpoints (§6.3).
- Estimativa de custo: Bedrock detalhado em §12.1; RDS e Fargate em ordem de grandeza.

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
- **Reconciliação automática pós-carga** ("a mais"): recalcula os KPIs direto da bruta (por caminho independente) e compara com a base analítica/API; diferença > tolerância → alerta + status vermelho na tela de Saúde.
- Checagens de anomalia: novos da semana fora de ±3σ, razão `usuario_id / hashed_ip` mudando, explosão de user-agents novos.

### 8.3 Testes e caminho até produção
- **Testes de definição** (pytest): dataset sintético pequeno com resposta conhecida → `retorno_7d` precisa dar exatamente X (pega mudança silenciosa de definição).
- Testes da carga (idempotência: rodar 2× não duplica; conversa que atravessa dia).
- Testes de contrato da API: test client do Flask valida cada resposta contra o schema marshmallow + snapshot do OpenAPI gerado pelo smorest (mudança de contrato aparece no PR).
- **Snapshot dos indicadores**: mudança de valor acima da tolerância exige aprovação explícita.
- **Caminho:** branch → PR com CI (testes + lint) → ambiente de homologação com cópia da base → migrations versionadas (Alembic/Flyway) → deploy em produção (ECS) → reconciliação pós-deploy.

---

## 9. Investigação do incidente (§4.2) → `docs/INCIDENTE.md`

**Fatos:** semana 20/11/2023: dashboard 2.034 novos / 366 voltaram (18%) × relatório por `hashed_ip`: 1.172 / 352 (30%). Semanas anteriores: dashboard ~5% acima do relatório. **Retornos estáveis, denominador quase dobra** → o problema está em **quem é contado como novo**.

Responder os 5 itens:
1. **Por onde começar e por quê:** comparar o resultado do endpoint com o relatório por camada — denominador vs. numerador; confirmar que a tela só exibe o que a API devolveu (resposta do monitoramento já confirma); descer para a base analítica e a carga.
2. **Camada da falha + evidências + consulta de confirmação.** Hipótese principal: **carga** — `usuario_id = sha256(hashed_ip | user-agent)` → mudança de user-agent (ex.: atualização de navegador) faz pessoas antigas aparecerem como novas. Confirmar: na bruta, para os "novos" da semana 20/11, quantos `hashed_ip` já existiam antes com outro user-agent; distribuição de user-agents/versões novas naquela semana. Outras hipóteses a checar e descartar com dados:
   - `ultimo_turno` (último turno) usado como "primeira vez";
   - `ON CONFLICT (conversa_id) DO NOTHING` + carga diária → conversa que continua no dia seguinte não atualiza; `turn_identifier` do 1º turno como chave;
   - possível recarga/backfill duplicado naquela semana;
   - `date_trunc('week')` em UTC; janela "> 1 hora".
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
| 001 | Base analítica em PostgreSQL | proposto |
| 002 | **Backend em Flask + flask-smorest** (vs. FastAPI, Django REST) — familiaridade do time, OpenAPI automático pelos schemas marshmallow, Blueprints | **aceito** |
| 003 | Frontend: Streamlit com tema, consumindo a API | **aceito (11/11)** |
| 004 | **Classificação com Bedrock — Claude Haiku 4.5, Batch Inference, pré-calculada e versionada**; validação com amostra manual; orçamento e teto de gasto (§12.1); alternativa avaliada: Amazon Nova Lite/Micro | **aceito** |
| 005 | Pré-cálculo na carga + cache com invalidação por versão da carga | proposto |
| 006 | Arquitetura AWS (S3, ECS Fargate, Bedrock, RDS, ElastiCache, CloudFront, CloudWatch, Secrets Manager) | proposto |
| 007 | Privacidade: o que o dashboard mostra e nunca mostra; k-anonimato | proposto |
| 008 | Método estatístico: logística + efeito marginal + propensity/IPW | proposto |
| 009 | Reconciliação automática + tela de Saúde ("a mais") | proposto |
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
db/views/ e docs/INDICADORES.md com a origem de cada número.
Consequências:
  - Sem linhagem automática: documentada à mão em INDICADORES.md e no diagrama.
  - Em produção, o equivalente gerenciado é Athena (SQL sobre parquet no S3) ou o
    mesmo job DuckDB rodando em ECS Fargate.
  - Evolução recomendada (registrar em "o que faria diferente"): migrar as definições
    para dbt (dbt-postgres ou dbt-duckdb) quando houver mais indicadores, mais pessoas
    mantendo ou outros países — o SQL em DuckDB facilita essa migração.
  - Revisitar se o volume crescer além de uma máquina (outros países, dados diários).
```

**BDRs:** 001–010 da §4.

---

## 11. Riscos e decisões em aberto (§4.3) → `docs/RISCOS.md`
- Definição de usuário por IP é frágil (NAT, IP dinâmico, VPN) → **decisão do cliente** sobre aceitar a margem ou implantar login/ID.
- Efeitos são observacionais → decisão de investir em **teste A/B** antes de mudanças grandes.
- Classificação por LLM tem erro → aceitar a acurácia medida?
- Dados pessoais no texto → política de retenção e quem acessa a base bruta (**jurídico/cliente**).
- Base pública ≠ produto do cliente (período 2023–2024, GPT-3.5/4) → validade externa.
- Custo AWS: Bedrock estimado em ~US$ 25–45 no desafio e ~US$ 4–7/mês em produção (§12.1); RDS/Fargate à parte → orçamento aprovado pelo cliente e alerta de gasto.
- Escopo de outros países → priorização.

---

## 12. Uso de IA → `docs/USO_DE_IA.md`
**Manter log desde o Dia 1** (data · ferramenta · para quê · o que conferi/corrigi/descartei):
- Claude Code: código do ETL, API, front, testes.
- Claude (chat): planejamento, revisão de texto.
- Bedrock (Claude Haiku 4.5): classificação de tema/recusa (desenho e custo em §12.1).
- **Conferência:** amostra estratificada de ~150 conversas rotuladas manualmente → acurácia/concordância por tema (matriz de confusão); comparar números da análise com consultas SQL independentes; revisar todo SQL gerado.
- Horas por dia (para o total final).

**Contingência (só se o Bedrock ficar indisponível ou a conta AWS travar):** classificador por palavras-chave PT/EN para tema e regex para recusa, validado na mesma amostra. Mesmo com o Bedrock, o regex de recusa roda junto como checagem cruzada.

### 12.1 Classificação com Bedrock — desenho e estimativa de custo

**Desenho**
- **Modelo:** Claude Haiku 4.5 no Bedrock (barato, rápido, bom em PT-BR). No Dia 1, confirmar no console qual versão de Haiku está habilitada na região e o preço vigente na página de preços do Bedrock (o Bedrock tem vários tiers: Standard, Flex, Priority, Batch).
- **O que classificar:** a **1ª conversa de cada usuário** (é o que a análise de retorno usa). Para a EDA de temas, se necessário, uma amostra aleatória das demais conversas.
- **Entrada enxuta:** instrução fixa (~400 tokens: taxonomia, 3–4 exemplos, formato) + 1ª mensagem do usuário + 1ª resposta do assistente, truncadas em ~800 tokens.
- **Saída JSON curta (~50 tokens):** `{"tema": "...", "recusa": true|false, "confianca": 0.0-1.0}`, temperatura 0.
- **Execução:** iterar o prompt em **on-demand** numa amostra de 200; rodar a base inteira com **Batch Inference** (JSONL no S3 → resultado no S3), ~50% mais barato.
- **Idempotência:** chave = `conversa_id + versao_prompt + modelo`; saída em `data/enriched/temas_v{N}.parquet`, versionada no repo (o `compose up` não chama o Bedrock).
- **Validação:** ~150 conversas rotuladas à mão, estratificadas por tema previsto → acurácia e matriz de confusão; meta ≥ 85%; no máximo 2 rodadas de ajuste de prompt/taxonomia. Comparar a recusa do LLM com o regex.
- **Privacidade:** mandar só o trecho necessário; o texto não vai para a base analítica; declarar no ADR-007 a política de dados do Bedrock (conferir na documentação da AWS).
- **Controle de gasto:** **AWS Budgets** com alerta em US$ 30 e US$ 60, criado antes da primeira chamada.

**Premissas da estimativa**

| Item | Valor |
|---|---|
| Preço Haiku 4.5 (on-demand, Standard) | US$ 1,00 / 1M tokens de entrada · US$ 5,00 / 1M de saída (perfis regionais/cross-region podem ser ~10% mais caros) |
| Batch Inference | ~50% do on-demand |
| Tokens de entrada por conversa | ~1.200 |
| Tokens de saída por conversa | ~50 |
| **Custo por conversa** | **on-demand ≈ US$ 0,00145 · batch ≈ US$ 0,00073** |

Fórmula: `custo = N × (tokens_in × preço_in + tokens_out × preço_out) × fator_batch`

**Cenários (N = conversas classificadas; medir o N real no Dia 1 e atualizar)**

> **Atualização 10/11 (N medido):** o Brasil tem **2.385 usuários** (`hashed_ip`) e **11.621 conversas**.
> Primeiras conversas: ≈ US$ 3,5 on-demand / US$ 1,7 batch. Todas as conversas BR: ≈ US$ 17 / US$ 8,5.
> Os cenários abaixo superestimavam o volume em ~12×; o teto do AWS Budgets pode cair para US$ 10/20.

| N | On-demand | Batch |
|---|---|---|
| 10.000 | US$ 14,50 | US$ 7,25 |
| 30.000 | US$ 43,50 | US$ 21,75 |
| 60.000 | US$ 87,00 | US$ 43,50 |

**Orçamento do desafio (cenário de referência: ~30 mil primeiras conversas, batch)**

| Item | Custo |
|---|---|
| Iteração do prompt (3 rodadas × 200 conversas, on-demand) | ~US$ 1 |
| Classificação completa (batch) | ~US$ 22 |
| 1 reprocessamento completo (se o prompt mudar após a validação) | ~US$ 22 |
| S3 (armazenamento e requests do batch) | < US$ 1 |
| **Total estimado** | **~US$ 25–45** |
| Teto (alerta do AWS Budgets) | US$ 60 |

**Em produção (para o documento):** só as primeiras conversas novas de cada dia. Com ~1.200 novos usuários/semana (ordem de grandeza do enunciado), são ~5 mil classificações/mês ≈ **US$ 4–7/mês** em batch.

**Alternativa registrada no ADR-004:** Amazon Nova Lite/Micro custa ~15–30× menos por token. Testar na mesma amostra de validação; só trocar se a acurácia ficar próxima da do Haiku.

---

## 13. Cronograma

| Dia | Foco | Tarefas | Entregável | h |
|---|---|---|---|---|
| **Ter 10/11** | Setup + dados | Criar repo e estrutura; baixar WildChat-1M (Hugging Face `allenai/WildChat-1M`, verificar termos de acesso); filtrar Brasil para parquet com DuckDB; contagens básicas (**N de primeiras conversas → recalcular custo do Bedrock**); habilitar acesso ao Claude Haiku no Bedrock + criar alerta no AWS Budgets; iniciar `USO_DE_IA.md`; **redigir dúvidas** | Parquet BR + primeiros números | 2 |
| **Qua 11/11** | Discovery | **Enviar dúvidas de manhã**; qualidade dos dados (§5.1); definições + tabela de sensibilidade (§4); ADR-003 (frontend) decidido | `01_discovery`, `03_definicoes`, BDRs rascunho | 3 |
| **Qui 12/11** | Features + IA | Tabela de 1ª experiência; iterar prompt no Bedrock (on-demand, amostra de 200) → rodar Batch Inference na base; amostra rotulada à mão + métricas de validação; EDA (§5.2) | `primeira_experiencia`, validação, `02_eda` | 3 |
| **Sex 13/11** | Análise | Logística + efeitos marginais com IC; propensity/IPW; bruto × ajustado; semana atípica (mix × taxa); 3 achados | `04_efeitos`, `05_semana`, resultados | 3 |
| **Sáb 14/11** | Construção | Migrations + ETL idempotente + pré-cálculos; Flask-smorest + Blueprints + schemas; 3 telas; `docker compose up` do zero | Dashboard funcionando com dados reais | 4 |
| **Dom 15/11** | Sustentação + docs | Incidente §4.2; monitoramento/testes (§8); tela de Saúde + reconciliação ("a mais"); arquitetura + diagrama; indicadores; riscos; ADRs/BDRs finais | `docs/` completo + testes passando | 3 |
| **Seg 16/11** | Revisão + envio | Clonar em pasta limpa e rodar `docker compose up`; revisar o `RELATORIO.md` (curto!); fechar parágrafo de IA + horas; **enviar até ~20h** | E-mail enviado | 1–2 |

**Se atrasar, cortar nesta ordem:** tela 3 → bootstrap → sensibilidade de sessão (15/60) → tela de Saúde (manter reconciliação só como job + doc).
**Nunca cortar:** `compose up` do zero, 2 telas com IC, efeitos ajustados com IC, incidente, ADR/BDR, parágrafo de IA.

---

## 14. "A mais" — Tela de Saúde dos Dados + Reconciliação automática

**Por quê:** é exatamente o mecanismo que teria evitado o incidente do desafio e é a rotina da vaga (sustentação: perceber que um número divergiu **antes** do cliente).

**O que é:**
- Job `quality_checks.py` roda após cada carga:
  - recalcula novos e retorno 7d por semana **direto da base bruta** (caminho independente do ETL);
  - compara com `agg_coorte_semanal` e com a resposta da API;
  - checa anomalias (novos ±3σ, razão usuários/IP, user-agents novos, linhas rejeitadas);
  - grava em `meta_reconciliacao`.
- Tela 4 mostra: última carga, status por indicador (verde/amarelo/vermelho), diferença, linhas rejeitadas por motivo.
- Teste automatizado: injetar a mudança de chave do incidente num dataset sintético e verificar que a reconciliação **dispara o alerta**.

**Na apresentação:** "Além de corrigir o incidente, construí o que faria ele ser detectado sozinho."

---

## 15. Dúvidas para enviar (até quarta 11/11)
1. Para rodar localmente, podemos entregar a classificação por LLM pré-calculada (feita via Bedrock) no repositório, ou o `docker compose up` deve chamar o Bedrock?
2. Há preferência de stack para o frontend ou é livre?
3. O filtro `country = 'Brazil'` vale por conversa, ou devemos considerar o usuário brasileiro se a maioria das conversas dele for do Brasil?
4. Podemos versionar no repositório um recorte da base bruta (só Brasil), para a carga rodar sem baixar a base inteira?

---

## 16. Preparação da apresentação (depois da entrega)
- 20 min: problema → definições (e sensibilidade) → 3 achados com decisões → dashboard ao vivo → incidente → o que faria diferente.
- Em "o que faria diferente": citar a migração das definições para dbt (ADR-010) quando o projeto crescer.
- Ensaiar a defesa de: definição de usuário, retorno, método de confusão, por que Postgres/Flask-smorest/DuckDB/frontend, custo do Bedrock, validação do LLM, o que a análise **não** prova.
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