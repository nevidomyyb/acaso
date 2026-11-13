# Riscos e decisões em aberto

Riscos da solução e decisões que dependem do time ou do cliente. Atualizado a cada achado.

| # | Risco | Efeito no resultado | Mitigação no projeto | Decisão a escalar (quem) |
|---|---|---|---|---|
| 1 | Usuário = IP (compartilhado ou dinâmico) | IP dinâmico subestima o retorno (≥ 2% dos novos IPs); IP compartilhado junta pessoas. Evidência local (13/11, notebook 02): o Rio de Janeiro tem 17,5% de retorno, contra 28,6%, nos dois dispositivos, e lá o user-agent raro reaparece em outro IP 2 a 3× mais. Parte da queda pode ser medição. O celular (−5 p.p. contra o desktop) tem a mesma suspeita | Sensibilidade no BDR-001 | Login ou ID anônimo persistente no produto (cliente) |
| 2 | Base pública sem conversas tóxicas e com PII removida | Retorno subestimado; fator "toxicidade" não mensurável | Registro explícito; o fator sai da análise | Usar o log completo do produto (cliente) |
| 3 | Base pequena: 2.219 pessoas, ~39 por semana | IC semanal de ±15 p.p.; efeitos pequenos não aparecem | Coorte mensal; aviso de amostra pequena | Aceitar leitura mensal (cliente) |
| 4 | Efeitos observacionais | Confusão residual por variáveis não observadas | Ajuste por perfil + IPW; bruto × ajustado | Teste A/B antes de mudanças grandes (cliente) |
| 5 | Modelo confundido com o tempo | Não há GPT-4 no Brasil de 24/06 a 07/11/2023 | Comparar modelos só nos períodos com os dois | — |
| 6 | Falhas de coleta (6 dias) | Coortes vizinhas com retorno subestimado | Exclusão do denominador (BDR-006); marca na tela | Alerta de volume diário na coleta (time de dados) |
| 7 | Erro da classificação por LLM | Ruído no efeito de tema e recusa | Validação manual medida em 12/11: tema 71,4% nos 11 temas → 7 grupos (83,8%, BDR-009); recusa total 8 de 9 corretas, regex como sensibilidade (BDR-010) | Aceitar a acurácia medida (cliente) |
| 8 | Dados pessoais no texto bruto | Exposição de dados | Texto fora da base analítica; k-anonimato (k = 20) | Retenção e acesso à base bruta (jurídico) |
| 9 | Validade externa | Serviço gratuito de pesquisa, 2023–2024, GPT-3.5/4 | Registro explícito | Validar com dados do produto real (cliente) |
| 10 | Custo AWS | Gasto fora do previsto | AWS Budgets; a EC2 de classificação se destrói em 10 h | Orçamento e alerta (cliente) |
| 11 | Conta AWS nova sem cota de LLM gerenciado: o Bedrock recusa todos os modelos (o Support confirmou em 12/11 que a liberação leva alguns ciclos de faturamento) e a cota de GPU é 0 no EC2 e no SageMaker | A classificação usa um modelo aberto de 8B, menor que um modelo gerenciado | LLM aberto em CPU numa EC2 (ADR-004); palavras-chave + regex como reserva; a validação manual mede a perda | Conta AWS com histórico, ou aceitar a acurácia medida (cliente) |
