# ADR-007 — Privacidade: o que o dashboard mostra e o que nunca mostra

**Status:** aceito · 2026-11-15 (k-anonimato decidido em 14/11)

## Contexto
As conversas podem conter dados pessoais, e o enunciado pede que digamos o que o dashboard mostra e o que nunca
mostra (§2.2). O enunciado não exige k-anonimato. Os filtros do dashboard são livres (período × dimensão), o que
cria recortes de 1 ou 2 pessoas, como "março, Maranhão, celular".

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A) Só agregados; base analítica sem texto nem identificadores; k-anonimato (k = 20) nos recortes | A regra "nunca mostra" fica verificável e testada; protege contra o cruzamento de atributos | Alguns recortes pequenos ficam ocultos (com aviso) |
| B) Só agregados, sem k | Nenhum número some da tela | Recorte de 2 pessoas aparece; a privacidade fica só na promessa |
| C) A + ruído (privacidade diferencial) | Proteção formal | Distorce números já pequenos; difícil de explicar a um cliente de negócio |
| D) Texto na base analítica, com acesso restrito | Permite abrir exemplos de conversa | Dado pessoal no banco que o dashboard lê; viola a regra do projeto |

## Decisão
Opção A. Ela protege onde o risco existe (o cruzamento de atributos), custa uma condição na view e um teste, e é
fácil de explicar.

## Consequências
- **Mostra:** contagens, taxas, IC e efeitos agregados, com definição e fonte.
- **Nunca mostra:** texto das conversas, IP, user-agent, identificador de pessoa, nível de dimensão com menos de 20
  novatos. O total da coorte (sem atributo) aparece mesmo com n < 20, esmaecido.
- A base analítica não guarda texto, `hashed_ip`, user-agent nem a chave md5 da análise. O usuário é um inteiro
  substituto (`usuario_sk`), sem tabela de mapeamento. O estado vem agrupado (menos de 20 → "outros").
- O texto só existe na base bruta e na EC2 de classificação (ADR-004); nada sai da conta AWS. A API lê com um papel
  só de leitura. Testes: nenhuma coluna proibida na base; nível com n < 20 volta sem números.
- **Se o risco for maior** (dados do produto real, com login): suba o k, aplique a regra também ao total da coorte, e
  leve a retenção e o acesso à base bruta ao jurídico (RISCOS, risco 8).
