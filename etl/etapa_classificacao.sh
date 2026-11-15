#!/usr/bin/env bash
# Etapa "classificacao" do docker compose (ADR-004).
#
#   - Arquivo em data/enriched/ existe  -> confere e sai (sem AWS). É o caso normal: o arquivo está no git.
#   - Arquivo ausente + credenciais     -> refaz na EC2: prepara, cria a infra, classifica, coleta e DESTRÓI.
#                                          ~6 h e ~US$ 5. A destruição roda sempre (trap), inclusive em erro.
#   - Arquivo ausente, sem credenciais  -> para com mensagem clara; a carga não sobe.
#
# Credenciais: usuário acaso-operador (infra/aws/iam/README.md), pelo .env.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSAO=${ACASO_CLS_VERSAO:-v2}
MODELO=${ACASO_CLS_MODELO:-qwen3_8b}
ARQ=${ACASO_CLS_ARQ:-data/enriched/temas_${VERSAO}_${MODELO}.parquet}
PASTA=cpu_${VERSAO}_${MODELO}_sessao1
# Comandos externos (substituíveis: tests/test_etapa_classificacao.py roda o fluxo com versões falsas)
EC2=${ACASO_CLS_EC2:-infra/aws/ec2/classificacao.sh}
CLS=${ACASO_CLS_CMD:-python etl/classificar_cpu.py}
ESPERA_BOOT_MIN=${ACASO_CLS_ESPERA_BOOT_MIN:-45}     # compilar o llama.cpp + baixar o modelo
ESPERA_RODADA_MIN=${ACASO_CLS_ESPERA_RODADA_MIN:-540} # 3.318 conversas a ~6,2 s = ~5,7 h; trava de 9 h
INTERVALO_S=${ACASO_CLS_INTERVALO_S:-300}

log() { echo "[classificacao $(date -u +%H:%M:%S)] $*"; }

if [ -f "$ARQ" ]; then
  python etl/conferir_classificacao.py "$ARQ"
  exit 0
fi

log "arquivo ausente: $ARQ"
faltam=""
for v in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY ACASO_S3_BUCKET; do
  [ -n "${!v:-}" ] || faltam="$faltam $v"
done
if [ -n "$faltam" ]; then
  cat >&2 <<EOF
ERRO: falta a classificação de tema e recusa ($ARQ) e não há credenciais AWS para refazê-la.
  Opção 1 (normal): restaure o arquivo do git:  git checkout -- $ARQ
  Opção 2: preencha no .env:$faltam  (usuário acaso-operador, veja infra/aws/iam/README.md)
           e rode de novo. A EC2 leva ~6 h e custa ~US\$ 5.
EOF
  exit 1
fi
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

if ! command -v aws >/dev/null; then
  log "instalando o AWS CLI v2"
  tmp=$(mktemp -d)
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "$tmp/awscli.zip"
  unzip -q "$tmp/awscli.zip" -d "$tmp" && "$tmp/aws/install" >/dev/null && rm -rf "$tmp"
fi
log "identidade: $(aws sts get-caller-identity --query Arn --output text)"

$CLS --versao "$VERSAO" --modelo "$MODELO" preparar
$CLS --versao "$VERSAO" --modelo "$MODELO" enviar

destruir() {
  log "destruindo a infraestrutura da EC2"
  bash "$EC2" destruir || log "ATENÇÃO: a destruição falhou. Rode 'bash $EC2 destruir' e confira a conta."
}
trap destruir EXIT

bash "$EC2" criar

log "aguardando o boot (até $ESPERA_BOOT_MIN min)"
fim=$(( $(date +%s) + ESPERA_BOOT_MIN * 60 ))
until bash "$EC2" pronto 2>/dev/null | grep -q PRONTO; do
  [ "$(date +%s)" -lt "$fim" ] || { log "boot não terminou a tempo"; exit 1; }
  sleep "${ACASO_CLS_INTERVALO_BOOT_S:-60}"
done

log "trocando o modelo para $MODELO"
bash "$EC2" modelo "$MODELO"
bash "$EC2" rodar "$PASTA"

log "classificando (até $ESPERA_RODADA_MIN min; progresso a cada $((INTERVALO_S / 60)) min)"
fim=$(( $(date +%s) + ESPERA_RODADA_MIN * 60 ))
while :; do
  saida=$(bash "$EC2" log "$PASTA" 2 2>/dev/null || true)
  echo "$saida" | tail -n 2
  echo "$saida" | grep -q '^fim:' && break
  [ "$(date +%s)" -lt "$fim" ] || { log "a rodada passou do limite"; exit 1; }
  sleep "$INTERVALO_S"
done

$CLS --versao "$VERSAO" --modelo "$MODELO" coletar
python etl/conferir_classificacao.py "$ARQ"
log "classificação refeita: $ARQ (lembre de commitar o arquivo novo)"
