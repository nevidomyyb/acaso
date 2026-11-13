# Metodologia — como cada número é calculado

Este documento mostra a origem de cada número da análise. Ele cobre os registros de decisão, a análise de
sensibilidade, o intervalo de confiança, o código linha a linha, os notebooks e os testes.

- Escopo: a análise e os indicadores do dashboard (§11).
- A etapa de rotulagem tem documento próprio: [METODOLOGIA_LABEL.md](METODOLOGIA_LABEL.md).
- Plano e cronograma: [../PROJECT.md](../PROJECT.md). Decisões aceitas e fatos dos dados: [../CLAUDE.md](../CLAUDE.md).
- Última conferência dos números: 12/11/2026.

---

## 1. ADR e BDR: por que dois tipos de registro

Os dois usam o mesmo formato: Contexto → Opções → Decisão → Consequências. Eles separam dois tipos de dúvida.

| | ADR | BDR |
|---|---|---|
| Pergunta | "Com que ferramenta eu construo?" | "O que este número significa?" |
| Exemplo | DuckDB em vez de Spark | "Usuário" é o IP |
| Se a escolha estiver errada | o código muda; o número não muda | **o número na tela muda** |
| Quem decide | a pessoa técnica | o cliente, com recomendação técnica |
| Onde | [adr/](adr/) | [bdr/](bdr/) |

A separação atende uma frase do enunciado: a pessoa da vaga responde pelos números do dashboard. Se a gerente
pergunta "por que 28,6% e não 34%?", a resposta não está no código. Ela está no BDR-002: 34% é o valor com
sessão de 15 minutos.

Por isso cada BDR tem uma seção que nenhum ADR tem: **Impacto no resultado**, com a taxa de cada opção. Veja
[bdr/BDR-002-sessao.md](bdr/BDR-002-sessao.md): quatro opções, quatro taxas, quatro intervalos de confiança.

ADR-004 (com que LLM classificar) é um ADR, porque escolhe a ferramenta. BDR-009 (quais temas existem) e
BDR-010 (o que é recusa) são BDRs, porque mudam a leitura do resultado.

---

## 2. Sensibilidade

A taxa de 28,6% não é um fato da natureza. Ela é a consequência de 11 escolhas. Mude uma escolha e o número muda.

**Sensibilidade** = quanto o resultado final se move quando uma definição muda, com todo o resto igual.

A tabela de sensibilidade responde à pergunta mais difícil de uma defesa técnica: "e se você tivesse escolhido
diferente?". Sem a tabela, não há resposta. Com a tabela, a resposta é um número.

### 2.1 Os 11 parâmetros

Todos ficam em [../etl/definicoes.py](../etl/definicoes.py#L31-L43). Cada um cita o seu BDR.

| Parâmetro | Padrão | Registro |
|---|---|---|
| `chave_usuario` | `ip` | BDR-001 |
| `max_uas_por_ip` | `None` | BDR-001 |
| `unidade_atividade` | `turno` | BDR-002 |
| `gap_sessao_min` | 30 | BDR-002 |
| `aquecimento_semanas` | 0 | BDR-003 |
| `regra_retorno` | `nova_sessao` | BDR-004 |
| `janela_retorno_dias` | 7 | BDR-004 |
| `fuso` | `America/Sao_Paulo` | BDR-005 |
| `excluir_janela_com_lacuna` | `True` | BDR-006 |
| `limiar_lacuna` | 0,15 | BDR-006 |
| `excluir_sem_conteudo` | `True` | BDR-008 |

### 2.2 Método

O cálculo está em [../analysis/03_definicoes_sensibilidade.py](../analysis/03_definicoes_sensibilidade.py#L83-L109),
em três passos.

1. **Declare as variantes.** Cada variante muda **um parâmetro só**.
   ```python
   VARIANTES = {
       "Padrão": {},
       "Sessão com gap de 15 min": {"gap_sessao_min": 15},
       "Retorno = atividade em outro dia": {"regra_retorno": "dia_seguinte"},
   }
   ```
2. **Reconstrua tudo do zero, para cada variante.**
   ```python
   def medir(d):
       u = construir(duckdb.connect(), BRUTA, d, volume_diario=VOLUME)
       return u, elegiveis(u, d)
   ```
   Cada linha da tabela relê o parquet de 22 MB. Ela remonta conversas → eventos → sessões → usuários com a
   nova regra. São 14 execuções completas do pipeline, não uma aproximação.
3. **Compare com o padrão**, em pontos percentuais: `delta_pp = (taxa − taxa_do_padrão) × 100`.

### 2.3 Ponto percentual e porcentagem

Os dois termos não são sinônimos. A troca entre eles destrói a credibilidade de uma apresentação.

- De 28,6% para 34,0% há **+5,4 pontos percentuais** (p.p.). É uma subtração.
- Em termos relativos, há +19%. É uma divisão.

Use sempre p.p. nos efeitos. Um público de negócio lê p.p. sem explicação.

### 2.4 A tabela

Fonte: [../data/work/sensibilidade.csv](../data/work/sensibilidade.csv), gerado pelo notebook 03.

| Variante | Denominador | Voltaram | Taxa | IC 95% | Δ p.p. |
|---|---|---|---|---|---|
| **Padrão** | 2.219 | 635 | **28,6%** | 26,8–30,5 | — |
| Sessão com gap de 15 min | 2.219 | 754 | 34,0% | 32,0–36,0 | **+5,4** |
| Usuário = IP + user-agent | 2.685 | 827 | 30,8% | 29,1–32,6 | **+2,2** |
| Usuário = IP + accept-language | 2.360 | 676 | 28,6% | 26,9–30,5 | +0,0 |
| Mantém janela com falha de coleta | 2.306 | 660 | 28,6% | 26,8–30,5 | +0,0 |
| Exclui IP com > 10 user-agents | 2.216 | 632 | 28,5% | 26,7–30,4 | −0,1 |
| Inclui conversa sem conteúdo | 2.249 | 638 | 28,4% | 26,5–30,3 | −0,2 |
| Aquecimento de 2 semanas | 2.157 | 609 | 28,2% | 26,4–30,2 | −0,4 |
| Aquecimento de 4 semanas | 2.026 | 564 | 27,8% | 25,9–29,8 | −0,8 |
| Retorno = atividade > 1h após o início | 2.219 | 600 | 27,0% | 25,2–28,9 | −1,6 |
| Sessão com gap de 60 min | 2.219 | 558 | 25,1% | 23,4–27,0 | **−3,5** |
| Atividade = só início de conversa | 2.219 | 539 | 24,3% | 22,6–26,1 | **−4,3** |
| Referência do incidente (IP+UA, conversa, > 1h) | 2.685 | 697 | 26,0% | 24,3–27,7 | −2,7 |
| Retorno = atividade em outro dia | 2.219 | 419 | 18,9% | 17,3–20,6 | **−9,7** |

**Como ler a tabela:**

1. **O que mais pesa não é quem é o usuário. É o que conta como "voltar".** As duas maiores variações (−9,7 e
   +5,4 p.p.) vêm da régua de tempo, não da identidade.
2. **Quatro escolhas quase não mudam a taxa** (≤ 0,2 p.p.): fuso, IP compartilhado, falha de coleta e conversa
   vazia. Mantenho cada uma porque elas corrigem a coorte certa, e não a taxa global.
3. **O denominador muda junto em algumas linhas.** Com "IP + user-agent", ele passa de 2.219 para 2.685: a
   mesma pessoa conta mais de uma vez. Essa linha é o mecanismo do incidente (§4.2 do desafio).

A última linha muda 3 parâmetros ao mesmo tempo, de propósito. Ela reconstrói as definições do código com
defeito e dá 26,0%. Ela mostra que o dashboard do enunciado media outra coisa.

### 2.5 Os dois limites do método

- **Uma variante por vez não mostra interação entre parâmetros.** Se o gap e a regra de retorno se reforçam, a
  tabela não revela. Por isso existe a linha com 3 mudanças juntas.
- **Os intervalos de confiança das variantes se sobrepõem.** Isso não torna a diferença um ruído. São as
  mesmas 2.219 pessoas, medidas com outra régua, e o Δ é exato para estes dados. O intervalo responde a outra
  pergunta: quanto o valor varia em outro grupo de pessoas.

---

## 3. Intervalo de confiança

O intervalo de confiança (IC) responde: a medição usou 2.219 pessoas, e não a população toda; quanto a
estimativa pode estar longe do alvo?

Leia "28,6% (IC 26,8–30,5%)" assim: numa repetição da medição com outro grupo comparável, em 95 de 100 vezes o
valor cai nessa faixa.

Uso o **IC de Wilson**, em [../etl/estatistica.py](../etl/estatistica.py#L10-L19). A fórmula clássica
(`p ± 1,96·√(p(1−p)/n)`) falha com n pequeno ou com taxa perto de 0% e de 100%: ela produz limite negativo.
Wilson nunca sai da faixa de 0 a 1. Com 39 pessoas por semana, isso não é um detalhe.

A largura do IC depende de n. Daí vem a decisão principal do dashboard:

| Coorte | Pessoas (mediana) | IC médio |
|---|---|---|
| Semanal | 39 | **±15 p.p.** |
| Mensal | — | **±7 p.p.** |

Um IC de ±15 p.p. não distingue 25% de 40%. Por isso a visão principal é mensal, e a semanal entra como
detalhe, com aviso de amostra pequena. O cálculo está em
[../analysis/03_definicoes_sensibilidade.py](../analysis/03_definicoes_sensibilidade.py#L145-L172).

---

## 4. A cadeia dos números

```
WildChat-1M (3,36 GB · 837.989 conversas · 201 países)
  │  etl/download.py          confere o SHA-256 dos 14 parquets
  ▼
wildchat_br.parquet (22 MB)   country = 'Brazil' → 11.621 conversas · 2.385 IPs
  │  etl/recorte_brasil.py    grava também o volume diário GLOBAL
  ▼
tabela conversas              1 linha por conversa, sem texto
  ▼
tabela eventos                1 linha por resposta do assistente
  ▼
tabelas eventos_sessao e sessoes
  ▼
tabela usuarios               1 linha por pessoa, com voltou_7d
  ▼
elegiveis()                   o denominador
  ▼
28,6% (IC 26,8–30,5%)
```

### 4.1 O funil

Valores conferidos em 12/11.

| Etapa | Pessoas | O que saiu | Registro |
|---|---|---|---|
| IPs no recorte Brasil | 2.385 | — | BDR-007 |
| Usuários com uso real | 2.354 | −31 IPs só com conversa sem mensagem | BDR-008 |
| Com 7 dias observáveis | 2.306 | −48 que chegaram perto do fim da base | BDR-006 |
| **Denominador** | **2.219** | −87 com falha de coleta na janela | BDR-006 |
| Voltaram em 7 dias | 635 | | BDR-004 |

635 ÷ 2.219 = **28,6%**.

A base tem 76 **conversas** sem conteúdo, mas só 31 **IPs** saem. Os outros IPs também têm conversas válidas.
Eles continuam na análise e perdem só aquela conversa.

Para refazer os números:

```bash
.venv/bin/python analysis/00_contagens_iniciais.py
cd analysis && ../.venv/bin/jupytext --to ipynb --execute 03_definicoes_sensibilidade.py
```

### 4.2 `criar_conversas()` — a query que resolve o schema

[../etl/definicoes.py](../etl/definicoes.py#L57-L90). Ela transforma a estrutura aninhada da WildChat em tabela
plana. Quatro linhas merecem atenção.

**A chave da conversa** ([linha 70](../etl/definicoes.py#L70)):
```sql
conversation[1].turn_identifier AS conversa_id
```
O campo óbvio, `conversation_hash`, não serve: ele repete em 93 conversas. São textos iguais ("oi", prompts
copiados) de IPs diferentes, ou seja, pessoas diferentes. Em DuckDB a lista começa em 1, então
`conversation[1]` é o primeiro turno.

**O início da conversa** ([linha 75](../etl/definicoes.py#L75)):
```sql
list_min(list_transform(conversation, lambda c: c.timestamp)) AS inicio_utc
```
Aqui está o erro mais fácil do desafio. O `timestamp` de topo da linha é o **último** turno, não o primeiro.
Os turnos do usuário nunca têm horário (0 de 26.579, medido). Só as respostas do assistente têm horário. Logo,
o início da conversa é o horário da 1ª resposta do assistente. O código com defeito do enunciado usa
`c["timestamp"]` como se fosse o início.

**O que conta como uso** ([linha 84](../etl/definicoes.py#L84)):
```sql
list_bool_and(list_transform(turnos_usuario, lambda u: trim(u.content) = '')) AS sem_conteudo
```
O valor é verdadeiro só quando **todas** as mensagens do usuário estão vazias. Esse caso é falha do coletor, e
não uma pessoa.

**O filtro** ([linha 67](../etl/definicoes.py#L67)): `WHERE country = 'Brazil'`, aplicado outra vez, mesmo com o
parquet já filtrado. É defesa em profundidade. Se alguém trocar a fonte, a definição continua correta. O teste
[test_definicoes.py](../tests/test_definicoes.py#L76-L87) prova que uma conversa de Portugal não entra.

### 4.3 `criar_lacunas()` — "ninguém usou" ou "ninguém registrou"

[../etl/definicoes.py](../etl/definicoes.py#L93-L108). Um dia sem dados tem duas explicações, com consequências
opostas: as pessoas não usaram, ou o coletor caiu.

```sql
WITH cal AS (SELECT unnest(generate_series(min, max, INTERVAL 1 DAY))::DATE AS dia_utc)
SELECT cal.dia_utc, coalesce(v.conversas, 0) AS conversas
FROM cal LEFT JOIN v USING (dia_utc)
WHERE coalesce(v.conversas, 0) < 0.15 * (SELECT median(conversas) FROM v)
```

Essas 4 linhas carregam 3 decisões.

1. **Calendário gerado, com `LEFT JOIN`.** Um dia ausente do parquet não aparece num `GROUP BY`. O calendário
   força o zero a aparecer.
2. **Volume global, não o do Brasil.** O Brasil tem cerca de 30 conversas por dia, e um dia fraco é ruído
   normal. Com 837 mil conversas globais, a queda é inequívoca.
3. **Limiar de 15%, e não de 25%.** O limiar de 25% marcava o Réveillon como falha de coleta, e Réveillon é
   comportamento. Medida: feriado fica perto de 20% da mediana; falha real fica em 0% ou perto disso. O limiar
   de 15% separa os dois casos.

Resultado: 6 dias. Em 13/10/2023 e em 18–19/01/2024 não há nenhuma conversa no mundo. Em 26/06, 14/10 e 17/01
o volume fica abaixo de 15%. Quem tem a janela de 7 dias sobre um desses dias pode ter voltado sem registro.
Essas 87 pessoas saem do denominador.

### 4.4 A query de sessão — a mais difícil do projeto

[../etl/definicoes.py](../etl/definicoes.py#L143-L157). Primeiro, o evento
([linhas 131-135](../etl/definicoes.py#L131-L135)):

```python
if d.unidade_atividade == "turno":
    eventos = "SELECT usuario_id, conversa_id, unnest(horarios_respostas) AS inicio_utc FROM u"
```

O `unnest` separa cada conversa em uma linha **por resposta do assistente**. Essa escolha vale 4,3 p.p. A base
tem uma conversa de 11 dias e 546 conversas acima de 1 hora. A pessoa deixa a aba aberta e volta no dia
seguinte. Com a conversa como evento, essa volta fica invisível.

Agora a parte sutil. O método ingênuo compara cada evento com o evento **anterior**. Ele falha aqui, porque as
conversas se sobrepõem: a pessoa abre a conversa B com a conversa A ainda aberta. A ordem por início não
garante que o fim anterior seja o maior fim até ali.

A solução usa uma janela com máximo acumulado:

```sql
max(fim_utc) OVER (PARTITION BY usuario_id ORDER BY inicio_utc, conversa_id
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS fim_anterior
```

`fim_anterior` é o maior fim entre **todos** os eventos anteriores da pessoa, e não o fim do evento vizinho.
Depois vem a soma acumulada:

```sql
sum(CASE WHEN fim_anterior IS NULL
           OR inicio_utc > fim_anterior + INTERVAL 30 MINUTE
         THEN 1 ELSE 0 END) OVER (... ROWS UNBOUNDED PRECEDING) AS sessao_seq
```

Cada evento que abre uma sessão nova recebe 1. A soma acumulada dá o número da sessão: 1, 1, 1, 2, 2, 3. Esse é
o padrão "gaps and islands". Ele resolve o problema em duas passagens, sem laço.

**Por que 30 minutos?** O histograma dos intervalos entre respostas do mesmo IP não tem vale natural entre 15 e
60 minutos ([notebook 01, seção 8](../analysis/01_discovery.py#L241-L261)). A distribuição cai de forma
contínua. Logo, não existe um corte "descoberto nos dados". O valor de 30 minutos é a convenção das ferramentas
de web analytics, e o documento declara isso. O preço da escolha está na tabela de sensibilidade: +5,4 p.p. com
15 minutos e −3,5 p.p. com 60 minutos.

O mesmo histograma trouxe um achado extra: há um pico perto de **1 dia**. Quem volta tende a voltar no mesmo
horário do dia seguinte. Esse é um sinal de hábito, e vira sugestão de produto (lembrete no horário de uso).

### 4.5 A query de retorno

[../etl/definicoes.py](../etl/definicoes.py#L165-L203). As três regras do BDR-004:

```python
if d.regra_retorno == "nova_sessao":
    cond = "e.sessao_seq >= 2"
elif d.regra_retorno == "apos_1h":
    cond = "e.inicio_utc > p.inicio_utc + INTERVAL 1 HOUR"
else:  # dia_seguinte
    cond = "timezone(fuso, e.inicio_utc)::DATE > timezone(fuso, p.inicio_utc)::DATE"
```

A regra padrão é só `sessao_seq >= 2`. Ela basta: por construção, a sessão 2 começa no mínimo 30 minutos depois
do fim da sessão 1. A regra de tempo mora na definição de sessão, e o código não a repete aqui.

**A janela:**
```sql
WHERE {cond} AND e.inicio_utc <= p.inicio_utc + INTERVAL 7 DAY
```
A contagem de 7×24h começa no **início** da primeira sessão, e não no fim. Com a contagem a partir do fim, quem
tem primeira sessão longa ganharia mais tempo para voltar, e a régua mudaria de tamanho por pessoa.

**A censura** ([linha 195](../etl/definicoes.py#L195)):
```sql
p.inicio_utc + INTERVAL 7 DAY <= l.base_fim AS observavel_7d
```
Quem aparece nos últimos 7 dias da base ainda não teve chance de voltar. A contagem dessa pessoa como "não
voltou" inventa uma queda no fim do gráfico. São 48 pessoas. Esse é o erro clássico de curva de retenção.

**A coorte** ([linhas 198-199](../etl/definicoes.py#L198-L199)):
```sql
date_trunc('week',  timezone('America/Sao_Paulo', p.inicio_utc))::DATE AS coorte_semana
date_trunc('month', timezone('America/Sao_Paulo', p.inicio_utc))::DATE AS coorte_mes
```
A conversão para São Paulo vem **antes** do truncamento. O código com defeito do enunciado faz
`date_trunc('week', ...)` sem fuso: quem usa às 22h de domingo no Brasil cai na semana errada. O efeito na taxa
total é de 0,2 p.p. ou menos, mas ele desloca as coortes.

### 4.6 `elegiveis()` — o denominador num lugar só

[../etl/definicoes.py](../etl/definicoes.py#L210-L216). Sete linhas decidem quem entra na conta:

```python
m = usuarios.observavel_7d & ~usuarios.em_aquecimento
if d.excluir_janela_com_lacuna:
    m &= ~usuarios.janela_com_lacuna
return usuarios[m]
```

A função fica separada de propósito. O denominador é o número que estraga um dashboard em silêncio, e foi ele
que explodiu no incidente do §4.2. Com a regra numa função, a API, os notebooks e os testes usam a mesma.

---

## 5. Notebook a notebook

A fonte é sempre o arquivo `.py` no formato jupytext. O `.ipynb` é **gerado**. Motivo: o `.py` aparece legível
no diff e na revisão. Um `.ipynb` versionado é JSON com saídas embutidas, ilegível num PR.

```bash
cd analysis && ../.venv/bin/jupytext --to ipynb --execute 01_discovery.py
```

### 00_contagens_iniciais.py — script, não notebook
[../analysis/00_contagens_iniciais.py](../analysis/00_contagens_iniciais.py). Roda em segundos. Responde:
tamanho do recorte, qualidade básica, N para o custo da classificação, e se o relatório do incidente é reproduzível.
É script porque a saída é texto para decidir, e não gráfico para mostrar.

### 01_discovery.py — os problemas e os tratamentos
[../analysis/01_discovery.py](../analysis/01_discovery.py). Cada seção segue o mesmo rito: query → achado →
tratamento → registro.

| § | Query | Achado | Tratamento |
|---|---|---|---|
| 1 | volume e período | 11.621 conversas · 2.385 IPs · 41 novos por semana | coorte mensal |
| 2 | [volume global com calendário](../analysis/01_discovery.py#L59-L81) | 6 dias de falha de coleta | saem do denominador (87 pessoas) |
| 3 | [hash repetido](../analysis/01_discovery.py#L95-L99) | 93 conversas, sempre de IPs diferentes | chave = `turn_identifier`; sem deduplicação |
| 4 | [durações](../analysis/01_discovery.py#L112-L120) | 546 conversas acima de 1h; a maior dura 11 dias | sessão por resposta (+4,3 p.p.) |
| 5 | [concentração](../analysis/01_discovery.py#L135-L156) | 1% dos IPs = 41% das conversas; 1 IP com 1.557 conversas e 35 UAs | na taxa, 1 IP = 1 voto; nas análises por conversa, marca o IP |
| 6 | [IP dinâmico](../analysis/01_discovery.py#L184-L194) | ≥ 2% dos novos IPs; 436 UAs no total; 36% mobile | risco registrado |
| 7 | [idioma, estado, conteúdo](../analysis/01_discovery.py#L211-L222) | 76% português; 10 de 28 estados com < 20 usuários; 0 tóxicas | idioma em 3 níveis; estado "outros"; fator toxicidade descartado |
| 8 | [histograma de intervalos](../analysis/01_discovery.py#L241-L261) | sem vale entre 15 e 60 min; pico perto de 1 dia | gap de 30 min, por convenção declarada |

Duas queries desse notebook precisam de explicação.

**O limite inferior do IP dinâmico** ([seção 6](../analysis/01_discovery.py#L184-L194)). A pergunta não tem
resposta exata: quando a operadora troca o IP de alguém, a pessoa vira "nova" e o dado não registra o vínculo.
A query busca uma pista. Ela conta os IPs novos cuja **primeira** conversa usa um user-agent raro (presente em
3 IPs ou menos), já visto em **outro** IP na semana anterior, com o mesmo `accept-language`. São 48 casos (2%).
O valor é um piso, e nunca o valor real. O notebook e o registro de riscos declaram esse limite.

**A curva de concentração** ([seção 5](../analysis/01_discovery.py#L135-L156)). A query ordena os IPs por volume
e acumula o total. Resultado: os 23 IPs mais ativos (1% do total, com 52 conversas ou mais) concentram 41% das
conversas. Por isso a taxa de retorno usa o IP como unidade, e não a conversa. Com a conversa como unidade, um
único IP de 1.557 conversas definiria a métrica da empresa.

### 03_definicoes_sensibilidade.py — a tabela e os intervalos
[../analysis/03_definicoes_sensibilidade.py](../analysis/03_definicoes_sensibilidade.py). Cinco seções:
definições padrão com o BDR de cada parâmetro · funil · tabela de sensibilidade com gráfico · coorte semanal e
mensal · ponteiros para os BDRs.

O gráfico de coortes ([seção 4](../analysis/03_definicoes_sensibilidade.py#L154-L172)) justifica a visão mensal.
Ele mostra a linha mensal com faixa de IC, e os pontos semanais com barras de erro largas por cima. O argumento
fica visual, sem vocabulário de estatística.

### 02_eda.py — a 1ª experiência, sem ajuste
[../analysis/02_eda.py](../analysis/02_eda.py). Lê a tabela de [../etl/primeira_experiencia.py](../etl/primeira_experiencia.py):
uma linha por usuário, com o **conteúdo** da 1ª conversa (tema, recusa, modelo, idioma, tamanho da resposta,
dispositivo, estado) e o **volume** da 1ª sessão (conversas, respostas, duração). O 03 veio antes porque a
definição vem antes da análise: sem a definição de "voltar", não há o que explorar.

Todo número do 02 é **bruto**, com IC de Wilson. Cada gráfico sustenta uma conclusão:

| § | Gráfico | Conclusão | Decisão para o 04 |
|---|---|---|---|
| 1 | quando a pessoa volta | 94% dos retornos em 30 dias caem em 7 dias; 55% dos retornos em 7 dias, em até 6 h | a janela de 7 dias perde pouco |
| 2 | tema, recusa, tamanho da resposta | recusa total 15% × 29%; saudação 22% | recusa e tema como fatores |
| 3 | idioma, dispositivo, horário, dia | idioma "outro" 19% (54% é saudação); madrugada 22%; celular 25% | idioma compete com a saudação |
| 4 | volume da 1ª sessão | 10 ou mais respostas: 52%; uma só: 23% | **fora** do modelo principal: é engajamento |
| 5 | estado | Rio de Janeiro 17,5% nos dois dispositivos | estado como controle; risco 1 |
| 6 | % de GPT-4 por mês | sem GPT-4 de jul. a out./2023 | comparar modelos só nos 6 meses com os dois |

**O caso do Rio** ([seção 5](../analysis/02_eda.py)). O Rio tem 55% de celular, contra 29% no resto. Mas o
retorno fica baixo no desktop (19%) e no celular (16%), então o mix não explica a queda. A query do IP dinâmico do
notebook 01 foi refeita para a frente: o user-agent raro da estreia reaparece em **outro** IP nos 7 dias
seguintes. No Rio, isso acontece 2 a 3 vezes mais. É um piso, não o valor real. A hipótese é medição: a mesma
pessoa vira um "novo" usuário que nunca volta.

**Por que o volume fica fora do modelo principal.** O volume da sessão está no caminho entre a experiência e o
retorno: uma recusa encurta a sessão, e a sessão curta volta menos. Controlar pelo volume apagaria parte do efeito
da recusa. O modelo principal mede o efeito total; o modelo com volume entra como sensibilidade.

### estilo.py
[../analysis/estilo.py](../analysis/estilo.py). Paleta única, validada para daltonismo. `aplicar()` ajusta o
`rcParams`. `nota()` escreve a fonte no pé de **todo** gráfico. Isso atende o requisito "cada número com
definição e fonte" sem depender de disciplina manual a cada gráfico.

---

## 6. Os testes

[../tests/test_definicoes.py](../tests/test_definicoes.py) e [../tests/conftest.py](../tests/conftest.py).
Última execução em 13/11: **33 testes passaram**, em 1,8 s. Desta seção, 11 são de definição. Os outros cobrem a
classificação (§7) e a tabela da 1ª experiência
([../tests/test_primeira_experiencia.py](../tests/test_primeira_experiencia.py), 4 testes: conteúdo da 1ª conversa
× volume da sessão, horário local com virada de dia, estado com menos de k usuários → "outros", e o mesmo
denominador de `elegiveis()`).

A base de teste é **sintética** ([conftest.py](../tests/conftest.py#L44-L85)), construída com pyarrow no mesmo
schema parcial da WildChat. Motivo: nos dados reais a resposta certa é desconhecida, então um teste contra eles
detecta mudança, mas não detecta erro. Na base sintética, o caso vem escrito e a resposta é conhecida.

```python
b.conversa("A", H(0))            # 1ª conversa
b.conversa("A", H(0) + M(20))    # 20 min depois: mesma sessão
b.conversa("A", D(3))            # dia 3: voltou
b.conversa("B", D(8))            # dia 8: fora da janela, não conta
```

`T0` é uma segunda-feira, às 10h em São Paulo. A escolha evita ambiguidade nos testes de fuso e de semana.

Dois testes merecem destaque.

**O mecanismo do incidente, como teste** ([linhas 76-87](../tests/test_definicoes.py#L76-L87)):
```python
b.conversa("H", H(0), ua="Chrome-118")
b.conversa("H", D(2), ua="Chrome-119")   # a pessoa atualizou o navegador
assert len(por_ip_ua) == 3             # a mesma pessoa virou dois "novos"
assert por_ip_ua.voltou_7d.sum() == 0  # e nenhum deles "voltou"
```
Uma pessoa, uma atualização de navegador, dois usuários novos, zero retornos. É o incidente em 4 linhas. Com
`chave_usuario="ip"`, a mesma base dá 1 usuário, que voltou.

**A conversa aberta** ([linhas 111-116](../tests/test_definicoes.py#L111-L116)): uma conversa só, com 3 dias de
duração. Com atividade por turno, a pessoa voltou. Com atividade por conversa, não voltou. O teste prova os
4,3 p.p. num caso isolado.

Os outros testes fixam: janela de 7 dias, gap de 30 e de 60 minutos, as 3 regras de retorno, censura e
aquecimento, filtro Brasil, conversa sem conteúdo, definição inválida, Wilson contra valor conhecido, e falha de
coleta fora do denominador.

Se alguém muda uma definição sem perceber, um teste quebra. Essa é a resposta à pergunta de sustentação do
desafio: como perceber que um número mudou antes do cliente.

---

## 7. A classificação: LLM aberto em CPU numa EC2

O enunciado exige que o LLM, se usado, rode na AWS. A conta é nova: o Bedrock tem cota 0 em todos os modelos
e a cota de GPU também é 0. Por isso o tema e a recusa saem de um LLM aberto (Qwen3-8B, llama.cpp) numa EC2 só
com CPU. As opções avaliadas estão no ADR-004.

| Peça | O que faz |
|---|---|
| [../etl/classificacao.py](../etl/classificacao.py) | Fonte única da taxonomia, do texto de entrada, do schema e da validação |
| [../etl/classificar_cpu.py](../etl/classificar_cpu.py) | Seleciona as 3.361 conversas da 1ª sessão, monta o corpo de cada requisição, envia ao S3 e coleta |
| [../etl/llm_runner.py](../etl/llm_runner.py) | Roda na EC2: chama o llama-server, grava uma linha por conversa, retoma de onde parou |
| [../infra/aws/ec2/](../infra/aws/ec2/) | Cria, acompanha e destrói a EC2; acesso só por SSM; modelos com revisão e SHA-256 fixados |
| [../etl/prompts/classificacao_v2.md](../etl/prompts/classificacao_v2.md) | 11 temas, regras de desempate, recusa em 3 níveis, conteúdo tratado como dado |
| [../etl/validacao_classificacao.py](../etl/validacao_classificacao.py) | Amostra de 151 para rótulo manual e acurácia ponderada pela base |
| [../etl/recusa_regex.py](../etl/recusa_regex.py) | Checagem cruzada da recusa, por padrões PT/EN nos primeiros 400 caracteres |

Três escolhas precisam de explicação:

- **Escopo na 1ª sessão.** A pergunta é sobre a estreia. Classificar as 11.621 conversas em CPU levaria ~20 h.
  As 3.361 da 1ª sessão levam ~6 h.
- **Saída por gramática.** O llama.cpp só deixa o modelo gerar JSON que cabe no `SCHEMA` de `etl/classificacao.py`.
  Assim nenhuma resposta sai fora do formato. O campo `motivo` tem limite de 90 caracteres, porque cada token de
  saída custa ~50 ms em CPU.
- **Acurácia ponderada.** A amostra de validação garante um mínimo de casos por tema. Por isso a média simples
  da amostra superestima os temas raros. O número reportado pesa cada tema pelo tamanho dele na base.

O ajuste usou 2 rodadas em 40 conversas (tabela no ADR-004). Essas 40 ficam fora da validação: medir nelas
inflaria a acurácia.

A validação manual (12/11) usa 151 conversas, rotuladas às cegas pela pessoa:

| Medida | Resultado | Uso |
|---|---|---|
| Tema, 11 temas | 71,4% (IC 64,4–78,5%) | Só gráficos descritivos |
| Tema, 7 grupos | 83,8% (IC 78,9–88,7%) | Fator do modelo (BDR-009) |
| Recusa `total` pelo LLM | 8 de 9 marcadas são recusa; 5 de 5 totais achadas | Fator do modelo (BDR-010) |
| Regex de recusa | 8 de 9; 4 de 5 | Sensibilidade |

O tema e a recusa de cada usuário vêm da 1ª conversa da 1ª sessão. A sessão inteira mistura engajamento (BDR-010).

---

## 8. Procedência de cada número

| Número | Onde nasce | Como refazer |
|---|---|---|
| 11.621 conversas · 2.385 IPs | recorte + `criar_conversas` | `analysis/00_contagens_iniciais.py` |
| 28,6% (IC 26,8–30,5%) · n = 2.219 | `construir` + `elegiveis` + `wilson` | notebook 03, seção 2 |
| Todos os Δ p.p. | 14 execuções do pipeline | notebook 03, seção 3 → `data/work/sensibilidade.csv` |
| IC ±15 p.p. semanal e ±7 mensal | `por_coorte` + Wilson | notebook 03, seção 4 |
| 6 dias de falha · 87 pessoas | volume global < 15% da mediana | notebook 01, seção 2 |
| 546 conversas acima de 1h · máx. 11 dias | `fim_utc − inicio_utc` | notebook 01, seção 4 |
| 1% dos IPs = 41% das conversas | curva acumulada | notebook 01, seção 5 |
| IP dinâmico ≥ 2% | UA raro em outro IP em 7 dias | notebook 01, seção 6 |
| 94% dos retornos em 30 dias caem em 7 dias | 2ª sessão − 1ª, observáveis por 30 dias (2.043) | notebook 02, seção 1 |
| Recusa total 15,1% × 29,3% · n = 106 | `primeira_experiencia` + Wilson | notebook 02, seção 2 |
| Rio de Janeiro 17,5% · n = 257 | `estado_grupo` + Wilson | notebook 02, seção 5 |
| Classificação ≈ US$ 4,70 | c7i.4xlarge ≈ US$ 0,714/h × 6,6 h (ADR-004) | `classificacao.sh log`; fatura da EC2 |

---

## 9. Correções de 12/11

A conferência deste documento achou dois números errados ou ambíguos na memória do projeto.

| Item | Antes | Depois |
|---|---|---|
| Concentração de IPs | top 1% (≥ 44 conversas) = 42% | **23 IPs, ≥ 52 conversas, 41,1%** |
| Duração da base | 57 semanas | **386 dias = 55 semanas corridas; 57 semanas de calendário** |

O notebook 01 sempre mostrou 41%. O valor de 42% entrou na memória por um corte anterior. Os dois valores de
semana estão certos, mas medem coisas diferentes: a primeira e a última semana da base são parciais.

---

## 10. Resumo das definições, para a apresentação

Use este bloco como roteiro da parte de definições. Abra pelo **resultado**, e só depois mostre a régua. Oito
definições antes do número cansam um público de negócio.

**Resultado:** 635 de 2.219 pessoas voltaram = **28,6% (IC 26,8–30,5%)**.

| Definição | Escolha | BDR |
|---|---|---|
| Pessoa | `hashed_ip`. Risco nos dois sentidos: IP compartilhado junta pessoas, IP dinâmico divide uma pessoa em duas (≥ 2% dos novos IPs) | 001 |
| Ter usado | conversa com ao menos 1 mensagem **do usuário** não vazia (76 conversas saem) | 008 |
| Atividade | **cada resposta do assistente**. É o único horário que a base tem | 002 |
| Sessão | atividades **da pessoa**, em qualquer conversa, com menos de 30 min entre si | 002 |
| O relógio começa | no horário da 1ª resposta do assistente da 1ª sessão | 004 |
| Voltar | nova sessão dentro de 7×24h desse horário | 004 |
| Denominador | pessoas cuja 1ª sessão tem 7 dias observáveis e sem falha de coleta na janela: 2.219 de 2.385 IPs (93%) | 003, 006 |
| População | só `country = 'Brazil'` (1,4% da base global) | 007 |

**Quatro pontos para dizer em voz alta:**

1. **A janela de 7 dias vem do enunciado** (linha 35). Ela não é escolha nossa. O que é nossa escolha: 7 dias
   contados de quando, e o que conta como "voltar".
2. **O denominador é a coorte de novatos.** Cada pessoa entra uma vez, na estreia. A métrica não é uso geral.
3. **Ninguém é contado como "não voltou" sem ter tido chance de voltar.** Saem 48 censurados e 87 com falha de
   coleta. Sem esse corte, o gráfico inventa uma queda no fim.
4. **A sessão atravessa conversas.** Ela não fica dentro de uma conversa. Uma pessoa pode ter 3 conversas
   abertas na mesma sessão.

**O preço de cada escolha, em uma frase:** sessão de 15 min daria 34,0% (+5,4 p.p.); "voltar = outro dia do
calendário" daria 18,9% (−9,7 p.p.). Por isso o dashboard mostra a definição ao lado do número.

**Detalhe para ter na manga:** o fuso (BDR-005) só afeta o agrupamento das coortes, nunca a janela. A janela
usa 7×24h absolutas, então horário de verão e fuso não a distorcem.

---

## 11. Os indicadores do dashboard

Esta seção substitui o `INDICADORES.md` previsto no plano (corte de 13/11, `PROJECT.md` §14). Cada indicador do
dashboard tem definição, numerador, denominador e regra de amostra mínima. Todos nascem das mesmas definições
dos BDRs, pelo mesmo módulo `etl/definicoes.py` que a análise usa.

| Indicador | Definição | Numerador ÷ denominador | Período | Fonte |
|---|---|---|---|---|
| **Novos usuários** | Pessoas cuja 1ª sessão começou no período | contagem de `usuario_id` elegíveis | mês (semana como detalhe) | `agg_coorte` |
| **Taxa de retorno em 7 dias** | Quem abriu nova sessão até 7×24h do início da 1ª | `voltou_7d` ÷ elegíveis da coorte | mês (semana como detalhe) | `agg_coorte` |
| **Efeito ajustado de um fator** | Diferença de retorno, em p.p., entre dois níveis do fator, com os outros fatores mantidos | efeito marginal médio da logística | base inteira | `resultado_efeitos` |
| **% de 1ª conversa com recusa** | Quem levou recusa total na 1ª conversa da estreia (BDR-010) | com recusa total ÷ elegíveis | mês | `primeira_experiencia` |
| **Mix de temas na estreia** | Distribuição dos 7 grupos de tema na 1ª conversa (BDR-009) | por grupo ÷ elegíveis | mês | `primeira_experiencia` |

**Regras comuns a todos:**

1. **Denominador = a coorte de novatos elegíveis.** `elegiveis()` tira 48 pessoas censuradas e 87 com falha de
   coleta na janela. Ninguém conta como "não voltou" sem ter tido chance de voltar.
2. **Todo número com IC de Wilson** (§3), nunca a proporção sozinha.
3. **Amostra mínima:** se o IC passar de ±10 p.p. (cerca de 80 pessoas), a tela mostra o número esmaecido, com o
   aviso "amostra insuficiente". O número nunca é escondido sem aviso.
4. **k-anonimato, k = 20:** um recorte com menos de 20 pessoas não aparece. O estado com poucos usuários entra
   em "outros".
5. **Cada resposta da API carrega `definicao_versao` e `fonte`.** Se uma definição mudar, o número muda de
   versão junto, e o rodapé da tela mostra qual versão gerou o valor.

O SQL de cada indicador fica ao lado do seu endpoint, em `backend/`, e entra aqui no Dia 5. Os valores não são
calculados no request: a carga grava `agg_coorte`, `resultado_efeitos` e `primeira_experiencia` já prontos
(`PROJECT.md` §6.4).
