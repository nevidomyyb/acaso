# IAM do projeto

Menor privilégio para a classificação de tema e recusa (ADR-004). O dashboard não usa estas credenciais.

## Identidades

| Identidade | Arquivo | Uso |
|---|---|---|
| Usuário `acaso-etl` | `usuario-acaso-etl.json` | Scripts locais: leem e gravam no bucket do projeto. Só S3 |
| Role da instância `acaso-classificacao` | [../ec2/role-ec2-confianca.json](../ec2/role-ec2-confianca.json) + [../ec2/role-ec2-s3.json](../ec2/role-ec2-s3.json) | A EC2 de classificação: acesso por SSM e leitura/gravação só no prefixo `cpu/*` do bucket |

O LLM roda na própria instância. Por isso nenhuma identidade precisa de permissão de serviço de IA.

## Procedimento

1. Substitua `<BUCKET>` em `usuario-acaso-etl.json`. Confira que não sobrou nenhum marcador.
2. Crie o bucket em `us-east-1`, com acesso público bloqueado.
3. Crie o usuário `acaso-etl` sem acesso ao console. Anexe `usuario-acaso-etl.json` como política inline.
4. Crie uma access key do usuário. Copie os valores para o `.env` (modelo em `.env.example`).
5. Crie o AWS Budgets com uma conta administradora. O usuário `acaso-etl` não gerencia custos.

A role da instância é criada e apagada pelo [classificacao.sh](../ec2/classificacao.sh), com o perfil administrador do AWS CLI.

## Observações

- Conta de desenvolvimento do desafio: o `acaso-etl` usa as políticas gerenciadas `AmazonS3FullAccess` + `AmazonBedrockFullAccess`. Em produção, use a política inline deste diretório (menor privilégio).
- A role `AmazonBedrock-acaso-batch` continua na conta, sem uso. Ela ficou do teste do Bedrock (opção A do ADR-004). Apague quando quiser.
- Ao fim do desafio, desative a access key e apague o usuário.
