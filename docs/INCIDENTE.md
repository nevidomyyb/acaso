# Incidente: o retorno da semana de 20/11/2023 "caiu" de 31% para 18%

Resposta à §4.2 do enunciado, seguida do monitoramento (§4.1). A análise com dados reais está no notebook
[05_incidente](../analysis/05_incidente.ipynb). O código de referência e a correção estão em
[etl/incidente.py](../etl/incidente.py), e os testes de regressão em [tests/test_incidente.py](../tests/test_incidente.py).

**Resumo.** O retorno não caiu. A carga troca de pessoa quando o user-agent muda: a chave do usuário é
`sha256(hashed_ip | user-agent)`. Na semana de 20/11, cerca de 860 chaves novas entraram no denominador e nunca
voltaram. A correção usa só o `hashed_ip` como chave (BDR-001) e reprocessa o histórico.

**Nota sobre os números.** Os números do enunciado não existem na base pública: na semana de 20/11, o Brasil tem 76
novatos pelo código de referência, não 2.034. Por isso, a investigação demonstra o **mecanismo** com os dados reais
e não tenta reproduzir os números.

---

## 1. Por onde eu começaria, e por quê

Comecei separando o **numerador** do **denominador**, porque os dois materiais já permitem isso sem rodar nada:

| Semana | Dashboard: novos / voltaram | Relatório: novos / voltaram |
|---|---|---|
| 06/11 | 1.210 / 375 | 1.150 / 345 |
| 13/11 | 1.188 / 368 | 1.131 / 351 |
| 20/11 | **2.034** / 366 | 1.172 / 352 |

- Os retornos ficam estáveis nas duas fontes (366 e 352). O que muda é o **denominador**: +846 novos só no dashboard.
- Logo, a pergunta certa não é "por que as pessoas voltaram menos". É "**quem passou a contar como novo**".
- Retornos parados com novos dobrando têm uma assinatura clara: ~860 "pessoas" que aparecem uma vez e não voltam.

Depois, passei pelas camadas, da tela para a origem, e descartei uma de cada vez, com a evidência de por que a falha não
está nela.

## 2. Em qual camada está a falha

**Na carga.** As evidências, camada por camada:

| Camada | Evidência | Conclusão |
|---|---|---|
| Tela | O log do backend (`req_4c19a2`) mostra que a API devolveu 2.034 / 366. A tela só repete | descartada |
| Backend (endpoint) | O mesmo SQL roda em todas as semanas. Um defeito só do SQL não explica um salto numa semana só | não é a causa principal (tem 3 defeitos menores, item 3) |
| Base bruta | O relatório conta por `hashed_ip` direto na bruta e fica estável (~30%) | descartada |
| Base analítica / carga | A chave `sha256(hashed_ip \| user-agent)` cria uma pessoa nova a cada user-agent novo | **causa** |

O "dashboard ~5% acima" das semanas anteriores tem a mesma origem, em escala menor. Na nossa base, a chave IP +
user-agent conta **21% mais "novos"** que a chave por IP (2.895 contra 2.385), e **17,6%** dessas chaves "novas" são
de IPs que já existiam.

**Qual mudança de user-agent produz a assinatura?** O notebook 05 testa 2 mecanismos sobre os dados reais, a partir
de 20/11:

| Mecanismo | Novos (dashboard) | Voltaram (dashboard) | Assinatura? |
|---|---|---|---|
| Real (sem mudança) | 76 | 16 | — |
| M1: atualização de navegador (todos, uma vez) | 90 | **26 ↑** | não: os retornos sobem junto |
| M2: user-agent único por conversa (metade das conversas) | **147 (≈ 2×)** | **11** | **sim** |

O relatório (chave por IP) dá 68 / 13 nos 3 cenários. Hipótese principal: **a partir de 20/11, parte do tráfego
passou a mandar um user-agent diferente a cada conversa** (por exemplo, uma versão de app que põe um identificador
de sessão no cabeçalho). Uma atualização de navegador comum não basta: ela faria os retornos subirem também.

**Consultas que eu rodaria para confirmar.** A 1ª usa só a base analítica; a 2ª precisa da bruta, que tem o IP e o
user-agent.

```sql
-- 1) Base analítica: a parcela de "novos" com uma conversa só deve saltar na semana de 20/11
WITH primeira AS (
    SELECT usuario_id, min(ultimo_turno) AS primeira_vez, count(*) AS n_conversas
    FROM analytics.conversas WHERE pais = 'Brazil' GROUP BY usuario_id
)
SELECT date_trunc('week', primeira_vez)::date AS semana, count(*) AS novos,
       count(*) FILTER (WHERE n_conversas = 1) AS so_uma_conversa
FROM primeira
WHERE primeira_vez >= '2023-10-30' AND primeira_vez < '2023-12-04'
GROUP BY 1 ORDER BY 1;

-- 2) Base bruta: chaves por IP e user-agents por IP, por semana
WITH c AS (
    SELECT hashed_ip, coalesce(header."user-agent", 'None') AS ua, "timestamp" AS ultimo_turno
    FROM bruta WHERE country = 'Brazil'
),
chave_ua AS (SELECT hashed_ip, ua, min(ultimo_turno) AS primeira_vez FROM c GROUP BY 1, 2),
chave_ip AS (SELECT hashed_ip, min(ultimo_turno) AS primeira_ip FROM c GROUP BY 1)
SELECT date_trunc('week', k.primeira_vez)::date AS semana,
       count(*)                                                  AS novos_ip_ua,
       count(*) FILTER (WHERE i.primeira_ip < k.primeira_vez)    AS chave_nova_de_ip_antigo
FROM chave_ua k JOIN chave_ip i USING (hashed_ip)
GROUP BY 1 ORDER BY 1;
```

**Leitura esperada.** Se a hipótese está certa, na semana de 20/11 a razão "chaves por IP" salta de ~1,05 para ~1,7
(2.034 ÷ 1.172), e quase todas as chaves extras têm uma conversa só.

## 3. O trecho que causa o problema, e a correção

**[1] Causa principal: a chave na carga.**

```python
chave = f"{c['hashed_ip']}|{c['header']['user-agent']}"      # ← o user-agent muda; a pessoa não
"usuario_id": sha256(chave.encode()).hexdigest(),
```

**Defeitos secundários** (medidos no notebook 05; nenhum explica o salto, mas todos distorcem o número):

| # | Trecho | Defeito | Efeito medido na nossa base |
|---|---|---|---|
| 2 | `"ultimo_turno": c["timestamp"]` + `min(ultimo_turno)` | a 1ª vez usa o **último** turno da 1ª conversa | −0,1 p.p. |
| 3 | `ON CONFLICT (conversa_id) DO NOTHING` | uma conversa que continua no dia seguinte não atualiza | não mensurável na base pública; coberto por teste |
| 4 | `date_trunc('week', p.primeira_vez)` | semana em UTC, não no fuso do país | 46 de 2.385 novatos (1,9%) mudam de semana |
| 5 | `EXISTS (... WHERE c.usuario_id = ...)` | o retorno não filtra o país | 0 aqui (nenhum IP brasileiro aparece fora); latente com VPN |

**Por que cada um é um defeito:**

**2. A 1ª vez usa o fim da conversa, não o começo.** Na base bruta, o `timestamp` de topo é o horário do
**último** turno da conversa. A carga grava esse valor como `ultimo_turno`, e o endpoint usa `min(ultimo_turno)`
como "1ª vez". Logo, a experiência da pessoa começa quando a 1ª conversa **termina**. Isso importa porque uma
conversa fica aberta por horas ou dias: 546 conversas do Brasil duram mais de 1 h, e a maior dura 11 dias.
- **Exemplo:** a pessoa abre a 1ª conversa segunda às 10h e escreve nela até quarta às 22h. Para o endpoint, ela
  chegou na quarta às 22h. A janela de 7 dias começa 2,5 dias atrasada, e a coorte pode cair na semana errada.
- **O mesmo erro no retorno:** o retorno também usa o fim da conversa de retorno. Uma 2ª conversa aberta 10 min
  depois da 1ª, que dura 2 h, termina 2h10 depois: passa da regra "> 1 hora" e conta como retorno. Mas a pessoa
  nunca saiu: é a mesma sessão.
- **Efeito na nossa base:** −0,1 p.p. no total, porque os erros vão para os dois lados e quase se anulam. Uma
  pessoa de cada vez, o erro é grande.
- **Correção:** gravar também o `primeiro_turno` (a 1ª resposta do assistente; os turnos do usuário não têm
  horário) e medir a 1ª vez e o retorno por ele.

**3. A carga diária ignora a continuação de uma conversa.** A carga roda todo dia, com as conversas do dia. Uma
conversa que começa na segunda e continua na terça chega nas duas cargas, com o mesmo `conversa_id`, porque a
chave é o 1º turno. Na segunda, a carga grava `ultimo_turno` = segunda. Na terça, chega a versão nova (mais
turnos, último turno na terça), e o `ON CONFLICT DO NOTHING` a descarta sem aviso.
- **Por que é defeito:** a base analítica fica diferente da bruta, e ninguém percebe. O `ultimo_turno` e o número
  de turnos ficam congelados no 1º dia.
- **O que acontece no número:** a atividade da terça nunca entra na base. Se a pessoa volta na terça **dentro da
  mesma conversa**, esse retorno se perde. Na base pública, 211 conversas atravessam a meia-noite (UTC).
- **Efeito na nossa base:** não dá para medir, porque a base pública traz cada conversa uma vez, já completa. O
  teste de regressão simula 2 cargas e prova o defeito.
- **Correção:** `ON CONFLICT ... DO UPDATE`, com o menor `primeiro_turno` e o maior `ultimo_turno`.

**4. A semana é calculada em UTC, não no fuso do país.** O `date_trunc('week', ...)` sobre um horário com fuso usa
o fuso da **sessão do banco**, que no servidor costuma ser UTC. A semana UTC começa na segunda às 0h UTC, que é
domingo às 21h em São Paulo.
- **Exemplo:** a pessoa chega domingo às 22h (horário de Brasília). Para ela e para o negócio, é domingo. Para o
  endpoint, já é a semana seguinte.
- **Por que é defeito:** a coorte não corresponde à semana do cliente (BDR-005), e o relatório do time de dados
  pode cortar a semana em outro horário. Pior: o mesmo código dá outro número se alguém mudar o fuso do servidor.
- **Efeito na nossa base:** 46 de 2.385 novatos (1,9%) mudam de semana.
- **Correção:** `date_trunc('week', primeira_vez AT TIME ZONE 'America/Sao_Paulo')`, com o fuso explícito no SQL. Com
  outros países, o fuso vem de uma tabela por país (ARQUITETURA §13).

**5. O retorno não filtra o país.** O `WHERE pais = $3` está só na subconsulta `primeira`, que escolhe os novatos.
O `EXISTS`, que procura o retorno, olha qualquer conversa da mesma pessoa, em qualquer país.
- **Exemplo:** a pessoa estreia no Brasil e, na semana seguinte, só usa o assistente numa viagem a Portugal (ou por
  uma VPN com saída lá). O dashboard do Brasil conta essa pessoa como "voltou".
- **Por que é defeito:** o denominador é "novatos no Brasil", mas o numerador é "voltou em qualquer lugar". As duas
  partes da taxa falam de populações diferentes. Com outros países no dashboard, piora: a mesma pessoa pode ser
  novata em dois países e voltar "nos dois" com uma conversa só.
- **Efeito na nossa base:** 0. Na base pública, nenhum IP brasileiro tem conversa em outro país. O defeito existe,
  mas só aparece com VPN, roaming ou mais países. O teste de regressão cobre o caso.
- **Correção:** `AND c.pais = $3` dentro do `EXISTS`.

**Um ponto que não é defeito:** a regra "retorno só depois de 1 hora". Ela é uma **definição** de retorno, não um
erro de código. A nossa definição usa "nova sessão" (pausa de 30 min, BDR-004), e a diferença é de −1,6 p.p.
(notebook 03). A correção mantém a regra de 1 hora para mudar só o que é defeito.

**A correção da carga.** O diff mostra o código do enunciado (`-`) e o corrigido (`+`). O número entre colchetes
liga cada mudança ao defeito da tabela acima.

```diff
 def carregar_conversas(conversas: list[dict]) -> None:
     """Recebe as conversas do dia na base bruta e grava uma linha por conversa."""
     for c in conversas:
-        chave = f"{c['hashed_ip']}|{c['header']['user-agent']}"
+        respostas = [t["timestamp"] for t in c["conversation"] if t["timestamp"] is not None]   # [2]
         db.execute("""
             INSERT INTO analytics.conversas
-                (conversa_id, usuario_id, ultimo_turno, modelo, turnos, pais)
+                (conversa_id, usuario_id, primeiro_turno, ultimo_turno, modelo, turnos, pais)  -- [2]
             VALUES
-                (%(conversa_id)s, %(usuario_id)s, %(ultimo_turno)s,
-                 %(modelo)s, %(turnos)s, %(pais)s)
-            ON CONFLICT (conversa_id) DO NOTHING
+                (%(conversa_id)s, %(usuario_id)s, %(primeiro_turno)s, %(ultimo_turno)s,
+                 %(modelo)s, %(turnos)s, %(pais)s)
+            ON CONFLICT (conversa_id) DO UPDATE SET                                             -- [3]
+                primeiro_turno = LEAST(analytics.conversas.primeiro_turno, EXCLUDED.primeiro_turno),
+                ultimo_turno   = GREATEST(analytics.conversas.ultimo_turno, EXCLUDED.ultimo_turno),
+                turnos         = GREATEST(analytics.conversas.turnos, EXCLUDED.turnos)
         """, {
             "conversa_id": c["conversation"][0]["turn_identifier"],
-            "usuario_id": sha256(chave.encode()).hexdigest(),
+            "usuario_id": sha256(c["hashed_ip"].encode()).hexdigest(),                           # [1]
+            "primeiro_turno": min(respostas),                                                    # [2]
             "ultimo_turno": c["timestamp"],
             "modelo": c["model"],
             "turnos": c["turn"],
             "pais": c["country"],
         })
```

| Mudança | Defeito | O que muda |
|---|---|---|
| `usuario_id` = `sha256(hashed_ip)`, sem o user-agent | [1] chave | A pessoa é a mesma enquanto o IP for o mesmo (BDR-001). Trocar de navegador ou mandar um user-agent por conversa não cria "novo" |
| Nova coluna `primeiro_turno` = a 1ª resposta do assistente | [2] fim × começo | A 1ª vez e o retorno passam a usar o começo da conversa. Os turnos do usuário não têm horário: vale a 1ª resposta |
| `DO NOTHING` → `DO UPDATE` com `LEAST` e `GREATEST` | [3] carga diária | A 2ª chegada de uma conversa atualiza o último turno e os turnos. `LEAST` e `GREATEST` deixam a carga idempotente: rodar 2 vezes dá o mesmo resultado |

**A correção do endpoint** (só o SQL muda; o TypeScript em volta fica igual):

```diff
 WITH primeira AS (
-    SELECT usuario_id, min(ultimo_turno) AS primeira_vez
+    SELECT usuario_id, min(primeiro_turno) AS primeira_vez                                   -- [2]
     FROM analytics.conversas WHERE pais = $3 GROUP BY usuario_id
 )
-SELECT date_trunc('week', p.primeira_vez)::date AS semana,
+SELECT date_trunc('week', p.primeira_vez AT TIME ZONE 'America/Sao_Paulo')::date AS semana,  -- [4]
        count(*) AS novos,
        count(*) FILTER (WHERE EXISTS (
            SELECT 1 FROM analytics.conversas c
-           WHERE c.usuario_id = p.usuario_id
-             AND c.ultimo_turno >  p.primeira_vez + interval '1 hour'
-             AND c.ultimo_turno <= p.primeira_vez + interval '7 days'
+           WHERE c.usuario_id = p.usuario_id AND c.pais = $3                                   -- [5]
+             AND c.primeiro_turno >  p.primeira_vez + interval '1 hour'                        -- [2]
+             AND c.primeiro_turno <= p.primeira_vez + interval '7 days'                        -- [2]
        )) AS voltaram_7d
 FROM primeira p
-WHERE p.primeira_vez >= $1 AND p.primeira_vez < $2
+WHERE (p.primeira_vez AT TIME ZONE 'America/Sao_Paulo')::date >= $1                            -- [4]
+  AND (p.primeira_vez AT TIME ZONE 'America/Sao_Paulo')::date <  $2
 GROUP BY 1 ORDER BY 1;
```

| Mudança | Defeito | O que muda |
|---|---|---|
| `min(ultimo_turno)` → `min(primeiro_turno)` | [2] fim × começo | A pessoa chega quando a 1ª conversa começa |
| `c.ultimo_turno` → `c.primeiro_turno` no `EXISTS` | [2] fim × começo | O retorno conta pelo começo da conversa de retorno. Uma conversa aberta 10 min depois e que dura 2 h deixa de virar "retorno" |
| `AT TIME ZONE 'America/Sao_Paulo'` na semana e no filtro de período | [4] fuso | A semana e o período seguem o calendário do Brasil (BDR-005), e não dependem do fuso do servidor |
| `AND c.pais = $3` no `EXISTS` | [5] país | Numerador e denominador falam da mesma população: novatos no Brasil que voltaram no Brasil |

O defeito [1] não aparece no SQL: o endpoint lê o `usuario_id` que a carga gravou. Por isso, corrigir só o endpoint
não resolve o incidente.

A regra "> 1 hora" fica (veja "Um ponto que não é defeito", acima). A coluna `primeiro_turno` entra por migration
(`ALTER TABLE ... ADD COLUMN`).

**Teste de regressão** ([tests/test_incidente.py](../tests/test_incidente.py), 12 casos). Cada caso roda nas duas
versões e tem resposta conhecida:

| Caso | Referência | Corrigida |
|---|---|---|
| Mesma pessoa troca de navegador | 2 novos, 0 voltaram | 1 novo, 1 voltou |
| User-agent único em 3 conversas (a assinatura) | 3 novos, 0 voltaram | 1 novo, 1 voltou |
| Conversa de domingo 19h (SP) que passa da meia-noite UTC | semana de 20/11 | semana de 13/11 |
| Retorno vindo de outro país | conta | não conta |
| Conversa que continua no dia seguinte (2 cargas) | último turno do dia 1 | último turno do dia 2 |
| **Nosso produto:** a chave padrão é o IP, sem user-agent | — | quebra se alguém mudar a chave |

## 4. O que fazer além de corrigir o código

1. **Reprocessar o histórico.** A chave muda para todas as linhas: recarregue a base analítica inteira a partir da
   bruta. Upsert não basta, porque o `usuario_id` antigo fica nas linhas já gravadas.
2. **Recalcular o que depende do usuário.** Agregados, caches e qualquer outro indicador que conte pessoas
   (ativos, novos, frequência). O número de pessoas cai em toda a série, não só em 20/11: ~5% nas semanas
   anteriores (a diferença que o dashboard sempre teve sobre o relatório; na base pública, 17,6%).
3. **Registrar a correção, sem aviso extra na tela.** A explicação vai para quem decide: a mensagem à gerente
   (item 5) e este relatório do incidente. Na tela, basta o rodapé que já existe: a correção muda a chave do
   usuário, então muda a **versão das definições** que o rodapé mostra. Quem guardou um número antigo liga o valor
   novo à correção por essa versão.
4. **Achar a origem do user-agent variável** com o time do produto (versão do app, SDK, proxy). A correção da chave
   protege o indicador, mas o time precisa saber que o cliente mudou.
5. **Evitar a volta do problema:**
   - **teste de regressão** da chave (acima), que roda no CI de todo PR;
   - **alerta de razão** "chaves por IP" e "% de novos com uma conversa só": se passar de 3 desvios-padrão das
     8 semanas anteriores, a carga marca a execução e avisa antes da publicação;
   - **reconciliação pós-carga** com um caminho independente (a contagem por IP direto na bruta, como o
     relatório). Diferença acima da tolerância segura a publicação do número;
   - **a definição de usuário tem dono:** mudar a chave exige um BDR novo (hoje, o BDR-001) e aprovação.
6. **Postmortem** sem culpados: linha do tempo, causa, impacto, o que muda no processo.

## 5. O que eu diria à gerente de produto

**Durante (no mesmo dia, antes de ter a causa):**
> "Vimos a queda e já estamos investigando. Os primeiros sinais indicam um problema de **contagem**, não de
> comportamento: o número de pessoas que voltaram ficou igual; o que quase dobrou foi o número de 'pessoas novas'
> contadas na semana. O relatório do time de dados, que conta de outro jeito, não mostra queda. Por enquanto,
> não use o número da semana de 20/11 para decisões. Marcamos o número como 'em revisão' no dashboard e voltaremos com a causa."

**Depois (com a causa e a correção):**
> "O retorno não caiu: está estável em ~30%. A partir de 20/11, parte do tráfego passou a mandar uma identificação
> de navegador diferente a cada conversa, e o dashboard contou cada conversa dessas como uma pessoa nova. Corrigimos
> a contagem, que agora identifica a pessoa só pela rede, como o relatório. Reprocessamos todo o histórico; por isso,
> o número de pessoas caiu cerca de 5% também nas semanas anteriores; o relatório do incidente detalha a mudança. Para não
> repetir: um teste automático trava essa regra, e um alerta avisa o time se a contagem de pessoas novas sair do
> padrão antes de o número chegar ao dashboard."

---

## 6. Monitoramento (§4.1)

### O que registrar em cada camada

| Camada | O que registrar | Onde está na entrega |
|---|---|---|
| Carga | id da execução, arquivos lidos e SHA-256, revisão da base, linhas lidas, gravadas e rejeitadas por motivo, duração, versão das definições, versão do prompt e do modelo de classificação, status e erro | tabela `meta_carga` + log JSON por etapa ([etl/carga.py](../etl/carga.py)) |
| Base analítica | versão do schema, carga que gerou cada linha (`carga_id`), contagens por semana | `alembic_version`, coluna `carga_id`, views |
| Backend | `request_id`, rota, parâmetros, status, duração, linhas lidas, carga usada | log JSON por requisição + header `X-Request-ID` ([backend/api/observabilidade.py](../backend/api/observabilidade.py)) |
| Tela | endpoint, `request_id`, carga, data dos dados e versão das definições de cada número | rodapé de cada tela |

Com isso, um número da tela leva ao `request_id`, daí ao `carga_id`, daí aos arquivos da bruta com o SHA-256.
O caminho de volta, da tela até a origem, existe sem adivinhação.

### Como perceber a divergência antes do cliente

| Sinal | Regra | Estado |
|---|---|---|
| Linhas rejeitadas por motivo | variação acima de 20% contra a carga anterior | gravado em `meta_carga.rejeitadas` |
| Chaves por IP e % de novos com uma conversa só | fora de 3 desvios-padrão das 8 semanas anteriores | proposto (teria pego o incidente) |
| Reconciliação com um caminho independente | KPIs da base analítica × contagem direta na bruta; diferença > 2% segura a publicação | proposto (cortado em 13/11, PROJECT §14) |
| Volume diário da coleta | dia com menos de 15% da mediana = falha de coleta (BDR-006) | na definição; o alerta em produção é proposto |
| Saúde da API e idade da carga | `/api/health` devolve a última carga; alerta se tiver mais de 26 h | endpoint pronto; alerta no CloudWatch proposto |

### Testes automatizados

| Teste | O que pega | Arquivo |
|---|---|---|
| Definições com base sintética e resposta conhecida | mudança silenciosa de sessão, retorno, censura, fuso | [tests/test_definicoes.py](../tests/test_definicoes.py) |
| Carga real ponta a ponta | número da análise ≠ número gravado; dado pessoal na base; carga duplicada; carga com erro apagando a anterior | [tests/test_carga.py](../tests/test_carga.py) |
| Contrato da API + snapshot do OpenAPI | mudança de contrato sem revisão; Wilson do SQL ≠ Wilson do Python; k-anonimato | [tests/test_api.py](../tests/test_api.py) |
| Regressão do incidente | chave do usuário com user-agent; os 4 defeitos secundários | [tests/test_incidente.py](../tests/test_incidente.py) |

### Como uma mudança chega à produção

1. Branch e PR. O CI roda `ruff` e `pytest` (com um Postgres de serviço para os testes de banco).
2. Toda mudança de schema é uma migration do Alembic, revisada no PR. Toda mudança de definição muda a
   `VERSAO_DEFINICOES` e exige um BDR.
3. Homologação com uma cópia da base: roda a carga, compara os KPIs com a produção e mostra a diferença no PR.
4. Deploy no ECS (imagem nova da API e do dashboard); a carga roda no Glue Python Shell e aplica as migrations antes
   de gravar (ADR-006).
5. Depois do deploy: a reconciliação e o `/api/health` confirmam o número e a carga.
