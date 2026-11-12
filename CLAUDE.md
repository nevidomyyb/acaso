# Memória do projeto — Desafio Técnico Acaso (retenção de assistente de IA, WildChat-1M Brasil)

> Memória persistente do projeto, carregada em toda sessão. Plano e escopo: [PROJECT.md](PROJECT.md).
> **Ao fim de cada sessão:** atualize "Status", "Pendências" e "Próximos passos". Registre fatos novos em
> "Fatos dos dados". Acrescente a linha do dia em [docs/USO_DE_IA.md](docs/USO_DE_IA.md), com horas.

## Contexto
- Pergunta: **o que faz quem experimentou o assistente voltar em até 7 dias?** Quanto pesa cada fator (com IC)? Quanto é causa e quanto é seleção?
- Cliente de negócio, sem perfil técnico. O resultado é um **dashboard**. Cada número tem definição, fonte e IC.
- Entrega: **seg 16/11/2026 23h59** (meta: ~20h). Dúvidas até **qua 11/11** ([docs/DUVIDAS.md](docs/DUVIDAS.md)). A pessoa candidata envia os e-mails, não o Claude.
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
5. Infra e custo na **AWS** (LLM = **Amazon Bedrock**). A entrega roda local; a implantação fica descrita.
6. A base analítica **não** tem texto das conversas, `hashed_ip`, user-agent completo nem identificador exibível. k-anonimato (k=20) nos recortes.
7. Toda premissa registrada **+ o que muda se estiver errada**. ADRs em `docs/adr/`, BDRs em `docs/bdr/` (índices em `README.md` de cada pasta).
8. Parágrafo final de uso de IA: ferramentas, o que foi conferido/corrigido/descartado e **horas**.

## Decisões tomadas (não reabrir sem fato novo)
| Item | Decisão | Status |
|---|---|---|
| ADR-002 backend | Flask + flask-smorest, gunicorn, Swagger em `/docs` | aceito |
| ADR-004 classificação | Bedrock **Haiku 4.5 em Batch** (decisão reafirmada em 11/11), via inference profile `us.anthropic.claude-haiku-4-5-20251001-v1:0`; resultado versionado em `data/enriched/`; o compose não chama o Bedrock | aceito |
| ADR-010 motor ETL | DuckDB (dbt adiado) | aceito |
| BDR-007 filtro | Só `country = 'Brazil'`. Alternativa rejeitada: `OR language = 'Portuguese'` (traria Portugal, Moçambique etc. e foge da restrição) | aceito |
| ADR-003 frontend | **Streamlit com tema próprio** (`.streamlit/config.toml` + CSS), lendo **só a API**; gráficos em Altair com a paleta da análise; ECS Fargate na AWS | aceito (11/11) |
| BDR-001 usuário | `hashed_ip` (IP+UA dá +2,2 p.p.; IP compartilhado −0,1 p.p.) | aceito |
| BDR-002 sessão | atividade = **cada resposta do assistente** (pega quem continua conversa aberta; +4,3 p.p. vs só início de conversa); gap 30 min | aceito (confirmado pela pessoa 11/11) |
| BDR-003 1ª experiência | 1ª sessão, sem aquecimento (base começa em 09/04/2023) | aceito |
| BDR-004 retorno | nova sessão até 7×24h do início da 1ª | aceito |
| BDR-005 fuso | UTC armazenado; agrupa em `America/Sao_Paulo` | aceito |
| BDR-006 período | tudo; tira censurados (48) e janela com falha de coleta (87); falha = volume global < 15% da mediana | aceito (confirmado pela pessoa 11/11) |
| BDR-008 uso | conversa com ≥ 1 mensagem não vazia (76 saem) | aceito |
| Visão do dashboard | coorte **mensal** principal; semanal como detalhe; esmaecer se IC > ±10 p.p. (~80 pessoas) | decidido 11/11 |

## Convenções
- Idioma: documentação, nomes de domínio (tabelas/colunas) e comentários em **português**.
- Python local: `.venv/` (Python 3.13, `python3 -m venv .venv`; não há `uv`). Rode com `.venv/bin/python`. Dependências fixadas em `requirements-analysis.txt`. Lint: `ruff` (`ruff.toml`, linha 120).
- Base bruta completa: `data/raw/wildchat-1m/` (gitignored, 3,36 GB), baixada por `etl/download.py` (SHA-256 + `manifest.json`).
- Recorte Brasil: `data/raw/wildchat_br.parquet` (+ `.manifest.json`), exatamente `country = 'Brazil'`, gerado por `etl/recorte_brasil.py`. É a "base bruta" que a carga do compose lê. 22 MB: vai para o git.
- Contagens rápidas: `.venv/bin/python analysis/00_contagens_iniciais.py`.
- **Definições = `etl/definicoes.py`** (fonte única: carga, notebooks e testes). `Definicoes()` = padrão aceito; cada campo cita o BDR. Mudou um padrão → mude `VERSAO_DEFINICOES`, rode `pytest` e o notebook 03. `construir(con, bruta, d, volume_diario=...)` cria `conversas → eventos → eventos_sessao → sessoes → usuarios`; `elegiveis(u, d)` = denominador.
- Volume diário global: `data/raw/wildchat_volume_diario.parquet` (gerado pelo recorte) → detecta falha de coleta.
- Testes: `.venv/bin/python -m pytest -q` (base sintética em `tests/conftest.py`). Lint: `.venv/bin/ruff check analysis etl tests`.
- **Notebooks:** fonte = `analysis/NN_*.py` (jupytext, formato percent); gerar/executar com `cd analysis && ../.venv/bin/jupytext --to ipynb --execute NN_x.py`. Estilo dos gráficos em `analysis/estilo.py` (paleta da skill dataviz; rodapé com fonte via `nota()`). Sempre olhar os PNGs gerados antes de concluir.
- Classificação: `etl/classify_bedrock.py {amostra|preparar-batch|enviar-batch|status|coletar}`; prompt em `etl/prompts/classificacao_v1.md`; regex de recusa em `etl/recusa_regex.py`. Usa **boto3** (mesmo corpo no on-demand e no batch).
- Enunciado original: PDF em `docs/` e texto em `docs/desafio/enunciado.txt` (grep-ável).
- Início da conversa = timestamp da **1ª resposta do assistente** (`list_min` dos timestamps dos turnos), nunca o `timestamp` de topo.
- Máquina: 15 GB RAM (≈ 6 GB livres), 12 núcleos. DuckDB com `memory_limit` explícito e `SET TimeZone='UTC'`.
- **Segredos:** `.env` (gitignored, `chmod 600`) tem `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (preenchidos em 11/11) e `ACASO_S3_BUCKET`, `ACASO_BEDROCK_ROLE_ARN` (vazios até a pessoa criar). Modelo em `.env.example`. No compose, use `env_file: [{path: .env, required: false}]` para subir sem o arquivo. Nunca leia nem imprima os valores do `.env` (para checar, mascare: `awk -F= ...`).
- **AWS:** políticas IAM de menor privilégio em `infra/aws/iam/` (usuário `acaso-etl` + role `AmazonBedrock-acaso-batch`; bucket `acaso-desafio-tecnico`). Não crie recursos AWS (Budgets, S3, jobs) sem confirmação explícita da pessoa.
- Commits só quando a pessoa pedir; branch a partir de `main`.

## Fatos dos dados (manter atualizado)
**Fonte**
- Hugging Face `allenai/WildChat-1M`, revisão `7d6490e462285cf85d91eabea0f9a954fbddcd1f` (2024-10-17), licença ODC-BY, sem gate. 14 parquets, 3,36 GB, 837.989 conversas, 178.724 `hashed_ip`, 201 países.
- A versão pública tem **só conversas não tóxicas** (tóxicas removidas em 2024-07-22; PII sensível em 2024-10-17). ⇒ `toxic` = 0 no Brasil (fator inutilizável). A remoção cria buracos no histórico: um retorno tóxico some e o retorno fica subestimado. Registrar como risco.

**Schema e semântica**
- `conversation_hash` **não é único** (11.621 conversas BR, 11.555 hashes). Chave: `conversation[1].turn_identifier` (único no BR).
- `timestamp` de topo = último turno (UTC). **Turnos do usuário nunca têm timestamp** (0 de 26.579). Turnos do assistente sempre têm.
- Turnos do usuário têm `hashed_ip`, `country`, `state`, `header`. Os do assistente não. `header` é igual em todos os turnos da conversa.
- DuckDB 2.0: lambda com sintaxe `lambda c: c.campo`. A seta `->` dá erro.

**Brasil (`country = 'Brazil'`)** — medido em 10/11 com `analysis/00_contagens_iniciais.py`
- **11.621 conversas, 2.385 `hashed_ip`** (1,4% da base), 2023-04-09 → 2024-04-29 (57 semanas).
- **Base pequena:** mediana de **41 novos IPs/semana** (mín. 9, máx. 100) ⇒ visão principal **mensal**; semanal só como detalhe.
- 1.424 de 2.385 usuários (60%) têm **uma única conversa**.
- **Concentração:** top 1% dos IPs (≥ 44 conversas) = 42% das conversas. 1 IP tem **1.557 conversas e 35 user-agents** (13% do BR). Precisa de regra de exclusão/flag.
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
- **28,6% (IC 26,8–30,5%)**, denominador 2.219 (2.354 usuários → 2.306 observáveis → 2.219 sem falha de coleta), 635 voltaram.
- Sensibilidade (Δ p.p.): gap 15 min +5,4 · gap 60 min −3,5 · retorno "outro dia" −9,7 · atividade por conversa −4,3 · IP+UA +2,2 · retorno > 1h −1,6 · aquecimento 2/4 sem −0,4/−0,8 · demais ≤ 0,2. "Referência do incidente" (IP+UA, conversa, > 1h) = 26,0%.
- IC médio: semanal ±15 p.p. (mediana 39 pessoas/semana); mensal ±7 p.p. Meses fora do padrão: abr/2023 40,3% (lançamento) e jan/2024 41,5% (n = 53, férias) ⇒ candidatos para o notebook 05 (mix × taxa).

**Incidente (§4.2 do desafio — texto em `docs/desafio/enunciado.txt`)**
- Dashboard (endpoint `/api/retencao/coortes`): 06/11 1.210/375 · 13/11 1.188/368 · **20/11 2.034/366** (31% → 18%). Relatório por `hashed_ip`: 1.150/345 · 1.131/351 · 1.172/352 (estável ~30%). Semanas anteriores: dashboard ~5% acima.
- Código de referência — carga diária: `usuario_id = sha256(hashed_ip|user-agent)`, `ultimo_turno = c["timestamp"]`, `conversa_id = conversation[0].turn_identifier`, `INSERT ... ON CONFLICT (conversa_id) DO NOTHING`. Endpoint: `min(ultimo_turno)` como `primeira_vez`; `date_trunc('week', ...)` sem fuso; retorno `ultimo_turno > primeira_vez + 1h AND <= +7d`; o EXISTS do retorno não filtra `pais`.
- Leitura: novos quase dobram e retornos ficam estáveis ⇒ ~860 "novos" que **não voltam** ⇒ chaves novas para pessoas antigas que não se repetem (ex.: user-agent que passa a variar por conversa, ou UA nulo/alterado). Confirmar com: UAs distintos por IP por semana; % das chaves novas cujo `hashed_ip` já existia.
- Os números não aparecem nos dados públicos (BR 20/11: 61 novos no padrão; global 5.355) ⇒ são ilustrativos; demonstrar o **mecanismo** com dados reais.

**Bedrock (verificado em 11/11 na documentação AWS e por consulta somente leitura)**
- Haiku 4.5 e Haiku 5.5 ativos em us-east-1. O batch do Haiku 4.5 só aceita **inference profile** (`us.` → us-east-1, us-east-2, us-west-2).
- **Mínimo de 100 registros por job** de batch. Em produção (~41 novos/semana) não passa: acumule 3 semanas ou use on-demand no incremental.
- **Bloqueio em 11/11:** `InvokeModel` → `ResourceNotFoundException: Model use case details have not been submitted`. A conta precisa enviar o formulário de caso de uso da Anthropic (console do Bedrock, conta admin).
- Custo: todas as 11.621 conversas BR ≈ US$ 9 em batch (decisão de 11/11: classificar **todas**).
- **Cotas on-demand zeradas (11/11):** depois do formulário, o playground deu `ThrottlingException: Too many tokens per day`. Service Quotas mostra **0** em RPM/TPM de todos os modelos (Haiku 4.5, Haiku 5.5, Sonnet 4.6, Nova), contra o padrão AWS de 10.000 RPM / 5M TPM no Haiku 4.5 ⇒ restrição de conta nova; trocar de modelo não resolve. Cotas de **batch** não estão zeradas (100k registros/job, 100 jobs). Códigos: `L-CCA5DF70` (RPM cross-region Haiku 4.5), `L-58BE175A` (TPM cross-region Haiku 4.5). Cotas "tokens per day" não são ajustáveis pelo Service Quotas ⇒ caso no AWS Support.
- Ajuste de prompt **via batch**: `classify_bedrock.py --amostra-n 200 {preparar-batch|enviar-batch|status|coletar}` (199 registros, ≈ 245k tokens, ≈ US$ 0,15) → `data/enriched/amostra_v1.parquet`. Entrada já preparada em `data/work/batch_v1_amostra200/`.
- **Causa provável (11/11):** conta no **plano FREE** (`aws freetier get-account-plan-state`): US$ 146,34 de créditos, expira em 19/12/2026. O plano gratuito exclui ofertas do Marketplace que consomem créditos (Claude no Bedrock é Marketplace). Decisão da pessoa: **migrar para o plano pago** (créditos continuam; classificação ≈ US$ 9 sai dos créditos). Depois: rechecar cotas; se seguirem em 0, caso no AWS Support. Alternativas avaliadas e descartadas por prazo/qualidade: EC2 ou SageMaker com modelo aberto; Comprehend (não cobre a taxonomia nem recusa).
- **Plano pago (11/11, tarde):** conta migrada para **PAID** (créditos mantidos, US$ 146,34). Modelo `AUTHORIZED`/`AVAILABLE`, mas o on-demand segue com `Too many tokens per day` e as cotas RPM/TPM seguem em 0. Os 2 pedidos de aumento da manhã (antes da migração) fecharam (`CASE_CLOSED`) sem aumento. **Novos pedidos enviados à tarde** (10.000 RPM e 5M TPM): `PENDING`.
- **Batch também bloqueado (11/11):** `CreateModelInvocationJob` → `ValidationException: Your account is not authorized to perform this action. Please create a support case`. Restrição da conta, não do IAM nem da cota. Só o AWS Support libera. O upload da entrada no S3 funcionou.
- **Recursos criados pela pessoa (11/11):** bucket `acaso-desafio-tecnico` (us-east-1, acesso público bloqueado) e role **`AmazonBedrock-acaso-batch`** (nome com `AmazonBedrock` porque a política gerenciada só permite `iam:PassRole` para esse padrão). Corrigi um `<BUCKET>` não trocado na política inline da role. `.env` preenchido.
- **IAM real ≠ documentado:** o `acaso-etl` usa `AmazonS3FullAccess` + `AmazonBedrockFullAccess` (gerenciadas) na conta de desenvolvimento. A política inline de `infra/aws/iam/` é o alvo de menor privilégio.
- Pedido de aumento de cota: o Service Quotas recusa valor abaixo do padrão AWS (`IllegalArgumentException`). Mínimo = 10.000 RPM (`L-CCA5DF70`) e 5.000.000 TPM (`L-58BE175A`).
- Consultas de plano e cotas: use o perfil padrão do AWS CLI (administrador), sem carregar o `.env`. O `acaso-etl` não tem `freetier:*` nem `servicequotas:*`.
- Contingência se nada liberar até sáb 14/11: classificador por palavras-chave + `recusa_regex` (PROJECT.md §12), registrado no ADR-004 e nos RISCOS.

## Status
- **10/11 (Dia 1):** repo estruturado; `.venv`; bruta baixada e verificada; recorte Brasil; contagens iniciais; ADR-002/004/010; dúvidas rascunhadas.
- **11/11 (Dia 2, madrugada):** `.env` + IAM em `infra/aws/iam/`; padrão ASD-STE100; ADRs enxutos; BDR-007.
- **11/11 (Dia 2):** enunciado lido e extraído; classificador pronto (`etl/classify_bedrock.py`, prompt v1, regex de recusa) e testado até a chamada (bloqueado pelo formulário da Anthropic); `etl/definicoes.py` + `etl/estatistica.py` + 10 testes passando; notebooks `01_discovery` e `03_definicoes_sensibilidade` executados; BDR-001 a 006 e 008 escritos; ADR-003 proposto; `docs/RISCOS.md` iniciado. Nada commitado.

## Pendências que dependem da pessoa
- **Bedrock — caso no AWS Support (urgente):** os 2 pedidos de cota abriram casos (`CASE_OPENED`, 11/11 tarde). Responder num deles pedindo também a liberação do batch (texto sugerido no chat de 11/11). Se liberar: `classify_bedrock.py --amostra-n 200 enviar-batch` (entrada pronta).
- AWS Budgets: existe ("My Monthly Cost Budget", US$ 20/mês).
- Validação manual da classificação: rotular ~150 conversas (amostra gerada após o batch).
- Enviar as dúvidas (qua 11/11). Pedir o primeiro commit quando quiser.

## Próximos passos
1. Quando o Bedrock liberar: `classify_bedrock.py amostra --n 200` → revisar → ajustar prompt (máx. 2 rodadas) → `preparar-batch` → `enviar-batch` → `status` → `coletar` → BDR-009/010 + amostra de validação.
2. Dia 3: tabela `primeira_experiencia` (features da 1ª sessão: modelo, tema, recusa, turnos, tamanho de resposta, horário/dia local, idioma 3 níveis, dispositivo, estado agrupado) em `etl/` + `analysis/02_eda` (só gráficos com conclusão).
3. Dia 4: `04_efeitos_e_confusao` (logística + efeito marginal em p.p. com IC; IPW para GPT-4 só nos períodos com os dois modelos; bruto × ajustado) e `05_semana_atipica` (mix × taxa; abr/2023 e jan/2024; falhas de coleta).
4. Dia 5: Postgres + carga + Flask-smorest + Streamlit com tema (ADR-003).
