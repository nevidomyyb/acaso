# BDR-009 — Tema da 1ª experiência

**Status:** aceito · 2026-11-12

## Contexto
O tema diz o que a pessoa foi fazer na estreia. Um LLM aberto classifica as 3.361 conversas da 1ª sessão em 11 temas (ADR-004). A validação manual de 151 conversas, às cegas, mede 71,4% de acerto nos 11 temas, abaixo da meta de 85%. Os erros ficam em temas vizinhos: estudo, trabalho e conhecimento geral.

## Opções
| Opção | Acerto ponderado (IC 95%) | Prós | Contras |
|---|---|---|---|
| A) 11 temas | 71,4% (64,4–78,5%) | Mais detalhe | Ruído alto; `conteudo_adulto` tem 18 usuários (abaixo de k = 20) |
| B) 7 grupos | 83,8% (78,9–88,7%) | Perto da meta; todo grupo tem ≥ 49 usuários | Junta estudo, trabalho e conhecimento geral |
| C) Sem tema | — | Sem ruído | Perde a pergunta "o que a pessoa foi fazer" |

## Decisão
Opção B. O grupo `tarefa_conhecimento` junta conhecimento_geral, estudo_escola e trabalho_profissional. O grupo `criativo_entretenimento` junta criativo_ficcao, roleplay_personagem e conteudo_adulto. Os outros 5 temas ficam iguais. O tema do usuário é o da **1ª conversa da 1ª sessão**.

## Impacto no resultado
- Usuários por grupo (2.219 elegíveis): tarefa_conhecimento 881 · saudacao_teste 516 · programacao_tecnologia 301 · criativo_entretenimento 292 · traducao_reescrita 110 · outro 70 · conselho_pessoal 49.
- 21% dos usuários têm mais de 1 conversa na 1ª sessão. Em 43% desses, o grupo muda. A 1ª conversa mostra a intenção de chegada.
- Os 11 temas ficam só nos gráficos descritivos, com o acerto de cada tema ao lado.
- Se a premissa estiver errada: rótulo errado em geral aproxima de zero a diferença entre grupos. Com 7 grupos, isso não é garantido para cada grupo. Os grupos vêm da matriz de confusão, então 83,8% pode estar um pouco acima do real.
- Código: `GRUPO_TEMA` em `etl/definicoes.py`. Validação: `etl/validacao_classificacao.py avaliar`.
