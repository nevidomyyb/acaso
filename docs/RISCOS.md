# Riscos e decisões em aberto

Riscos da solução e decisões que dependem do time ou do cliente. Atualizado a cada achado.

| # | Risco | Efeito no resultado | Mitigação no projeto | Decisão a escalar (quem) |
|---|---|---|---|---|
| 1 | Usuário = IP (compartilhado ou dinâmico) | IP dinâmico subestima o retorno (≥ 2% dos novos IPs); IP compartilhado junta pessoas | Sensibilidade no BDR-001 | Login ou ID anônimo persistente no produto (cliente) |
| 2 | Base pública sem conversas tóxicas e com PII removida | Retorno subestimado; fator "toxicidade" não mensurável | Registro explícito; o fator sai da análise | Usar o log completo do produto (cliente) |
| 3 | Base pequena: 2.219 pessoas, ~39 por semana | IC semanal de ±15 p.p.; efeitos pequenos não aparecem | Coorte mensal; aviso de amostra pequena | Aceitar leitura mensal (cliente) |
| 4 | Efeitos observacionais | Confusão residual por variáveis não observadas | Ajuste por perfil + IPW; bruto × ajustado | Teste A/B antes de mudanças grandes (cliente) |
| 5 | Modelo confundido com o tempo | Não há GPT-4 no Brasil de 24/06 a 07/11/2023 | Comparar modelos só nos períodos com os dois | — |
| 6 | Falhas de coleta (6 dias) | Coortes vizinhas com retorno subestimado | Exclusão do denominador (BDR-006); marca na tela | Alerta de volume diário na coleta (time de dados) |
| 7 | Erro da classificação por LLM | Ruído no efeito de tema e recusa | Validação manual (meta ≥ 85%); regex de recusa | Aceitar a acurácia medida (cliente) |
| 8 | Dados pessoais no texto bruto | Exposição de dados | Texto fora da base analítica; k-anonimato (k = 20) | Retenção e acesso à base bruta (jurídico) |
| 9 | Validade externa | Serviço gratuito de pesquisa, 2023–2024, GPT-3.5/4 | Registro explícito | Validar com dados do produto real (cliente) |
| 10 | Custo AWS | Gasto fora do previsto | AWS Budgets; classificação em batch | Orçamento e alerta (cliente) |
| 11 | Bedrock bloqueado na conta nova: on-demand com cota 0; batch com "account is not authorized" | Classificação de tema e recusa atrasa ou não sai | Plano pago; pedidos de cota; caso no AWS Support; contingência por palavras-chave + regex até sáb 14/11 | Liberação da conta (AWS Support) |
