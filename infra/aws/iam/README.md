# IAM do projeto

Menor privilégio para o único usuário do projeto e para as roles que ele cria. O `docker compose up` não precisa
de credenciais: a classificação já vem pronta em `data/enriched/`. As credenciais só servem para refazer a
classificação na EC2 (ADR-004).

## Identidades

| Identidade | Arquivo | Uso |
|---|---|---|
| Usuário `acaso-operador` | [usuario-acaso-operador.json](usuario-acaso-operador.json) (política gerenciada `acaso-operador`) | Scripts locais e o serviço `classificacao` do compose: S3 do bucket, EC2 de classificação, SSM e roles `acaso-*` |
| Limite de permissões `acaso-limite` | [limite-acaso.json](limite-acaso.json) | O máximo que **qualquer** role criada pelo operador pode fazer |
| Role `acaso-classificacao` | [../ec2/role-ec2-confianca.json](../ec2/role-ec2-confianca.json) + [../ec2/role-ec2-s3.json](../ec2/role-ec2-s3.json) | A EC2 de classificação: SSM e o prefixo `cpu/*` do bucket. O operador cria e apaga |

## O que o operador pode e não pode fazer

| Pode | Não pode |
|---|---|
| Ler, gravar e apagar objetos no bucket do projeto | Acessar outro bucket |
| Criar EC2 **só** do tipo `c7i.4xlarge`, em `us-east-1`, com a tag `projeto=acaso` | Criar instância de outro tipo ou sem a tag |
| Encerrar instância e apagar security group **só** com a tag `projeto=acaso` | Encerrar recurso de outro projeto |
| Mandar comando SSM (`AWS-RunShellScript`) **só** para instância com a tag | Abrir sessão em outra instância |
| Criar roles `acaso-*` **só** com o limite `acaso-limite` anexado | Criar role sem limite, ou com outro nome |
| Passar roles `acaso-*` **só** para EC2, ECS (tarefas) e Glue | Passar role para outro serviço |
| — | Alterar as políticas `acaso-limite` e `acaso-operador`, ou tirar o limite de uma role (negação explícita) |
| — | Gerenciar usuários, chaves, custos ou faturamento |

**Por que o limite:** quem cria roles e anexa políticas pode criar uma role de administrador e assumi-la. O limite
fecha essa porta. Uma role `acaso-*` nunca passa do que está em `limite-acaso.json`, mesmo com
`AdministratorAccess` anexada. O limite já cobre as roles da implantação descrita no ADR-006: tarefa e execução do
ECS (ECR, Logs, Parameter Store), job do Glue (rede na VPC, conexão, S3) e a EC2 (agente SSM, S3).

## Procedimento (com uma conta administradora)

1. Copie os 2 JSON para `data/work/iam/` (fora do git). Na cópia, troque `<BUCKET>` pelo nome do bucket e `<CONTA>`
   pelo ID da conta (12 dígitos). Confira que não sobrou marcador: `grep -n '<' data/work/iam/*.json` não mostra nada.
   Os arquivos deste diretório ficam com os marcadores: o ID da conta não vai para o git.
2. Crie o bucket em `us-east-1`, com acesso público bloqueado (se ainda não existir).
3. Crie a política gerenciada `acaso-limite` a partir de `limite-acaso.json`.
4. Crie a política gerenciada `acaso-operador` a partir de `usuario-acaso-operador.json`. Ela não cabe como
   inline (4.282 caracteres; o limite inline é 2.048).
5. Crie o usuário `acaso-operador` sem acesso ao console. Anexe só a política `acaso-operador`.
6. Crie uma access key do usuário. Copie os valores para o `.env` (modelo em [../../../.env.example](../../../.env.example)).
7. Confira: `aws sts get-caller-identity` deve mostrar `user/acaso-operador`.
8. Crie o AWS Budgets com a conta administradora. O operador não gerencia custos.

Comandos da CLI para os passos 3 a 6 (rode da raiz do repositório):

```bash
CONTA=<CONTA>
aws iam create-policy --policy-name acaso-limite   --policy-document file://data/work/iam/limite-acaso.json
aws iam create-policy --policy-name acaso-operador --policy-document file://data/work/iam/usuario-acaso-operador.json
aws iam create-user   --user-name acaso-operador --tags Key=projeto,Value=acaso
aws iam attach-user-policy --user-name acaso-operador --policy-arn arn:aws:iam::$CONTA:policy/acaso-operador
aws iam create-access-key  --user-name acaso-operador   # copie os 2 valores para o .env
```

## Observações

- O `acaso-operador` substitui o `acaso-etl` (só S3). Na conta de desenvolvimento, o `acaso-etl` tem
  `AmazonS3FullAccess` + `AmazonBedrockFullAccess`. Depois de criar o operador, desative a chave e apague o
  `acaso-etl`.
- A role `AmazonBedrock-acaso-batch` continua na conta, sem uso. Ela ficou do teste do Bedrock (opção A do
  ADR-004). Apague quando quiser.
- Para **implantar** a arquitetura do ADR-006 (criar RDS, ECS, ALB, Glue), o operador precisa de mais permissões
  de serviço. A entrega só descreve a implantação, então essas permissões ficam fora. As roles que esses serviços
  usam já cabem no limite.
- Ao fim do desafio, desative a access key e apague o usuário e as 2 políticas.
