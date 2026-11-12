# Dúvidas para a Acaso

**Para:** nathalia.anjos@aca.so, daniele.cardoso@aca.so
**Prazo:** qua 11/11, de manhã
**Assunto:** Desafio técnico — dúvidas de escopo

> Rascunho. A pessoa candidata envia. Se não houver resposta a tempo, a premissa de cada item vale.

---

Olá, Nathalia e Daniele, tudo bem?

Tenho quatro dúvidas de escopo. Ao lado de cada uma, indico a premissa que sigo se não houver resposta a tempo.

1. **Classificação por LLM.** Posso entregar a classificação de tema e recusa já calculada no Amazon Bedrock e versionada no repositório? Assim o `docker compose up` sobe sem credenciais AWS.
   *Premissa:* entrego a classificação pronta e o script que a refaz no Bedrock.

2. **Frontend.** Há uma stack preferida para o frontend?
   *Premissa:* a escolha é livre.

3. **Filtro Brasil.** Uso só `country = 'Brazil'`, por conversa. Essa regra atende?
   *Premissa:* sim. Não incluo conversas em português de outros países (Portugal, Moçambique etc.).

4. **Base bruta no repositório.** Posso versionar o recorte do Brasil (22 MB) no repositório? Assim a carga roda sem baixar a base inteira (3,4 GB).
   *Premissa:* versiono o recorte e o script que o gera a partir da base pública.

Agradeço desde já!
