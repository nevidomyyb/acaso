# Dúvidas para a Acaso

**Para:** nathalia.anjos@aca.so, daniele.cardoso@aca.so
**Prazo:** qua 11/11, de manhã
**Assunto:** Desafio técnico — dúvidas de escopo

> Enviado em 11/11. O desfecho de cada item está no fim deste arquivo.

---

Olá, Nathalia e Daniele, tudo bem?

Tenho quatro dúvidas de escopo. Ao lado de cada uma, indico a premissa que sigo se não houver resposta a tempo.

1. **Classificação por LLM.** Posso entregar a classificação de tema e recusa já calculada e versionada no repositório? Assim o `docker compose up` sobe sem credenciais AWS.
   *Premissa:* entrego a classificação pronta e o script que a refaz na AWS.

2. **Frontend.** Há uma stack preferida para o frontend?
   *Premissa:* a escolha é livre.

3. **Filtro Brasil.** Uso só `country = 'Brazil'`, por conversa. Essa regra atende?
   *Premissa:* sim. Não incluo conversas em português de outros países (Portugal, Moçambique etc.).

4. **Base bruta no repositório.** Posso versionar o recorte do Brasil (22 MB) no repositório? Assim a carga roda sem baixar a base inteira (3,4 GB).
   *Premissa:* versiono o recorte e o script que o gera a partir da base pública.

Agradeço desde já!

---

## Desfecho (16/11)

| # | Dúvida | O que a entrega faz | Registro |
|---|---|---|---|
| 1 | Classificação pronta no repositório | A classificação vai versionada em `data/enriched/`. O compose só a confere; sem o arquivo, refaz na EC2 | ADR-004 |
| 2 | Stack do frontend | Streamlit com tema próprio, lendo só a API | ADR-003 |
| 3 | Filtro Brasil | Só `country = 'Brazil'` | BDR-007 |
| 4 | Recorte no repositório | **Mudou:** o recorte **não** vai para o git. O `docker compose up` baixa a base pública (SHA-256 conferido) e gera o recorte; se `./data` já tem a base, nada é baixado de novo | README ("Como subir"); ARQUITETURA §4 |
