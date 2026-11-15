# Metodologia da rotulagem — tema e recusa da 1ª experiência

Este documento cobre a etapa que gera dois fatores da análise: o **tema** do primeiro pedido e a **recusa** do
assistente na primeira resposta. Ele explica o desenho, a execução, a validação e os limites. A §11 lista a
simplificação de 12/11, arquivo por arquivo.

- Decisão de ferramenta: [adr/ADR-004-classificacao-llm-aberto-ec2.md](adr/ADR-004-classificacao-llm-aberto-ec2.md).
- Decisões de leitura: [bdr/BDR-009-tema.md](bdr/BDR-009-tema.md) e [bdr/BDR-010-recusa.md](bdr/BDR-010-recusa.md).
- Origem dos outros números: [METODOLOGIA.md](METODOLOGIA.md).

---

## 1. O que a etapa produz

Um arquivo: `data/enriched/temas_v2_qwen3_8b.parquet`, com **3.361 linhas**, uma por conversa da 1ª sessão de
cada usuário. Colunas: `conversa_id`, `tema`, `recusa`, `confianca`, `motivo`, `recusa_regex`, `fonte`,
`modelo`, `versao_prompt`, `input_tokens`, `output_tokens`, `erro`, `segundos`.

O arquivo vai para o git. A carga do `docker compose up` lê esse parquet e **nunca chama um LLM**.

**Escopo:** só a 1ª sessão de cada usuário, e não as 11.621 conversas do Brasil. A pergunta do desafio é sobre a
estreia. Em CPU, a base inteira levaria ~20 h, contra ~6 h.

---

## 2. As peças

| Arquivo | O que faz |
|---|---|
| [../etl/classificacao.py](../etl/classificacao.py) | Fonte única: taxonomia, texto de entrada, schema de saída e validação |
| [../etl/prompts/classificacao_v2.md](../etl/prompts/classificacao_v2.md) | O prompt de sistema, versionado |
| [../etl/classificar_cpu.py](../etl/classificar_cpu.py) | Local: seleciona as conversas, monta as requisições, envia ao S3 e coleta |
| [../etl/llm_runner.py](../etl/llm_runner.py) | Na EC2: chama o llama-server, grava uma linha por conversa, retoma de onde parou |
| [../infra/aws/ec2/](../infra/aws/ec2/) | Cria, acompanha e destrói a EC2; acesso só por SSM |
| [../etl/recusa_regex.py](../etl/recusa_regex.py) | Detecta recusa por regex PT/EN: checagem cruzada |
| [../etl/validacao_classificacao.py](../etl/validacao_classificacao.py) | Amostra para rótulo manual e acurácia ponderada |

---

## 3. Quem roda o modelo

Duas peças com nomes parecidos, e uma confusão comum:

| Peça | O que é |
|---|---|
| **llama.cpp** | O motor de inferência, na tag `v0.9.0`. Entrega o binário `llama-server`, com API compatível com a OpenAI |
| **Qwen3-8B Q4_K_M** | Os pesos, o único modelo usado. Licença Apache 2.0 |

Nenhum modelo Llama entra no projeto. O nome aparece só porque o motor se chama llama.cpp.

A instância é uma `c7i.4xlarge` (16 vCPU, 32 GB), Ubuntu 24.04, com o modelo servido em `127.0.0.1:8080`. O
repositório, a revisão e o SHA-256 de cada modelo ficam fixados em
[../infra/aws/ec2/classificacao.sh](../infra/aws/ec2/classificacao.sh). O boot confere o hash antes de subir o
serviço.

**Segurança e custo:** o security group não tem regra de entrada, e o acesso é só por SSM. A instância se
destrói sozinha pelo `shutdown`, porque o `shutdown-behavior` é `terminate`.

---

## 4. O prompt e a taxonomia

O prompt de sistema tem quatro partes: o papel, a regra contra injeção de instrução, os **11 temas** e os **3
níveis de recusa**. O texto da conversa chega como mensagem do usuário, entre marcas:

```
<mensagem_pessoa>…</mensagem_pessoa>
<resposta_assistente>…</resposta_assistente>
```

Os limites são 2.000 caracteres para a mensagem da pessoa e 1.500 para a resposta. A entrada truncada recebe a
marca ` [...truncado]`. A recusa aparece no começo da resposta, então o corte não a esconde.

**Temas:** `saudacao_teste`, `estudo_escola`, `trabalho_profissional`, `programacao_tecnologia`,
`traducao_reescrita`, `criativo_ficcao`, `roleplay_personagem`, `conteudo_adulto`, `conselho_pessoal`,
`conhecimento_geral`, `outro`.

**Recusa:** `nao`, `parcial`, `total`.

O prompt v2 acrescenta ao v1 duas regras de desempate de tema e três casos que são sempre `recusa = nao`. Elas
vieram dos erros da 1ª rodada de ajuste.

---

## 5. O fluxo de uma conversa

1. `classificar_cpu.py preparar` monta `entrada.jsonl`, com uma linha `{recordId, body}` por conversa. O
   `recordId` é o `conversa_id`.
2. `classificar_cpu.py enviar` sobe `entrada.jsonl` e `llm_runner.py` para o prefixo `cpu/` do bucket.
3. `classificacao.sh rodar` baixa os dois na instância e inicia o executor com `nohup`.
4. O executor usa 4 linhas de execução, igual ao `-np 4` do servidor. Cada conversa vai num POST para
   `/v1/chat/completions`, com `temperature = 0`, `max_tokens = 160` e `cache_prompt`.
5. Cada chamada tem **3 tentativas** e **300 s de prazo** por tentativa. Entre tentativas, espera 2 s, 4 s e 6 s.
6. O resultado vira uma linha em `saida.jsonl`, gravada na hora, sob trava. A cada 50 registros, o executor
   imprime o ritmo e copia a saída para o S3.
7. `classificar_cpu.py coletar` baixa a saída, interpreta cada linha e grava o parquet.

**Retomada:** o executor pula os `recordId` que já estão na saída sem erro. Se a instância cair, basta criar
outra, copiar a saída parcial do S3 e rodar de novo.

**Duas armadilhas resolvidas:**
- **U+2028 no texto.** O caractere aparece em 3 conversas. O `str.splitlines()` quebra a linha do JSONL nele e
  corta o JSON ao meio. A leitura usa `split("\n")`, e a gravação usa `ensure_ascii` no padrão.
- **AWS CLI por snap.** O 1º boot falhou porque a snap store não respondeu. O script passou a usar o
  instalador oficial em zip.

---

## 6. As cinco camadas de validação da saída

| # | Camada | Onde | O que faz |
|---|---|---|---|
| 1 | Gramática | `corpo_cpu` + `SCHEMA` | O llama.cpp só deixa o modelo gerar JSON que cabe no schema. Um tema fora da lista é impossível |
| 2 | Erro de chamada | `interpretar_cpu` | A linha com `erro` do executor passa adiante, com os tokens |
| 3 | JSON inválido | `interpretar_cpu` | `json.loads` dentro de `try`; a mensagem guarda o `finish_reason` |
| 4 | Campos | `validar` | `tema` e `recusa` nas listas; `confianca` entre 0 e 1 |
| 5 | Ausência | `montar` | Marca `"ausente na saída"` quem foi selecionado e não voltou |

A conversa com a 1ª mensagem vazia (bug do coletor, 43 casos) recebe `saudacao_teste` e `recusa = nao` por
regra, com `fonte = regra_vazio`. O modelo não é chamado.

Nada é reprocessado por conta própria. A linha inválida vai para o parquet com `erro` preenchido, e a análise a
descarta. **Na rodada real, 0 linhas com erro e 0 JSON inválido**, em 3.318 chamadas.

---

## 7. O regex de recusa

O regex **não** é uma etapa do classificador. Ele roda em toda linha e grava a coluna `recusa_regex`, paralela à
do modelo. O modelo nunca vê o regex, e o regex nunca corrige o modelo. Ele serve para dois fins: checagem
cruzada da BDR-010 e reserva, caso nenhum LLM esteja disponível.

São 9 padrões, 5 em português e 4 em inglês, numa única alternação, aplicada aos **400 primeiros caracteres**.
A resposta é um booleano: ele não separa recusa total de parcial.

**Onde ele erra:**
- **Falso positivo:** um pedido de esclarecimento com a forma da recusa ("não posso calcular sem a velocidade
  inicial, mas o método é…"). Também a recusa de uma parte, com o resto entregue.
- **Falso negativo:** formas fora da lista ("me recuso", "prefiro não", "não é permitido"), desvio de assunto
  sem negação, e recusa depois do caractere 400.

---

## 8. A validação manual

O desenho evita três erros comuns de medição.

1. **Amostra estratificada.** Um sorteio simples traria quase só temas comuns. A amostra garante um mínimo de 8
   casos por tema previsto, com o resto proporcional ao tamanho. Resultado: 151 conversas (o 1 extra vem do
   arredondamento).
2. **As 40 conversas do ajuste do prompt ficam fora.** Medir nelas inflaria a acurácia.
3. **Rótulo às cegas.** A pessoa leu cada conversa e escolheu o tema e a recusa sem ver a previsão do modelo. A
   rotulagem usou um mini-app, feito no Claude do navegador, que mostra a mensagem, a resposta e as listas de
   valores. O app não mostra a previsão.

Como a amostra é estratificada, a média simples superestima os temas raros. O número reportado é a **acurácia
ponderada**: Σ Wₕ·accₕ, com Wₕ = o peso de cada tema na base, e a variância Σ Wₕ²·p(1−p)/nₕ.

### Resultado

| Medida | Valor | IC 95% |
|---|---|---|
| Tema, 11 temas (bruta na amostra) | 67,5% | 59,7–74,5% |
| **Tema, 11 temas (ponderada)** | **71,4%** | 64,4–78,5% |
| **Tema, 7 grupos (ponderada)** | **83,8%** | 78,9–88,7% |
| Recusa, 3 níveis | 90,7% | 85,0–94,4% |

**Por tema previsto:** `saudacao_teste` e `traducao_reescrita` 100%; `roleplay_personagem` 90%;
`conhecimento_geral` 75%; `estudo_escola`, `trabalho_profissional`, `programacao_tecnologia` e `criativo_ficcao`
entre 56% e 60%; `outro` 40%; `conteudo_adulto` 38%; `conselho_pessoal` 33%.

**Para onde vão os erros:** estudo → conhecimento geral (6 casos), trabalho → estudo (5), conhecimento geral →
conselho (4). Os erros ficam entre temas vizinhos, e não entre temas distantes.

**Recusa.** A pessoa marcou 16 recusas: 5 totais e 11 parciais.

| Detector | Marcadas que são recusa | Totais achadas |
|---|---|---|
| LLM, `total` | 8 de 9 | 5 de 5 |
| LLM, `parcial` ou `total` | 9 de 13 | 5 de 5 |
| Regex | 8 de 9 | 4 de 5 |

A recusa **parcial** quase não é detectada: 7 das 11 viraram `nao`. Com 16 casos, estas proporções têm margem
larga.

---

## 9. O que a validação decidiu

- **BDR-009:** o fator do modelo usa **7 grupos**, não os 11 temas. `tarefa_conhecimento` junta conhecimento
  geral, estudo e trabalho. `criativo_entretenimento` junta criativo, roleplay e conteúdo adulto. Os 11 temas
  ficam nos gráficos descritivos, cada um com o seu acerto ao lado.
- **BDR-010:** o fator é **recusa total pelo LLM na 1ª conversa**. O regex e a sessão inteira entram como
  sensibilidade. A recusa parcial fica fora, porque nenhum dos dois detectores a enxerga.
- O tema e a recusa de cada usuário vêm da **1ª conversa** da 1ª sessão. Contar a sessão inteira mistura
  engajamento: quem abre mais conversas tem mais chance de levar recusa, e também volta mais.

O mapa dos grupos e a regra da recusa ficam em [../etl/definicoes.py](../etl/definicoes.py) (`GRUPO_TEMA` e
`RECUSA_FATOR`), com um teste que garante que todo tema tem grupo.

---

## 10. Limites conhecidos

1. **Os 7 grupos vieram depois de ver a matriz de confusão.** Por isso os 83,8% saem um pouco otimistas.
2. **Rótulo com erro aproxima de zero a diferença entre dois níveis de um fator.** Com 7 grupos, isso não vale
   para cada grupo. O efeito de um grupo pode ir nos dois sentidos.
3. **O campo `confianca` é inútil.** Ele sai quase constante (≈ 0,95) e não serve de filtro.
4. **O ajuste do prompt usou a leitura do Claude como referência**, em 40 conversas. A acurácia oficial vem só
   da validação humana.
5. **A acurácia de recusa repousa em 16 casos.** Qualquer leitura fina dela é frágil.

---

## 11. A simplificação de 12/11, arquivo por arquivo

O projeto nunca classificou nada no Bedrock: a conta nova tem cota 0 em todos os modelos. O código e os
documentos ainda tratavam o Bedrock como caminho principal. Esta rodada removeu esse caminho.

### Código

| Arquivo | Mudança |
|---|---|
| `etl/classificacao.py` | **Novo.** Taxonomia (`TEMAS`, `RECUSAS`), `SCHEMA`, `texto_entrada`, `validar`, `linha_resultado`, `regra_vazio`, `cliente_s3`, `bucket`, `carregar_entradas`, `resumir` |
| `etl/classify_bedrock.py` | **Apagado** (339 linhas). ~160 morreram: corpo de requisição do Bedrock, leitura de `tool_use`, os 4 subcomandos de batch, preço por token e o mínimo de 100 registros por job. O resto virou `classificacao.py` |
| `etl/classificar_cpu.py` | Importa de `classificacao`. Saíram `sistema_json`, `schema_json`, `LINHA_FERRAMENTA`, `LINHA_JSON` e a cópia do schema. Os padrões do CLI passaram a ser `--versao v2 --modelo qwen3_8b` |
| `etl/prompts/classificacao_v1.md` e `_v2.md` | A linha "registre com a ferramenta" virou "responda só com um objeto JSON". O v2 agora é, caractere a caractere, o prompt que foi enviado ao modelo |
| `etl/validacao_classificacao.py` | Importa de `classificacao`. Novo argumento `--rotulos`, para avaliar um CSV com outro nome |
| `etl/recusa_regex.py` | A docstring não cita mais o Bedrock |
| `etl/llm_runner.py` | Só o número do ADR |
| `analysis/00_contagens_iniciais.py` | O custo estimado deixou de usar o preço do Haiku. Agora usa 6,2 s por conversa e US$ 0,714/h de c7i.4xlarge |
| `tests/` | Imports; 2 testes reescritos (o prompt pede JSON; o schema vem de `classificacao`). **29 testes passando**, `ruff` limpo |

### Documentos

| Arquivo | Mudança |
|---|---|
| `docs/adr/ADR-004-classificacao-bedrock.md` | **Apagado** |
| `docs/adr/ADR-011-classificacao-cpu-ec2.md` | **Apagado** |
| `docs/adr/ADR-004-classificacao-llm-aberto-ec2.md` | **Novo.** A decisão original sobre classificação. O Bedrock entra como opção A, descartada pelos testes de 11 e 12/11 |
| `docs/adr/README.md` | Índice: uma linha de classificação, não duas |
| `docs/bdr/BDR-009`, `BDR-010` | Apontam para o ADR-004 |
| `docs/METODOLOGIA.md` | §1 (exemplo de ADR), §6 (script de contagens), §7 (texto e peça nova), §8 (custo medido: US$ 4,70) |
| `docs/RISCOS.md` | Riscos 10 e 11 reescritos sem o enquadramento de migração |
| `docs/DUVIDAS.md` | A dúvida 1 fala de LLM, não de Bedrock |
| `docs/USO_DE_IA.md` | **Só a seção "Como a IA é conferida".** O log de horas não foi tocado, de propósito |
| `PROJECT.md` | 22 trechos: checklist §2.2, stack, deploy, estrutura do repo, arquitetura, tabela de ADRs, riscos, §12 e cronograma. A §12.1 caiu de 45 para 22 linhas e passou a trazer o custo medido |
| `CLAUDE.md` | Regra 5, tabela de decisões, convenções de classificação, segredos, AWS e status. O bloco de fatos do Bedrock caiu de 20 para 9 linhas |
| `README.md` | O `.env` não é mais "para o Bedrock"; `infra/aws/ec2/` entrou no índice |

### Configuração e infra

| Arquivo | Mudança |
|---|---|
| `.env.example` | `ACASO_BEDROCK_ROLE_ARN` saiu. Ficaram as credenciais e `ACASO_S3_BUCKET` |
| `requirements-analysis.txt` | **Sem mudança.** O `boto3` continua, porque o S3 é o canal entre a máquina local e a EC2 |
| `infra/aws/iam/usuario-acaso-etl.json` | De 5 blocos para 2: só `s3:ListBucket`, `GetObject` e `PutObject`. Em 14/11, o arquivo deu lugar a `usuario-acaso-operador.json` + `limite-acaso.json` |
| `infra/aws/iam/role-bedrock-batch-*.json` | **Apagados** (2 arquivos) |
| `infra/aws/iam/README.md` | Reescrito: usuário de S3 e role da instância. Saíram o procedimento de 1º acesso ao Bedrock e o texto do caso no Support |
| `infra/aws/ec2/*` | Só o número do ADR |
| `data/work/batch_v1_amostra200/` | **Apagado.** Entrada de batch que nunca rodou (estava fora do git) |

### Conferências feitas

1. O prompt v2 em disco é **idêntico** à mensagem de sistema do `entrada.jsonl` da rodada real. O schema também.
2. A avaliação da validação, depois do refatoramento, dá os mesmos números: 71,4% e 83,8%.
3. `classificar_cpu.py preparar` roda de ponta a ponta e gera o mesmo formato de requisição.
4. `ruff check` limpo e 29 testes passando.

---

## 12. Avisos

1. **`docs/USO_DE_IA.md` cita o "ADR-011" na linha de 12/11.** Esse número não existe mais. A linha é do log de
   horas, que ficou intocado por decisão da pessoa. A correção é de uma palavra, se você quiser.
2. **O `.env` ainda tem `ACASO_BEDROCK_ROLE_ARN`.** O valor não é mais lido por nenhum script. O arquivo não é
   editado por automação.
3. **Nada foi apagado na AWS.** O bucket `acaso-desafio-tecnico` continua em uso pela EC2. A role
   `AmazonBedrock-acaso-batch` continua na conta, sem uso.
4. **O rótulo do schema mudou de nome**, de `registrar_classificacao` para `classificacao`. Esse nome é
   metadado: o llama.cpp monta a gramática só a partir do campo `schema`. A conferência 1 acima mostra que o
   schema não mudou.
5. **O prompt v1 também recebeu a linha do JSON.** Ele serviu só à 1ª rodada de ajuste, com o modelo de 4B. Se
   você preferir congelar o v1 como estava, é um `git checkout` de um arquivo.
6. **O campo `confianca` continua no schema**, apesar de inútil. Tirá-lo mudaria o schema e quebraria a
   equivalência com a rodada que gerou o parquet.
