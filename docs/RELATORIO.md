# Relatório — o que faz quem experimentou o assistente voltar em 7 dias

WildChat-1M, conversas do Brasil, abril/2023 a abril/2024. O detalhe de cada número está nos documentos citados.

## 0. Resumo

- **28,6% dos novatos voltam em até 7 dias** (IC 95%: 26,8–30,5%; 635 de 2.219).
- **O que mais pesa é a recusa total na estreia:** quem leva uma recusa na 1ª conversa volta 17,4 p.p. menos.
- **O GPT-4 não faz voltar mais.** A vantagem bruta vem do mês em que a pessoa chegou, não do modelo.
- A decisão é rápida: **55% dos retornos acontecem em até 6 horas**.
- A semana atípica (julho/2023) mudou a **taxa**, não o perfil de quem chegou.

## 1. Três achados e a decisão de cada um

| Achado | Número (IC 95%) | Decisão | Como confirmar |
|---|---|---|---|
| A recusa total na 1ª conversa afasta | **−17,4 p.p.** (−25,4 a −9,4), com perfil e mês iguais. Resiste a 4 checagens (de −10,0 a −16,2) | Revisar a política de recusa nos temas em que ela é evitável; trocar recusa total por resposta parcial com orientação | Teste A/B da política nova, medindo o retorno em 7 dias |
| A estreia decide cedo | **55%** dos retornos em 7 dias acontecem em até 6 h; 94% dos retornos em 30 dias caem nos 7 primeiros | Investir na 1ª resposta e num convite de retorno no mesmo dia | Teste A/B do convite; acompanhar o retorno em 6 h e em 24 h |
| O modelo mais caro não traz retorno | GPT-4: bruto +0,6 p.p.; no mesmo mês e perfil, **−3,7** (−9,4 a +2,0) | Não usar o GPT-4 como alavanca de retenção sem um teste | Teste A/B de modelo na estreia |

Deixado de fora: conselho pessoal (+17,1 p.p., n = 49). Com 17 comparações, ~1 resultado pode ser acaso.

## 2. Como medimos

| Conceito | Definição | Registro |
|---|---|---|
| Usuário | `hashed_ip` (não existe login) | BDR-001 |
| Sessão | respostas do assistente sem pausa de 30 min | BDR-002 |
| Estreia (1ª experiência) | a 1ª sessão do usuário na base | BDR-003 |
| Retorno em 7 dias | nova sessão até 7×24 h do início da 1ª | BDR-004 |
| Denominador | novatos observáveis por 7 dias, sem falha de coleta na janela (2.219) | BDR-006 |

**Quanto a definição muda o número:** de 18,9% (retorno só em outro dia do calendário) a 34,0% (pausa de 15 min
para nova sessão). As escolhas e o efeito de cada uma estão em [METODOLOGIA.md](METODOLOGIA.md) §2 e nos
[BDRs](bdr/README.md).

## 3. O que os dados mostram

1. **Uso concentrado:** 1% dos IPs (23) faz 41% das conversas; um IP sozinho faz 13%. O retorno conta cada pessoa
   uma vez, então essa concentração não distorce a taxa.
2. **Falhas de coleta:** 6 dias com quase nenhuma conversa no mundo todo. 87 novatos saem do denominador, porque
   não tiveram chance de voltar.
3. **O modelo se confunde com o tempo:** não há GPT-4 no Brasil de julho a outubro/2023. Comparar modelos sem olhar
   o mês mede o mês.
4. **A estreia por saudação ("oi", "teste") é comum e volta menos:** 23% dos novatos; 21,9% de retorno.
5. **O tema da estreia vem de um LLM** (Qwen3-8B numa EC2, ADR-004), conferido em 151 conversas rotuladas à mão,
   às cegas: 83,8% de acerto em 7 grupos ([METODOLOGIA_LABEL.md](METODOLOGIA_LABEL.md)).

Problemas de qualidade e tratamento: notebook [01_discovery](../analysis/01_discovery.ipynb). Gráficos da estreia:
[02_eda](../analysis/02_eda.ipynb).

## 4. Causa ou seleção

- **Método:** uma regressão compara pessoas iguais em tema, horário, idioma, dispositivo, estado e mês. A diferença
  entre o efeito bruto e o ajustado é **seleção** (o perfil de quem tem o fator).
- **Exemplo:** o GPT-4 parece ajudar (+0,6 p.p.) só porque existe nos meses que já voltam mais; no mesmo mês e
  perfil, fica em −3,7 p.p.
- **O que prova:** a associação, com o perfil e o mês controlados.
- **O que não prova:** causa. Um fator fora dos dados (motivação, origem do tráfego) pode explicar parte do efeito.
  Os efeitos principais pedem um teste A/B.
- **A semana atípica:** 17 e 24/07/2023 têm 8,6% de retorno (5 de 58; IC 3,7–18,6%). O perfil de quem chegou era o
  de sempre (taxa esperada: 28,6–29,8%), então **a taxa caiu, o perfil não mudou**. O resto do mundo não caiu junto:
  a queda é só do Brasil, e a causa não aparece nos dados.

Detalhe: notebook [04_efeitos_e_confusao](../analysis/04_efeitos_e_confusao.ipynb).

## 5. O que os dados permitem medir, e o que falta

| Permitem | Não permitem | Faltaria |
|---|---|---|
| Retorno por IP, com IC | Saber se o IP é uma pessoa (IP dinâmico ou compartilhado) | Login ou identificador do aparelho |
| Efeito de tema, recusa, horário, modelo | Saber se a resposta foi boa para a pessoa | Avaliação da resposta pela pessoa (👍/👎) |
| Perfil × taxa de uma semana | Saber de onde a pessoa veio | Origem do tráfego (campanha, busca, indicação) |
| — | Medir toxicidade: a base pública removeu as conversas tóxicas | O log completo do produto |
| — | Ver o que a pessoa fez na tela | Eventos de interface (copiou, regenerou, abandonou) |

## 6. Sugestões

| Para o assistente | Para o dashboard |
|---|---|
| Trocar a recusa total por resposta parcial com orientação, nos temas em que a recusa é evitável | Indicador "% de estreias com recusa total", por semana, com alerta |
| Responder melhor à saudação: 23% dos novatos começam assim e voltam menos (21,9%) | Curva de "tempo até voltar" (6 h, 24 h, 7 dias): mostra que a decisão sai cedo |
| Responder no idioma da pessoa: o idioma "outro" volta 8,0 p.p. menos | Alerta de qualidade do dado ("chaves por IP", falha de coleta): é o que teria pego o incidente |

## 7. Dashboard e arquitetura

- **Telas:** 2 telas com dados reais ("Quantos experimentam e quantos voltam?" e "O que na estreia faz voltar?").
  Cada número tem definição, fonte e IC, e as amostras pequenas aparecem esmaecidas.
- **Pilha:** `docker compose up` sobe tudo do zero, sem credenciais. Postgres com o SQL dos indicadores em views,
  API Flask com 4 endpoints (~15 ms) e Streamlit.
- **Produção (descrita):** 6 serviços AWS, ≈ US$ 70/mês. A classificação custou ≈ US$ 4,70 numa EC2.
- **Privacidade:** a base analítica não guarda texto, IP nem navegador; grupos com menos de 20 pessoas não
  aparecem (ADR-007).

Detalhe: [ARQUITETURA.md](ARQUITETURA.md) (inclui outros países, cache e endpoints) e [METODOLOGIA.md](METODOLOGIA.md)
§11 (indicadores e SQL).

## 8. Sustentação e o incidente

O "31% → 18%" da semana de 20/11/2023 é um erro de **contagem na carga**, não uma queda de retorno. A chave do usuário
inclui o user-agent; quando ele passa a variar por conversa, cada conversa vira uma "pessoa nova" que nunca volta.
A correção usa só o IP (BDR-001), reprocessa o histórico e fica travada por um teste de regressão.

Resposta completa, consultas, correções e monitoramento: [INCIDENTE.md](INCIDENTE.md).

## 9. Premissas principais

| Premissa | Se estiver errada |
|---|---|
| Um IP é uma pessoa | IP dinâmico separa uma pessoa em duas e baixa o retorno; com IP + navegador, o retorno sobe 2,2 p.p. |
| Sessão = pausa de 30 min | Com 15 min, 34,0%; com 60 min, 25,1% |
| O LLM classifica bem o tema e a recusa | Com o regex no lugar do LLM, a recusa dá −15,8 p.p.: o achado se mantém |
| A base pública representa o produto | É um serviço gratuito de pesquisa, de 2023–2024, com GPT-3.5 e GPT-4. Os números servem de método, não de meta |
| As falhas de coleta são do registro, não do uso | Se forem uso real, 87 pessoas voltam ao denominador, e a taxa continua em 28,6% |

Todos os riscos e as decisões a levar ao cliente: [RISCOS.md](RISCOS.md).

## 10. Uso de IA

- Usei o **Claude Code** em todo o trabalho: discovery, análise, código da carga, da API e do dashboard, testes e
textos. Usei o **Claude no navegador** para o primeiro passo do projeto, criar o plano de desenvolvimento e analisar o contexto do desafio, além disso também usei para montar o mini-app em que rotulei 151 conversas à mão, e um **LLM aberto
(Qwen3-8B) numa EC2** para classificar o tema e a recusa. 
- **Conferi:** a classificação contra os meus rótulos, feitos às cegas (83,8% em 7 grupos); cada número da carga contra o notebook; o SQL dos indicadores contra o Python (por teste). Glossário de dados e atualização do PROJECT.md e CLAUDE.md conforme iamos avançando e mudando o escopo.
- **Corrigi:** Alucinaões de números dados como fatos antes mesmo de rodar a análise. Claude tinha tratado o compose up como se fosse re-baixar todos os dados sempre que fosse rodar o projeto. Fluxo de desenvolvimento e commit: o claude tentava commitar os dados brutos sempre, além de fazer um fluxo de commit diferente do que eu tinha definido para o projeto (por entrega/dia)
- **Descartei:** o Bedrock (conta sem cota); um método estatístico mais complexo, trocado por regressão linear; duas telas a mais para validação da saúde dos dados (descartado para manter o projeto viável no prazo). Utilização de múltiplos serviços na AWS na sugestão de deploy.
- **Horas:** cerca de 10,5 h (~1,5 h por dia, de 10 a
16/11). O log dia a dia está em [USO_DE_IA.md](USO_DE_IA.md).
