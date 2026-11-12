# IAM do projeto

Menor privilégio para classificar conversas no Bedrock (ADR-004). O dashboard não usa estas credenciais.

## Identidades

| Identidade | Arquivo | Uso |
|---|---|---|
| Usuário `acaso-etl` | `usuario-acaso-etl.json` | Script de classificação: invoca o Haiku (on-demand), cria jobs de batch, lê e grava no bucket. |
| Role `AmazonBedrock-acaso-batch` | `role-bedrock-batch-confianca.json` + `role-bedrock-batch-permissoes.json` | O Bedrock assume esta role para ler a entrada e gravar a saída do batch no S3. |

O job de batch roda no serviço Bedrock, depois que o script termina. O serviço não usa as permissões do usuário. Por isso o `CreateModelInvocationJob` exige uma role própria (`roleArn`). O usuário só entrega a role ao serviço (`iam:PassRole`).

## Procedimento

1. Substitua `<ACCOUNT_ID>` e `<BUCKET>` nos três arquivos. Confira que não sobrou nenhum marcador.
2. Crie o bucket em `us-east-1`, com acesso público bloqueado.
3. Crie a role `AmazonBedrock-acaso-batch` com a política de confiança. Anexe a política de permissões.
4. Crie o usuário `acaso-etl` sem acesso ao console. Anexe `usuario-acaso-etl.json` como política inline.
5. Crie uma access key do usuário. Copie os valores para o `.env` (modelo em `.env.example`).
6. Crie o AWS Budgets com uma conta administradora. O usuário `acaso-etl` não gerencia custos.

## Observações

- O Haiku 4.5 só aceita batch via inference profile `us.anthropic.claude-haiku-4-5-20251001-v1:0`. O profile envia requisições para `us-east-1`, `us-east-2` e `us-west-2`. Por isso as políticas listam os três ARNs do modelo.
- O nome da role contém `AmazonBedrock`. Motivo: a política gerenciada `AmazonBedrockFullAccess` só permite `iam:PassRole` para roles com esse padrão no nome. Assim o batch funciona com a política inline e com a gerenciada.
- Conta de desenvolvimento do desafio: o `acaso-etl` usa as políticas gerenciadas `AmazonS3FullAccess` + `AmazonBedrockFullAccess`. Em produção, use a política inline deste diretório (menor privilégio).
- Ao fim do desafio, desative a access key e apague o usuário.

## Primeiro acesso ao Claude no Bedrock (uma vez por conta)

Sem estes passos, o `InvokeModel` falha com `ResourceNotFoundException: Model use case details have not been submitted`.

1. Entre no console com uma conta administradora, na região `us-east-1`.
2. Abra a página da Anthropic no Bedrock: `https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/providers/anthropic`. Outro caminho: **Model catalog** → **Claude Haiku 4.5** → abrir no playground.
3. Preencha o formulário de caso de uso (First Time Use). O site pode ser um perfil do GitHub ou a página de um projeto.
4. No playground, envie uma mensagem curta ao Claude Haiku 4.5. Essa 1ª chamada cria a assinatura no AWS Marketplace. Ela precisa de `aws-marketplace:Subscribe`, `Unsubscribe` e `ViewSubscriptions`, que a conta administradora tem e o `acaso-etl` não tem.
5. Se a resposta for `AccessDeniedException`, o acordo está pendente. A AWS envia um e-mail quando ele termina. Para ver o status: `aws bedrock get-foundation-model-availability --model-id anthropic.claude-haiku-4-5-20251001-v1:0` (campo `agreementAvailability`).

A conta precisa de uma forma de pagamento válida para compras no Marketplace. Depois do 1º acesso, o `acaso-etl` invoca o modelo sem permissões do Marketplace.

## Caso no AWS Support (conta nova com Bedrock bloqueado)

Situação em 12/11/2026: a conta está no plano pago, o modelo aparece como `AUTHORIZED`/`AVAILABLE`, mas as duas vias falham.

| Via | Erro |
|---|---|
| On-demand (`InvokeModel`) | `ThrottlingException: Too many tokens per day`; cotas RPM e TPM em 0 |
| Batch (`CreateModelInvocationJob`) | `ValidationException: Your account is not authorized to perform this action` |

O bloqueio é da conta, não do IAM nem da cota. Só o Support libera. Os 2 pedidos de cota de 12/11 abriram casos (`CASE_OPENED`). Responda num deles com o texto abaixo, em inglês.

```
Hello,

This account moved from the Free plan to the Paid plan on 2026-11-11.
I need Amazon Bedrock access to Anthropic Claude Haiku 4.5 in us-east-1. Two calls fail:

1. CreateModelInvocationJob (batch inference) returns:
   "ValidationException: Your account is not authorized to perform this action.
   Please create a support case."
2. InvokeModel with the inference profile us.anthropic.claude-haiku-4-5-20251001-v1:0
   returns "ThrottlingException: Too many tokens per day".
   The applied quotas L-CCA5DF70 and L-58BE175A are 0.

Model access is granted (agreementAvailability = AVAILABLE,
authorizationStatus = AUTHORIZED). The Anthropic use case form is submitted.

Use case: a one-off classification of 11,621 conversations from the public
WildChat-1M dataset (ODC-BY license) for a product retention analysis.
Each record gets a topic label and a refusal label.
Volume: one test batch job of 199 records, then one batch job of about
14 million input tokens. Expected cost: below USD 20. A monthly AWS Budget
of USD 20 is active.

Please:
- enable batch inference for this account;
- set the on-demand quotas for Claude Haiku 4.5 to the default values
  (10,000 requests per minute and 5,000,000 tokens per minute),
  or to a lower value you can approve.

Thank you.
```

O Service Quotas recusa pedido abaixo do valor padrão da AWS (`IllegalArgumentException`). O mínimo é 10.000 RPM (`L-CCA5DF70`) e 5.000.000 TPM (`L-58BE175A`).

Para consultar plano e cotas, use o perfil padrão do AWS CLI (administrador). O `acaso-etl` não tem `freetier:*` nem `servicequotas:*`.
