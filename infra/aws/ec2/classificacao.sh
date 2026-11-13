#!/usr/bin/env bash
# EC2 de classificação em CPU (ADR-004). Usa o perfil padrão do AWS CLI (administrador), nunca o .env.
#
#   classificacao.sh criar              role + instance profile + security group + instância
#   classificacao.sh pronto             mostra se o llama-server subiu (fim do user-data)
#   classificacao.sh setup              reaplica o user-data numa instância já criada (boot com falha)
#   classificacao.sh rodar PASTA        baixa entrada e executor do S3 e inicia a classificação
#   classificacao.sh log PASTA          últimas linhas do executor
#   classificacao.sh modelo CHAVE       baixa (com SHA-256) e troca o modelo do llama-server (chaves abaixo)
#   classificacao.sh exec "COMANDO"     roda um comando na instância (SSM)
#   classificacao.sh destruir           termina a instância e apaga role, profile e security group
#
# PASTA = nome da pasta em data/work (ex.: cpu_v2_qwen3_8b_sessao1_amostra40). Acesso só por SSM: sem SSH,
# sem porta aberta.
set -euo pipefail

# CHAVE -> "repositório revisão arquivo sha256". Mesmas chaves de MODELOS em etl/classificar_cpu.py.
declare -A MODELOS=(
  [qwen3_4b]="unsloth/Qwen3-4B-Instruct-2507-GGUF a06e946bb6b655725eafa393f4a9745d460374c9 Qwen3-4B-Instruct-2507-Q4_K_M.gguf 3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
  [qwen3_8b]="Qwen/Qwen3-8B-GGUF 7c41481f57cb95916b40956ab2f0b139b296d974 Qwen3-8B-Q4_K_M.gguf d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
)

NOME=acaso-classificacao
TIPO=${TIPO:-c7i.4xlarge}
ZONA=${ZONA:-us-east-1a}
DIR=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$DIR/../../.." && pwd)
BUCKET=$(grep -E '^ACASO_S3_BUCKET=' "$RAIZ/.env" | cut -d= -f2)
export AWS_PAGER="" AWS_DEFAULT_REGION=us-east-1
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY  # garante o perfil administrador

instancia() {
  aws ec2 describe-instances --filters "Name=tag:Name,Values=$NOME" \
    "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query "Reservations[].Instances[].InstanceId" --output text
}

ssm() {  # roda um script bash na instância e imprime a saída
  local id cid params
  id=$(instancia)
  params=$(jq -n --arg c "$1" '{commands: [$c], executionTimeout: ["3600"]}')
  cid=$(aws ssm send-command --instance-ids "$id" --document-name AWS-RunShellScript \
    --parameters "$params" --query Command.CommandId --output text)
  local estado=""
  for _ in $(seq 1 360); do  # até 30 min; o waiter do CLI desiste em ~100 s
    sleep 5
    estado=$(aws ssm get-command-invocation --command-id "$cid" --instance-id "$id" \
      --query Status --output text 2>/dev/null || echo Pending)
    case "$estado" in Pending|InProgress|Delayed) ;; *) break ;; esac
  done
  aws ssm get-command-invocation --command-id "$cid" --instance-id "$id" \
    --query "[Status, StandardOutputContent, StandardErrorContent]" --output text
}

trocar_modelo() {
  local repo rev arq sha
  read -r repo rev arq sha <<< "${MODELOS[$1]:?chave de modelo desconhecida: $1}"
  ssm "set -e; cd /opt/modelos
[ -f $arq ] || curl -fsSL -o $arq https://huggingface.co/$repo/resolve/$rev/$arq
echo '$sha  $arq' | sha256sum -c -
sed -i -E 's#-m /opt/modelos/[^ ]+#-m /opt/modelos/$arq#' /etc/systemd/system/llama.service
systemctl daemon-reload && systemctl restart llama
for _ in \$(seq 1 60); do curl -sf http://127.0.0.1:8080/health >/dev/null && break; sleep 5; done
curl -s http://127.0.0.1:8080/health; echo; grep -o 'modelos/[^ ]*' /etc/systemd/system/llama.service"
}

criar() {
  if ! aws iam get-role --role-name "$NOME" >/dev/null 2>&1; then
    aws iam create-role --role-name "$NOME" --assume-role-policy-document "file://$DIR/role-ec2-confianca.json" \
      --tags Key=projeto,Value=acaso >/dev/null
    aws iam attach-role-policy --role-name "$NOME" \
      --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
    aws iam put-role-policy --role-name "$NOME" --policy-name s3-prefixo-cpu \
      --policy-document "$(sed "s/<BUCKET>/$BUCKET/g" "$DIR/role-ec2-s3.json")"
    aws iam create-instance-profile --instance-profile-name "$NOME" >/dev/null
    aws iam add-role-to-instance-profile --instance-profile-name "$NOME" --role-name "$NOME"
    sleep 15  # propagação do instance profile
  fi
  local vpc sg subnet ami
  vpc=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query "Vpcs[0].VpcId" --output text)
  sg=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$NOME" "Name=vpc-id,Values=$vpc" \
    --query "SecurityGroups[0].GroupId" --output text)
  if [ "$sg" = "None" ]; then  # sem regra de entrada: o acesso é só por SSM
    sg=$(aws ec2 create-security-group --group-name "$NOME" --vpc-id "$vpc" \
      --description "acaso: classificacao em CPU, sem entrada" --query GroupId --output text)
  fi
  subnet=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" "Name=availability-zone,Values=$ZONA" \
    "Name=default-for-az,Values=true" --query "Subnets[0].SubnetId" --output text)
  ami=$(aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
    --query Parameter.Value --output text)
  aws ec2 run-instances --image-id "$ami" --instance-type "$TIPO" --subnet-id "$subnet" \
    --security-group-ids "$sg" --iam-instance-profile "Name=$NOME" \
    --user-data "file://$DIR/user-data.sh" --instance-initiated-shutdown-behavior terminate \
    --metadata-options HttpTokens=required \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=40,VolumeType=gp3,DeleteOnTermination=true}' \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NOME},{Key=projeto,Value=acaso}]" \
    --query "Instances[0].[InstanceId,InstanceType,Placement.AvailabilityZone]" --output text
}

rodar() {
  local p=$1 s3="s3://$BUCKET/cpu/$1"
  ssm "set -e; mkdir -p /opt/acaso/$p && cd /opt/acaso/$p
aws s3 cp --only-show-errors $s3/entrada.jsonl . && aws s3 cp --only-show-errors $s3/llm_runner.py .
nohup python3 llm_runner.py --entrada entrada.jsonl --saida saida.jsonl --paralelo 4 --sync-cada ${SYNC:-50} \
  --s3-saida $s3/saida.jsonl > runner.log 2>&1 &
sleep 2; cat runner.log"
}

destruir() {
  local id
  id=$(instancia)
  if [ -n "$id" ]; then
    aws ec2 terminate-instances --instance-ids $id --query "TerminatingInstances[].CurrentState.Name" --output text
    aws ec2 wait instance-terminated --instance-ids $id
  fi
  local sg
  sg=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$NOME" \
    --query "SecurityGroups[0].GroupId" --output text)
  [ "$sg" != "None" ] && aws ec2 delete-security-group --group-id "$sg"
  if aws iam get-role --role-name "$NOME" >/dev/null 2>&1; then
    aws iam remove-role-from-instance-profile --instance-profile-name "$NOME" --role-name "$NOME" || true
    aws iam delete-instance-profile --instance-profile-name "$NOME" || true
    aws iam detach-role-policy --role-name "$NOME" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
    aws iam delete-role-policy --role-name "$NOME" --policy-name s3-prefixo-cpu
    aws iam delete-role --role-name "$NOME"
  fi
  echo "destruído: instância, security group, role e instance profile"
}

case "${1:-}" in
  criar) criar ;;
  pronto) ssm "test -f /opt/acaso/pronto && echo PRONTO || echo AINDA_NAO; tail -n 3 /var/log/acaso-setup.log" ;;
  setup)  # reaplica o user-data numa instância já criada (se o boot falhou); roda em segundo plano
    ssm "echo $(base64 -w0 "$DIR/user-data.sh") | base64 -d > /opt/acaso-setup.sh
nohup bash /opt/acaso-setup.sh > /dev/null 2>&1 &
echo iniciado" ;;
  rodar) rodar "$2" ;;
  modelo) trocar_modelo "$2" ;;
  log) ssm "tail -n ${3:-5} /opt/acaso/$2/runner.log; wc -l < /opt/acaso/$2/saida.jsonl" ;;
  exec) ssm "$2" ;;
  destruir) destruir ;;
  *) sed -n '2,16p' "$0"; exit 1 ;;
esac
