# Memória do projeto — Desafio Técnico Acaso (retenção de assistente de IA, WildChat-1M Brasil)

> Memória persistente do projeto, carregada em toda sessão. Plano e escopo: [PROJECT.md](PROJECT.md).
> **Ao fim de cada sessão:** atualize "Status", "Pendências" e "Próximos passos". Registre fatos novos em
> "Fatos dos dados". Acrescente a linha do dia em [docs/USO_DE_IA.md](docs/USO_DE_IA.md), com horas.

## Contexto
- Pergunta: **o que faz quem experimentou o assistente voltar em até 7 dias?** Quanto pesa cada fator (com IC)? Quanto é causa e quanto é seleção?
- Cliente de negócio, sem perfil técnico. O resultado é um **dashboard**. Cada número tem definição, fonte e IC.
- Entrega: **seg 16/11/2026 23h59** (meta: ~20h). Dúvidas de escopo esclarecidas no Dia 2 (11/11). A pessoa candidata envia os e-mails, não o Claude.
- Depois: 20 min de apresentação + 40 min de entrevista técnica.

## Padrão de escrita de documentos (obrigatório)
Use em **todo documento** do projeto (ADR, BDR, README, docs/, relatório, e-mails). Padrão: **ASD-STE100 (Simplified Technical English) adaptado ao português, com ~80% de rigor**. Aplique as regras abaixo sempre que o português permitir. Não force uma regra que deixa o texto artificial.
1. Frases curtas: até 20 palavras em instrução, até 25 em descrição.
2. Uma ideia por frase. Parágrafo com até 6 frases.
3. Voz ativa e tempo presente. Instrução no imperativo.
4. Um termo = um significado. Use sempre o mesmo termo (usuário, conversa, sessão, retorno em 7 dias, coorte).
5. Condição antes da ação: "Se X, faça Y".
6. Sem gerúndio, sem palavras vagas ("bastante", "muito", "diversos"). Números com unidade e fonte.
7. Listas para 3 itens ou mais. Tabelas para comparar opções.
8. Sem grupos de mais de 3 substantivos seguidos.
- ADR/BDR seguem os modelos [docs/adr/_MODELO.md](docs/adr/_MODELO.md) e [docs/bdr/_MODELO.md](docs/bdr/_MODELO.md): Contexto (≤ 4 frases) · Opções (tabela) · Decisão (1–2 frases) · Consequências/Impacto. Meia página no máximo.
- Código e comentários de código não seguem este padrão; seguem clareza normal.

## Regras que eliminam (nunca violar)
1. `docker compose up` sobe **tudo do zero** (Postgres + carga + backend + frontend), **sem credenciais AWS**.
2. A carga popula a base analítica **a partir da base bruta**. O dashboard **nunca lê a bruta**.
3. ≥ 2 telas com **dados reais**.
4. Só `country = 'Brazil'` (BDR-007, aceito).
5. Infra e custo na **AWS**, inclusive o LLM. A entrega roda local; a implantação fica descrita.
6. A base analítica **não** tem texto das conversas, `hashed_ip`, user-agent completo nem identificador exibível. k-anonimato (k=20) nos recortes.
7. Toda premissa registrada **+ o que muda se estiver errada**. ADRs em `docs/adr/`, BDRs em `docs/bdr/` (índices em `README.md` de cada pasta).
8. Parágrafo final de uso de IA: ferramentas, o que foi conferido/corrigido/descartado e **horas**.

## Decisões tomadas (não reabrir sem fato novo)
| Item | Decisão | Status |
|---|---|---|
| ADR-002 backend | Flask + flask-smorest, gunicorn, Swagger em `/docs` | aceito |
| ADR-004 classificação | **LLM aberto em CPU numa EC2**: **Qwen3-8B Q4_K_M** (sem thinking) + llama.cpp v0.9.0, c7i.4xlarge, acesso só por SSM, autodestruição por `shutdown`. **Prompt v2**, saída JSON por gramática. Escopo: **só a 1ª sessão** (3.361 conversas; 43 vazias por regra). Saída: `data/enriched/temas_v2_qwen3_8b.parquet`; o compose não chama LLM. Bedrock descartado (cota 0). Ajuste fechado (2 rodadas) | aceito (12/11) |
| ADR-010 motor ETL | DuckDB (dbt adiado). Em produção, o mesmo job roda no Glue Python Shell | aceito |
| ADR-006 arquitetura | **6 serviços AWS:** S3 → **Glue Python Shell** (carga agendada) → RDS PostgreSQL → ECS Fargate (API + dashboard) atrás de ALB · CloudWatch Logs · SSM Parameter Store. ≈ US$ 70/mês. **Glue Python Shell, não Spark** (base de 22 MB). Fora: Step Functions, EventBridge, ElastiCache, CloudFront, Secrets Manager | aceito (13/11) |
| BDR-007 filtro | Só `country = 'Brazil'`. Alternativa rejeitada: `OR language = 'Portuguese'` (traria Portugal, Moçambique etc. e foge da restrição) | aceito |
| ADR-003 frontend | **Streamlit com tema próprio** (`.streamlit/config.toml` + CSS), lendo **só a API**; gráficos em Altair com a paleta da análise; ECS Fargate na AWS | aceito (11/11) |
| BDR-001 usuário | `hashed_ip` (IP+UA dá +2,2 p.p.; IP compartilhado −0,1 p.p.) | aceito |
| BDR-002 sessão | atividade = **cada resposta do assistente** (pega quem continua conversa aberta; +4,3 p.p. vs só início de conversa); gap 30 min | aceito (confirmado pela pessoa 11/11) |
| BDR-003 1ª experiência | 1ª sessão, sem aquecimento (base começa em 09/04/2023) | aceito |
| BDR-004 retorno | nova sessão até 7×24h do início da 1ª | aceito |
| BDR-005 fuso | UTC armazenado; agrupa em `America/Sao_Paulo` | aceito |
| BDR-006 período | tudo; tira censurados (48) e janela com falha de coleta (87); falha = volume global < 15% da mediana | aceito (confirmado pela pessoa 11/11) |
| BDR-008 uso | conversa com ≥ 1 mensagem não vazia (76 saem) | aceito |
| BDR-009 tema | **7 grupos** (`GRUPO_TEMA` em `definicoes.py`), tema da **1ª conversa da 1ª sessão**; 11 temas só nos gráficos descritivos | aceito (12/11) |
| BDR-010 recusa | fator = recusa **`total` pelo LLM na 1ª conversa** (`RECUSA_FATOR`); regex e sessão inteira = sensibilidade; parcial fora | aceito (12/11) |
| Visão do dashboard | coorte **mensal** principal; semanal como detalhe; esmaecer se IC > ±10 p.p. (~80 pessoas) | decidido 11/11 |
| Escopo da entrega | **2 telas** (visão geral; o que faz voltar, com 2º bloco por tema e modelo), **4 endpoints** (`kpis`, `retencao/coortes` com `dimensao`, `fatores/efeitos`, `health`), **sem cache externo** (tabelas prontas da carga). Cortes e motivos em PROJECT.md §14 | decidido 13/11 |
| Base analítica | **4 tabelas:** `primeira_experiencia` (1 linha/usuário, `usuario_sk` substituto), `resultado_efeitos`, `meta_carga`, `alembic_version`. Fora: `agg_coorte`, `dim_usuario`, `fato_conversa`, `fato_sessao` (nenhuma tela lê). **Agregação em views SQL** na hora da requisição (filtros dinâmicos; o SQL do indicador fica no banco). Pré-cálculo pesado (sessões, retorno, fatores, regressão) continua na carga | decidido 14/11 |
| Migrations | **Alembic**, migrations escritas à mão (sem autogenerate); as views entram como migrations (histórico de cada mudança de indicador). SQLAlchemy só como conexão do Alembic; a carga grava com psycopg 3 | decidido 14/11 |
| k-anonimato (k=20) | **Mantido**, apesar de não ser requisito do enunciado (§2.2 só pede "o que mostra e o que nunca mostra"). Recorte por dimensão com n < 20 volta sem taxa e IC, com `suprimido_k = true` e aviso na tela. Total da semana/mês aparece mesmo com n < 20, esmaecido. `estado_grupo` segue agrupado | decidido 14/11 |
| Compose | 6 serviços: `bruta` → `classificacao` → `carga` → `postgres` ← `api` ← `dashboard`. `classificacao`: se `data/enriched/temas_v2_qwen3_8b.parquet` existe, só confere e sai; se não, roda a EC2 (ADR-004) com as credenciais do `.env` e sempre destrói no fim; sem arquivo e sem credenciais, para com mensagem clara | decidido 14/11 |
| IAM | **Usuário único `acaso-operador`** (política gerenciada) + **limite de permissões `acaso-limite`** para toda role `acaso-*` que ele cria. Substitui o `acaso-etl`. Arquivos em `infra/aws/iam/`. A pessoa cria o usuário; o Claude testa depois | decidido 14/11 |
| Commit do Dia 5 | **Um commit no fim do dia**, quando a pessoa pedir | decidido 14/11 |

## Convenções
- Idioma: documentação, nomes de domínio (tabelas/colunas) e comentários em **português**.
- Python local: `.venv/` (Python 3.13, `python3 -m venv .venv`; não há `uv`). Rode com `.venv/bin/python`. Dependências fixadas em `requirements-analysis.txt`. Lint: `ruff` (`ruff.toml`, linha 120).
- Base bruta completa: `data/raw/wildchat-1m/` (gitignored, 3,36 GB), baixada por `etl/download.py` (SHA-256 + `manifest.json`).
- Recorte Brasil: `data/raw/wildchat_br.parquet` (+ `.manifest.json`), exatamente `country = 'Brazil'`, gerado por `etl/recorte_brasil.py`. É a "base bruta" que a carga do compose lê. **Fora do git (decisão de 13/11):** o `docker compose up` baixa a base (`etl/download.py`) e gera o recorte do zero. O compose **monta `./data` como volume**: se a base já existe e o SHA-256 confere, o `download.py` pula o arquivo (já é idempotente) e nada é baixado de novo. Desde 14/11, com o `manifest.json` conferido, o `download.py` não consulta a API (3,7 s, sem rede), e o `recorte_brasil.py --se-necessario` pula se o recorte veio da mesma revisão. Só `data/enriched/temas_v2_qwen3_8b.parquet` vai para o git, porque refazê-lo exige a EC2 (commit `71ed97a`, branch `dia-3`).
- Contagens rápidas: `.venv/bin/python analysis/00_contagens_iniciais.py`.
- **Definições = `etl/definicoes.py`** (fonte única: carga, notebooks e testes). `Definicoes()` = padrão aceito; cada campo cita o BDR. Mudou um padrão → mude `VERSAO_DEFINICOES`, rode `pytest` e o notebook 03. `construir(con, bruta, d, volume_diario=...)` cria `conversas → eventos → eventos_sessao → sessoes → usuarios`; `elegiveis(u, d)` = denominador.
- **Fatores da 1ª experiência = `etl/primeira_experiencia.py`**: `construir_primeira_experiencia(con, bruta, temas, volume_diario=...)` → 1 linha por usuário (2.354; `elegivel` = o mesmo denominador de `elegiveis()`, testado). Conteúdo da **1ª conversa** (modelo, `familia_modelo`, `idioma_3`, `dispositivo`, `estado_grupo` com k=20 sobre elegíveis, `tema`, `tema_grupo`, `recusa_total`, `recusa_regex`, tamanhos) e volume da **1ª sessão** (`n_conversas_sessao1`, `n_respostas_sessao1`, `duracao_sessao1_min`); `hora_local`/`faixa_horaria`/`dia_semana` (ISO, 1 = segunda) no fuso do BDR-005; `recusa_total_sessao` = sensibilidade. `usuario_id` = md5(hashed_ip): a carga troca por chave substituta (regra 6).
- **Efeitos = `etl/efeitos.py`** (notebook 04 e carga): `preparar(pe)` → elegíveis com categorias (referência em 1º); `ajustar(df, fatores, controles)` = **regressão linear** com IC robusto (HC1): o coeficiente já é o efeito em p.p.; `coeficiente(res, col, nivel)` = (efeito, IC inf, IC sup); `tabela_efeitos()` = bruto × ajustado por nível; `taxa_esperada(grupo, base, cols)` = taxa normal de cada perfil aplicada ao grupo (semana atípica). `FATORES`/`CONTROLES`/`ROTULOS` definem fatores, referências e nomes da tela. **Método simplificado em 13/11 a pedido da pessoa** (sem AME, método delta, bootstrap nem IPW; METODOLOGIA §5 tem o glossário e a conferência antiga × nova): manter o vocabulário de 10 termos do glossário.
- DuckDB: `fetchone()` de um `TIMESTAMPTZ` exige `pytz`, que não está instalado. Leia por `.df()`.
- Volume diário global: `data/raw/wildchat_volume_diario.parquet` (gerado pelo recorte) → detecta falha de coleta.
- Testes: `.venv/bin/python -m pytest -q` (base sintética em `tests/conftest.py`). Lint: `.venv/bin/ruff check analysis etl tests`.
- **Notebooks:** fonte = `analysis/NN_*.py` (jupytext, formato percent); gerar/executar com `cd analysis && ../.venv/bin/jupytext --to ipynb --execute NN_x.py`. Estilo dos gráficos em `analysis/estilo.py` (paleta da skill dataviz; rodapé com fonte via `nota()`). Sempre olhar os PNGs gerados antes de concluir.
- Classificação (ADR-004): `etl/classificacao.py` = base (taxonomia `TEMAS`/`RECUSAS`, `SCHEMA`, `texto_entrada`, `validar`, `linha_resultado`, `regra_vazio`, `cliente_s3`). `etl/classificar_cpu.py {preparar|enviar|coletar}` (local, padrão `--versao v2 --modelo qwen3_8b`) + `etl/llm_runner.py` (roda na EC2, só stdlib, retomável) + `infra/aws/ec2/classificacao.sh {criar|pronto|modelo|rodar|log|exec|destruir}` (credenciais do `acaso-operador`; a role nasce com o limite `acaso-limite`). O user-data sobe com o 4B: troque com `modelo qwen3_8b`. No compose, `etl/etapa_classificacao.sh` faz o fluxo inteiro e destrói sempre (trap). Prompt em `etl/prompts/classificacao_v2.md`; regex de recusa em `etl/recusa_regex.py`.
- Enunciado original: PDF em `docs/` e texto em `docs/desafio/enunciado.txt` (grep-ável). A janela de 7 dias é **exigência do enunciado** (linha 35), não escolha nossa ⇒ `janela_retorno_dias` não tem variante na sensibilidade.
- **`docs/ARQUITETURA.md`** tem o desenho dos 6 serviços AWS, local × produção, custo e o que ficou de fora (ADR-006).
- **`docs/METODOLOGIA_LABEL.md`** documenta a rotulagem (tema e recusa): desenho, 5 camadas de validação da saída, validação manual e limites.
- **`docs/METODOLOGIA.md`** explica a origem de cada número: ADR × BDR, sensibilidade, IC, cada query de `definicoes.py`, cada notebook e cada teste. Atualize junto com os números. O §10 tem o resumo das definições para a apresentação.
- Início da conversa = timestamp da **1ª resposta do assistente** (`list_min` dos timestamps dos turnos), nunca o `timestamp` de topo.
- Máquina: 15 GB RAM (≈ 6 GB livres), 12 núcleos. DuckDB com `memory_limit` explícito e `SET TimeZone='UTC'`.
- **Segredos:** `.env` (gitignored, `chmod 600`) tem `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (preenchidos em 11/11) e `ACASO_S3_BUCKET` (preenchidos em 11/11). O `ACASO_BEDROCK_ROLE_ARN` ficou no arquivo, sem uso. Modelo em `.env.example`. No compose, use `env_file: [{path: .env, required: false}]` para subir sem o arquivo. Nunca leia nem imprima os valores do `.env` (para checar, mascare: `awk -F= ...`).
- **AWS:** políticas IAM de menor privilégio em `infra/aws/iam/` (usuário `acaso-operador` + limite `acaso-limite`, decisão de 14/11; bucket `acaso-desafio-tecnico`) e em `infra/aws/ec2/` (role da instância: SSM + prefixo `cpu/*` do bucket). Não crie recursos AWS (Budgets, S3, EC2) sem confirmação explícita da pessoa.
- Commits e push só quando a pessoa pedir (remoto `origin` = GitHub). Ao concluir um dia, marque ✅ no cronograma do PROJECT.md (§13) e os itens prontos do checklist final. **Tudo direto na `main`, sem branches** (nem por dia, nem por tarefa; decisão da pessoa em 13/11).

## Fatos dos dados (manter atualizado)
**Fonte**
- Hugging Face `allenai/WildChat-1M`, revisão `7d6490e462285cf85d91eabea0f9a954fbddcd1f` (2024-10-17), licença ODC-BY, sem gate. 14 parquets, 3,36 GB, 837.989 conversas, 178.724 `hashed_ip`, 201 países.
- A versão pública tem **só conversas não tóxicas** (tóxicas removidas em 2024-07-22; PII sensível em 2024-10-17). ⇒ `toxic` = 0 no Brasil (fator inutilizável). As colunas `openai_moderation` e `detoxify_moderation` existem (nota por turno), mas também foram cortadas (conferido em 14/11): 0 de 837.989 conversas com `flagged` da OpenAI, e a nota máxima do Detoxify na base inteira é 0,0999 (Brasil: mediana 0,0016). Ninguém fica acima do corte ⇒ nenhuma das 3 serve como fator. A remoção cria buracos no histórico: um retorno tóxico some e o retorno fica subestimado. Registrar como risco.

**Schema e semântica**
- `conversation_hash` **não é único** (11.621 conversas BR, 11.555 hashes). Chave: `conversation[1].turn_identifier` (único no BR).
- `timestamp` de topo = último turno (UTC). **Turnos do usuário nunca têm timestamp** (0 de 26.579). Turnos do assistente sempre têm.
- Turnos do usuário têm `hashed_ip`, `country`, `state`, `header`. Os do assistente não. `header` é igual em todos os turnos da conversa.
- DuckDB 2.0: lambda com sintaxe `lambda c: c.campo`. A seta `->` dá erro.

**Brasil (`country = 'Brazil'`)** — medido em 10/11 com `analysis/00_contagens_iniciais.py`
- **11.621 conversas, 2.385 `hashed_ip`** (1,4% da base), 2023-04-09 → 2024-04-29 (386 dias = 55 semanas corridas; 57 semanas de calendário, porque a 1ª e a última são parciais).
- **Base pequena:** mediana de **41 novos IPs/semana** (mín. 9, máx. 100) ⇒ visão principal **mensal**; semanal só como detalhe.
- 1.424 de 2.385 usuários (60%) têm **uma única conversa**.
- **Concentração:** top 1% dos IPs (23 IPs, ≥ 52 conversas) = 41% das conversas (conferido em 12/11). 1 IP tem **1.557 conversas e 35 user-agents** (13% do BR). Precisa de regra de exclusão/flag.
- Qualidade: 273 conversas com entrada vazia; 56 `redacted`; 51 sem `state`; 0 sem user-agent; 211 atravessam o dia (UTC); 546 duram > 1h.
- Idioma: 76% Portuguese; 2.824 conversas (24%) em outro idioma (English é o 2º).
- **Modelo confundido com o tempo:** não há GPT-4 no BR entre 2023-06-24 e 2023-11-07. Versões: 3.5-0301 → 0613 (2023-06-28) → 0125 (2024-02-18); gpt-4-1106-preview entra em 2023-11-07; 0125-preview em 2024-03-14.
- Sazonalidade: queda de 2023-12-18 a 2024-02-05 (férias); retomada em fev/mar 2024.
- Filtro alternativo `OR language='Portuguese'` traria +1.589 conversas de 679 IPs (Portugal 663, EUA 143, Moçambique 96).

**Discovery (11/11, `analysis/01_discovery.ipynb`)**
- **Falhas de coleta globais:** 0 conversas em 13/10/2023 e 18–19/01/2024; < 15% da mediana em 26/06/2023, 14/10/2023, 17/01/2024. Feriados (Réveillon) ficam em ~20% e NÃO são falha. 87 pessoas têm a janela de 7d afetada (coortes 12–19/06, 02–09/10/2023, 08–15/01/2024).
- `timestamp` de topo = sempre o máximo dos turnos; nenhum turno fora de ordem. `conversation_hash` repetido: 93 conversas, sempre IPs diferentes (texto igual, pessoas diferentes).
- Conversa aberta por dias (máx. 11 dias; 546 > 1h). Sessão por **resposta** (turno) recupera 96 retornos.
- IPs: 89% com 1 user-agent; 3 IPs com > 10 UAs = 16% das conversas (maior: 1.557 conversas, 35 UAs, 129 dias). Sem UA de robô. 36% mobile. Só 436 UAs distintos ⇒ UA não identifica pessoa. IP dinâmico: ≥ 2% dos novos IPs (limite inferior, 48 casos).
- Intervalo entre respostas do mesmo IP: sem vale natural 15–60 min; **pico perto de 1 dia** (hábito: volta no mesmo horário do dia seguinte).
- Idioma: 76% PT, 16% EN; "Latin/Finnish/Nolang" = ruído em mensagens curtas ⇒ fator idioma em 3 níveis. Estado: 10 de 28 valores com < 20 usuários ⇒ "outros". 76 conversas sem nenhuma msg de usuário; 65 só com a 1ª vazia.

**Retorno em 7 dias (padrão, `analysis/03_definicoes_sensibilidade.ipynb`)**
- **28,6% (IC 26,8–30,5%)**, denominador 2.219, 635 voltaram. Funil conferido em 12/11: 2.385 IPs → 2.354 usuários (−31 IPs só com conversa sem conteúdo, BDR-008) → 2.306 observáveis (−48 censurados) → **2.219** (−87 com falha de coleta). O denominador é a **coorte de novatos**: cada pessoa entra uma vez, na 1ª sessão; não é "quem usou no período".
- Sensibilidade (Δ p.p.): gap 15 min +5,4 · gap 60 min −3,5 · retorno "outro dia" −9,7 · atividade por conversa −4,3 · IP+UA +2,2 · retorno > 1h −1,6 · aquecimento 2/4 sem −0,4/−0,8 · demais ≤ 0,2. "Referência do incidente" (IP+UA, conversa, > 1h) = 26,0%.
- IC médio: semanal ±15 p.p. (mediana 39 pessoas/semana); mensal ±7 p.p. Meses fora do padrão: abr/2023 40,3% (lançamento) e jan/2024 41,5% (n = 53, férias) ⇒ não usados: o enunciado pede uma **semana** atípica, tratada no 04.

**Incidente (§4.2 do desafio — texto em `docs/desafio/enunciado.txt`)**
- Dashboard (endpoint `/api/retencao/coortes`): 06/11 1.210/375 · 13/11 1.188/368 · **20/11 2.034/366** (31% → 18%). Relatório por `hashed_ip`: 1.150/345 · 1.131/351 · 1.172/352 (estável ~30%). Semanas anteriores: dashboard ~5% acima.
- Código de referência — carga diária: `usuario_id = sha256(hashed_ip|user-agent)`, `ultimo_turno = c["timestamp"]`, `conversa_id = conversation[0].turn_identifier`, `INSERT ... ON CONFLICT (conversa_id) DO NOTHING`. Endpoint: `min(ultimo_turno)` como `primeira_vez`; `date_trunc('week', ...)` sem fuso; retorno `ultimo_turno > primeira_vez + 1h AND <= +7d`; o EXISTS do retorno não filtra `pais`.
- Leitura: novos quase dobram e retornos ficam estáveis ⇒ ~860 "novos" que **não voltam** ⇒ chaves novas para pessoas antigas que não se repetem (ex.: user-agent que passa a variar por conversa, ou UA nulo/alterado). Confirmar com: UAs distintos por IP por semana; % das chaves novas cujo `hashed_ip` já existia.
- Os números não aparecem nos dados públicos (BR 20/11: 61 novos no padrão; global 5.355) ⇒ são ilustrativos; demonstrar o **mecanismo** com dados reais.

**Bedrock avaliado e descartado (11–12/11; opção A do ADR-004)**
- Cota on-demand **0 em todos os modelos**, com chamada real (Converse, 5 tokens): Haiku 4.5/5.5, Sonnet 4.6, Nova Micro/Lite/2 Lite, Qwen3 32B, gpt-oss-120b, Gemma 3 27B, Llama 3.3 70B, Ministral 3 8B, DeepSeek V3.2 ⇒ `ThrottlingException: Too many tokens per day`. Trocar de modelo não resolve.
- Batch: `CreateModelInvocationJob` → `ValidationException: Your account is not authorized`. É restrição da conta, não do IAM nem da cota. O upload da entrada no S3 funcionou.
- **Resposta do AWS Support (12/11):** conta nova com pouco histórico de uso e gasto ⇒ restrita por "alguns ciclos de faturamento", com liberação automática ⇒ **não libera antes da entrega**. Os casos de cota seguem abertos (`L-CCA5DF70` 10.000 RPM, `L-58BE175A` 5M TPM); o Service Quotas recusa valor abaixo do padrão AWS.
- Conta migrada de FREE para **PAID** em 11/11. Créditos mantidos: US$ 146,34, expiram em 19/12/2026. O custo do desafio sai deles. Consultas de plano e cota: perfil padrão do AWS CLI (administrador), sem carregar o `.env`.
- **Capacidade da conta (12/11):** GPU = **0** em tudo (EC2 G/VT on-demand e spot; SageMaker em g4dn, g5, g6, g6e; o padrão AWS também é 0). CPU: EC2 16 vCPU on-demand e 32 vCPU spot. Pedido de GPU `L-DB2E81BA` = 4 vCPU, `CASE_OPENED`; já não é necessário.
- Enunciado §2.2 (linha 112): o LLM, se usado, **tem de rodar na AWS**. O texto **não nomeia o Bedrock** (conferido em 13/11): "LLM = Bedrock" era glosa nossa. Na análise vale qualquer ferramenta ⇒ LLM local está fora; palavras-chave + regex (sem LLM) pode rodar em qualquer lugar.
- **Recursos que continuam na conta:** bucket `acaso-desafio-tecnico` (us-east-1, acesso público bloqueado) — usado pela EC2 — e role `AmazonBedrock-acaso-batch`, sem uso. O `.env` ainda tem `ACASO_BEDROCK_ROLE_ARN`, sem uso.
- IAM real ≠ documentado: o `acaso-etl` usa `AmazonS3FullAccess` + `AmazonBedrockFullAccess` (gerenciadas) na conta de desenvolvimento. Em 14/11, o alvo passou a ser o `acaso-operador` (a pessoa cria; depois, desativar e apagar o `acaso-etl`).
- Contingência (se a EC2 falhar): classificador por palavras-chave + `recusa_regex` (PROJECT.md §12).

**Classificação em CPU (12/11, ADR-004)**
- EC2 `i-078e9e3579173f86c` (c7i.4xlarge, us-east-1a). 1º boot falhou: `snap install aws-cli` sem acesso à snap store ⇒ AWS CLI pelo zip oficial; `classificacao.sh setup` reaplica.
- Ritmo (4 slots paralelos): Qwen3-4B 4,0 s/conversa; Qwen3-8B 6,5 s/conversa (latência mediana 15 s e 23 s).
- Ajuste em 40 conversas da 1ª sessão (semente 42), contra a referência do Claude em `data/work/ajuste_referencia_claude.json` (temas ambíguos aceitam mais de 1 valor): 4B v1 = 36/40 tema e 38/40 recusa; 4B v2 = 35 e 37; **8B v2 = 35 e 39** (1 recusa falsa em 3). Erros do 4B: pergunta técnica → `conhecimento_geral`; texto novo → `traducao_reescrita`; ressalva "como IA…" → `parcial`. `confianca` ≈ 0,95 constante: inútil.
- Regex de recusa perdia "sou um modelo de linguagem… não tenho a capacidade" e "I am an AI language model and cannot": corrigido + 9 testes.
- **U+2028 dentro das conversas** (3 de 3.318 registros): `str.splitlines()` quebra a linha do JSONL ⇒ ler com `split("\n")` (`ler_jsonl`) e gravar com `ensure_ascii=True`.
- **Rodada completa (12/11):** 3.318 registros em 341,7 min (6,2 s/conversa), **0 erros**, 0 JSON inválido. Instância viva 12h01–18h40 UTC (6,6 h ≈ US$ 4,7). EC2, SG, role e profile **destruídos** e conferidos. Tokens: 4,50 M entrada / 0,18 M saída.
- **Distribuição (3.361):** conhecimento_geral 817 · saudacao_teste 630 · programacao_tecnologia 429 · criativo_ficcao 363 · estudo_escola 329 · trabalho_profissional 302 · traducao_reescrita 193 · outro 117 · roleplay 88 · conselho_pessoal 69 · conteudo_adulto 24. Recusa: nao 3.149 · total 168 (5,0%) · parcial 44.
- **LLM × regex de recusa:** regex marca 155; o LLM concorda em 122 (113 total + 9 parcial). 33 o regex marca e o LLM diz `nao`; 90 o LLM marca (55 total + 35 parcial) e o regex não. A validação manual decide.
- Amostra de validação: **151 conversas** (arredondamento da alocação; 13 com recusa prevista ⇒ IC largo para precisão da recusa).
- **Validação manual (12/11):** rótulos da pessoa em `data/work/validacao_v2/rotulos_labeled.csv` (feitos num mini-app no Claude do navegador, **às cegas**: o app não mostrava a previsão). `avaliar --rotulos <csv>`.
  - Nível usuário (2.219 elegíveis, 1ª conversa): recusa total LLM 106 (4,8%) → retorno 15,1% × 29,3%; regex 103 → 15,5%. Qualquer conversa da 1ª sessão: 133 → 21,1% (mistura engajamento). 21% dos usuários têm > 1 conversa na 1ª sessão; 43% desses mudam de grupo.
  - Tema, 11 temas: bruta 67,5% (IC 59,7–74,5%), **ponderada 71,4% (IC 64,4–78,5%)**. Acima do piso de 70%, abaixo da meta de 85%. Precisão: saudacao_teste e traducao_reescrita 100%; roleplay 90%; conhecimento_geral 75%; estudo/trabalho/programação/criativo 56–60%; conselho 33%, adulto 38%, outro 40%. Confusões: estudo → conhecimento_geral (6), trabalho → estudo (5), conhecimento → conselho (4).
  - Tema em 7 grupos (conhecimento+estudo+trabalho = `tarefa_conhecimento`; criativo+roleplay+adulto = `criativo_entretenimento`): bruta 77,5%, **ponderada 83,8% (IC 78,9–88,7%)**. Grupos escolhidos depois de ver a matriz ⇒ leve otimismo.
  - Recusa: humano marcou 16 (5 total + 11 parcial). LLM `total`: precisão 8/9, recall 8/16, pega 5/5 das totais. Regex: precisão 8/9, recall 8/16, pega 4/5. LLM parcial+total: 9/13 e 9/16. "Parcial" humana quase nunca é detectada (7 de 11 → `nao`).

**EDA da 1ª experiência (13/11, `analysis/02_eda.ipynb`; tudo bruto, IC de Wilson, 2.219 elegíveis)**
- **Quando volta:** 94% dos retornos em 30 dias caem em 7 dias; 55% dos retornos em 7 dias acontecem em até 6 h (15,7% dos novatos). Base: 2.043 observáveis por 30 dias.
- **Recusa total na 1ª conversa:** 15,1% (IC 9,5–23,1%, n = 106) × 29,3% sem. Quase nunca em saudação (1 de 106).
- **Tema:** saudação 21,9% (n = 516, 23% dos novatos); tradução 40% (n = 110); conselho 47% (n = 49); tarefa 29%; programação 28%; criativo 32%. Resposta no 1º quartil (≤ 119 caracteres) 22%, e 80% dela responde a uma saudação.
- **Perfil:** idioma "outro" 19% (54% é saudação ⇒ ruído do detector); madrugada 21,6%, manhã 32,6%; celular 25,2% × desktop 30,2%; dia útil ≈ fim de semana.
- **Volume da 1ª sessão:** 1 resposta 23%, 10 ou mais 52%; 3+ conversas 45%. É engajamento ⇒ **fora do modelo principal do 04** (mediador da recusa); entra como sensibilidade.
- **Rio de Janeiro:** 17,5% (IC 13,4–22,6%, n = 257), baixo no desktop (19%) e no celular (16%); 55% celular × 29% no resto. O UA raro reaparece em outro IP em 7 dias 2–3× mais no RJ (2,6%/5,6% × 0,8%/2,5%) ⇒ hipótese de medição (IP dinâmico); estado = controle; registrado no risco 1. Maranhão 48% (n = 42) também fora do IC; 19 estados ⇒ pode ser acaso.
- **Modelo:** 28,4% (GPT-3.5) × 28,9% (GPT-4) bruto. Meses com os dois (10–90% de GPT-4): 04, 05, 06, 11, 12/2023 e 01/2024 ⇒ 28,1% × 30,1%, IC sobreposto. O 04 compara dentro do mesmo mês (mês como controle).

**Efeitos e confusão (13/11, `analysis/04_efeitos_e_confusao.ipynb`; regressão linear, IC robusto HC1; n = 2.219; estado e mês como controles)**
- **Recusa total: −17,4 p.p. (IC −25,4 a −9,4)**, bruto −14,2 (o ajuste aumenta: a recusa quase nunca cai em saudação, que já volta menos). Resiste: + volume −15,5; regex −15,8; logística −16,2 (IC −22,9 a −9,4); sessão inteira −10,0 (dilui, como o BDR-010 previu). O volume quase não muda o efeito ⇒ a recusa não age só por encurtar a sessão.
- **Com IC fora do zero:** conselho pessoal +17,1 (2,9 a 31,3; n = 49); manhã +5,3 (0,2 a 10,5) vs. tarde; idioma "outro" −8,0 (−13,9 a −2,1). **Cruzam o zero:** saudação −4,3 (bruto −7,3), resposta Q1 −5,2, celular −4,2 (−8,5 a 0,1), madrugada −3,9, tradução +8,2. 17 comparações ⇒ ~1 falso positivo esperado.
- **Saudação, resposta curta e idioma "outro" se sobrepõem:** o ajuste divide o efeito entre os três.
- **GPT-4, passo a passo:** bruto +0,6 (base) → +2,0 (6 meses com os dois) → **−1,0 dentro do mesmo mês** (média das diferenças mês a mês, pelo nº de novatos; ganha em 3 meses, perde em 3) → **−3,7 (IC −9,4 a +2,0)** com mês e perfil iguais (regressão). Sem evidência de ganho; a vantagem bruta era seleção (mês). A versão antiga (IPW nos 6 meses) dava −3,3 (IC −9,5 a +3,0).
- **Semana atípica (enunciado pede semana, não mês): 17/07/2023**, 9,1% (3/33); 24/07: 8,0% (2/25). Juntas: **8,6% (5/58; IC 3,7–18,6%)** × **28,6–29,8% esperados** por qualquer perfil (`taxa_esperada`: tema, dispositivo, idioma, horário, recusa, resposta, estado, tema+dispositivo+horário) ⇒ efeito do perfil < 1 p.p.; efeito da taxa ≈ −20 p.p. 6 de 55 semanas fora do IC (≈ 2,8 por acaso); as outras 4 têm n ≤ 11 ou 39. Perfil igual ao resto (saudação 21 × 23%, celular 24 × 32%); só GPT-3.5 no período. **Resto do mundo (definição simplificada: IP, 1h–7d) fica em ~20%**, igual às vizinhas; o volume global cai 31% a partir de 20/07 (2.825 → 1.947/dia), mas o retorno global não acompanha ⇒ queda **local do Brasil**, causa não identificável. Hipótese: recesso escolar de julho (fraca: janeiro teve o movimento oposto).

**Arquitetura e escopo (13/11, ADR-006 e PROJECT.md §14)**
- **Glue:** o tipo **Python Shell** é um processo Python agendado e gerenciado (0,0625 DPU ≈ 1 GB, cobrado por segundo); o tipo **Spark** é cluster. Para 22 MB, Spark é desproporcional ⇒ Python Shell. Duas frições a tratar: o runtime do Python Shell fica atrás do Python 3.13 local (bibliotecas extras por `--additional-python-modules`), e gravar num RDS em subnet privada exige uma **Glue Connection** com VPC, subnet e SG.
- **Custo da arquitetura:** ≈ **US$ 70/mês** (Fargate ~36 + ALB ~17 + RDS ~14 + resto ~4). Fargate e ALB = 76% do total ⇒ desligar a tarefa fora do horário comercial corta quase metade. Os preços unitários são **premissa**, não cotação conferida; refazer no Pricing Calculator antes de citar.
- **Equivalência conferida (12/11):** o `etl/prompts/classificacao_v2.md` em disco é idêntico, caractere a caractere, à mensagem de sistema do `entrada.jsonl` da rodada real, e o `SCHEMA` também. Só o rótulo do schema mudou de nome (metadado; o llama.cpp monta a gramática a partir do campo `schema`). Comando da conferência no §11 do `METODOLOGIA_LABEL.md`.
- **Dependências:** `statsmodels` é usada por `etl/efeitos.py`; `scipy` e `patsy` ficam fixadas como dependências dele (declaradas em 13/11). **Sem uso:** `scikit-learn` e `user-agents` (dispositivo por SQL).

**Construção (14/11)**
- **Colima compartilha só a pasta pessoal** com os containers. Volume de `/tmp` (ex.: scratchpad) aparece vazio: a etapa `classificacao` para com "falta a classificação". Teste do zero = cópia em `data/work/` (fora do git). Nesta máquina: `docker-compose` (não `docker compose`); Colima com 4 CPUs e 3 GB.
- Tempos: carga ~1,5 s; consulta mais pesada da API (semana × tema) ~15 ms; 1º `up` do zero ~4 min (download de 3,3 GB).
- Flask 3: ordem das chaves do JSON por `app.json.sort_keys = False` (o `JSON_SORT_KEYS` não vale mais). Marshmallow 4: `load_default`.
- Screenshot do Streamlit: o Chrome headless fotografa antes de renderizar. Use Playwright (no `.venv`, fora dos requirements) com `channel="chrome"` e espere `canvas.marks`/`svg.marks`; janela alta, porque o Streamlit rola por dentro.
- O `user-data` da EC2 sobe com o Qwen3-4B; a etapa troca para o 8B (`classificacao.sh modelo qwen3_8b`).

## Status
- **10/11 (Dia 1):** repo estruturado; `.venv`; bruta baixada e verificada; recorte Brasil; contagens iniciais; ADR-002/004/010; dúvidas rascunhadas.
- **11/11 (Dia 2, madrugada):** `.env` + IAM em `infra/aws/iam/`; padrão ASD-STE100; ADRs enxutos; BDR-007.
- **11/11 (Dia 2):** enunciado lido e extraído; classificador pronto (prompt v1, regex de recusa) e testado até a chamada no Bedrock (barrado pela conta); `etl/definicoes.py` + `etl/estatistica.py` + 10 testes passando; notebooks `01_discovery` e `03_definicoes_sensibilidade` executados; BDR-001 a 006 e 008 escritos; ADR-003 proposto; `docs/RISCOS.md` iniciado. Nada commitado.
- **12/11 (Dia 3, manhã):** AWS — plano migrado para pago e verificado; bucket + role criados; `.env` completo; batch barrado pela conta (caso no Support). PROJECT.md auditado contra o repo: 12 trechos vencidos corrigidos (estrutura §3.2 com os arquivos reais e a descrição de cada um; §4 trazia a escolha antiga de BDR-002/003/006; custo do Bedrock US$ 25–45 → ≈ US$ 9; coorte mensal, estado agrupado, sem `toxic`; 4 riscos novos; cronograma; 2 tabelas quebradas). Escrito `docs/METODOLOGIA.md`: origem de cada número, ADR × BDR, sensibilidade, IC de Wilson, cada query, notebook e teste. Funil e 2 números reconferidos. Notas da apresentação revisadas (§10 do METODOLOGIA). Commits `6e763d8` (dia 2) e `03977d5` (docs).
- **12/11 (Dia 3, tarde):** Support confirmou que o Bedrock não libera a tempo; teste mostrou 0 de cota em todos os modelos e 0 de GPU. Decisão (pessoa): LLM aberto em CPU numa EC2, escopo só 1ª sessão; pedido de GPU em paralelo. Feito: ADR-004 reescrito; `etl/classificar_cpu.py`, `etl/llm_runner.py`, `etl/validacao_classificacao.py`; `infra/aws/ec2/`; prompt v2; regex corrigido; 28 testes. Ajuste em 2 rodadas → Qwen3-8B + v2; rodada completa concluída (0 erros) → `data/enriched/temas_v2_qwen3_8b.parquet`; EC2 destruída; amostra de validação gerada.
- **12/11 (Dia 3, noite):** simplificação. O Bedrock saiu do código e dos documentos: `etl/classify_bedrock.py` virou `etl/classificacao.py` (base compartilhada) + caminho único da EC2; a indireção do prompt ("linha da ferramenta") saiu, e o prompt v2 em disco é agora idêntico ao que foi enviado ao modelo; o ADR-004 foi reescrito como a decisão original, com o Bedrock como opção descartada, e o ADR-011 deixou de existir. Políticas IAM de batch apagadas (a role segue na conta, sem uso); `usuario-acaso-etl.json` caiu de 5 blocos para 2, só S3; `ACASO_BEDROCK_ROLE_ARN` saiu do `.env.example`. O `boto3` fica: o S3 é o canal da EC2. `docs/METODOLOGIA_LABEL.md` documenta a etapa de rotulagem e lista a mudança arquivo por arquivo. **Conferido:** prompt e schema idênticos aos da rodada real, validação reavaliada com os mesmos números (71,4% e 83,8%), `preparar` de ponta a ponta, 29 testes e `ruff` limpo. Nada commitado.
- **13/11 (Dia 4):** escopo reduzido (PROJECT.md §14): fora a tela de Saúde e a reconciliação automática, a tela 3, o cache em Redis, 2 endpoints, `INDICADORES.md`, `MONITORAMENTO.md` e 3 ADRs (~8 h). Ficam 2 telas e 4 endpoints. Escritos `docs/ARQUITETURA.md` (diagrama, 6 serviços, local × produção, custo ≈ US$ 70/mês, o que ficou de fora) e o **ADR-006**; o ADR-010 foi alinhado (em produção, DuckDB roda no Glue Python Shell); os indicadores viraram o **§11 do METODOLOGIA**; o índice de ADRs diz onde cada decisão cortada ficou. Cronograma refeito: 13/11 análise, 14/11 construção, 15/11 incidente e docs, 16/11 revisão e envio.
- **13/11 (Dia 3 concluído):** branch `dia-3`. Commit `71ed97a`: só `data/enriched/temas_v2_qwen3_8b.parquet` vai para o git; `data/raw/` inteiro ignorado (o compose baixa e gera do zero). ADR-010 (linhagem no METODOLOGIA, não em `INDICADORES.md`), PROJECT.md §3.2 e índices de ADR alinhados. Feitos `etl/primeira_experiencia.py` + 4 testes (33 passando, `ruff` limpo) e `analysis/02_eda` (6 gráficos, cada um com conclusão; tabela final = o que entra no 04). `estilo.py`: grade atrás das barras. METODOLOGIA (§5, §6, §8), RISCOS (risco 1: caso do Rio) e PROJECT.md atualizados. Commits `71ed97a` (parquet) e `8a469c6` (fim do Dia 3).
- **13/11 (Dia 4):** Seção de dúvidas removida (esclarecidas em 11/11); compose reaproveita `./data` como volume. Feitos `etl/efeitos.py` + 3 testes (36 passando) e `analysis/04_efeitos_e_confusao` (gráficos: forest plot bruto × ajustado e coorte semanal; seções de sensibilidade, semana atípica, prova × não prova, candidatos aos 3 achados e a tabela `resultado_efeitos`). `scipy` e `patsy` declarados. Conclusão da semana corrigida antes do fechamento: o resto do mundo não caiu junto. METODOLOGIA (§5, §6, §8), RISCOS (risco 5), PROJECT.md atualizados. **Depois, a pedido da pessoa, o método foi simplificado** (regressão linear, GPT-4 no mesmo mês, taxa esperada pelo perfil; sem AME, delta, bootstrap nem IPW) e conferido contra a versão antiga: nenhuma conclusão mudou. Glossário de 10 termos (novato e n entraram depois de 2 dúvidas da pessoa) e roteiro de 4 frases no METODOLOGIA §5. Dia 4 commitado; `dia-3` e `dia-4` mescladas na `main` (13/11). Daqui em diante, tudo na `main`.
- **14/11 (Dia 5):** construção. Decisões da pessoa registradas na tabela (views SQL, 4 tabelas, k=20 mantido, Alembic, compose com etapa da EC2, IAM `acaso-operador` + `acaso-limite`, um commit no fim). Feitos: `docker-compose.yml` (6 serviços), `etl/Dockerfile`, `db/` (Alembic 0001 tabelas + papel `acaso_leitura`; 0002 Wilson, `k_minimo`, `amostra_suficiente`, `vw_retorno_coorte`, `vw_novato_dimensao`), `etl/carga.py`, `etl/etapa_classificacao.sh` + `etl/conferir_classificacao.py`, `backend/` (4 endpoints, `meta`, log JSON, gunicorn), `frontend/` (2 telas em Altair), políticas IAM e `classificacao.sh` adaptado (sem `unset` das credenciais, tag no SG e no volume, role com limite). **Conferido:** carga = notebook 04 (2.219 / 635 / 28,6%; recusa −17,4, IC −25,4 a −9,4; rejeitadas 76/48/87); 59 testes com banco (43 + 16 pulados sem banco); `ruff` limpo; `docker-compose up` do zero numa pasta limpa, sem `.env` (download de 3,3 GB → carga #1 → telas); screenshots das 2 telas revisados (3 defeitos corrigidos). Nada commitado.

## Pendências que dependem da pessoa
- Bedrock: os casos de cota seguem abertos; nada a fazer para o desafio.
- Preencher as horas de cada dia em `docs/USO_DE_IA.md` (hoje `_preencher_`). O desafio pede o total.
- Decidir se `user-agents` e `scikit-learn` saem do `requirements-analysis.txt` (as duas sem uso).
- Criar o usuário IAM `acaso-operador` e as políticas `acaso-limite` e `acaso-operador` (`infra/aws/iam/README.md`) e preencher o `.env`. Depois, o Claude testa as políticas (Policy Simulator ou `criar`/`destruir` com confirmação). Ponto de atenção: `AddRoleToInstanceProfile` com a condição `iam:PassedToService`.
- Commit do Dia 5 (um só, quando a pessoa pedir). Inclui `tests/snapshots/openapi.json`.
- ADR-001 (Postgres) e ADR-007 (privacidade) ficaram para 15/11, de meia página cada. Se o tempo apertar, viram seção do `RELATORIO.md`.
- Pronto, sem ação: AWS Budgets ("My Monthly Cost Budget", US$ 20/mês) e plano pago.

## Próximos passos
1. ~~`primeira_experiencia.py` + `02_eda`~~ feitos (13/11).
2. ~~`04_efeitos_e_confusao`~~ feito (13/11). Ficou: regressão linear com recusa total, tema (referência = tarefa), faixa horária, dispositivo, idioma, quartil da resposta e modelo, estado e mês como controles, **sem** o volume da sessão; bruto × ajustado; GPT-4 no mesmo mês; sensibilidade com volume, regex, sessão inteira e logística; **semana atípica** (17/07/2023; perfil × taxa).
3. ~~Construção (14/11)~~ feita: compose do zero, carga, API, 2 telas.
4. **15/11:** incidente §4.2 com teste de regressão, `INCIDENTE.md`, ADR-001 e ADR-007, `RELATORIO.md`.
