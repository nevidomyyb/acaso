#!/bin/bash
# Boot da EC2 de classificação (ADR-011): compila o llama.cpp, baixa o modelo com SHA-256 e sobe o llama-server.
set -euxo pipefail
exec > /var/log/acaso-setup.log 2>&1

# Trava de custo: em 10 h a máquina desliga e, pelo shutdown-behavior=terminate, é destruída.
shutdown -h +600 "acaso: limite de 10 h"

LLAMA_TAG=v0.9.0
REPO=unsloth/Qwen3-4B-Instruct-2507-GGUF
REV=a06e946bb6b655725eafa393f4a9745d460374c9
ARQ=Qwen3-4B-Instruct-2507-Q4_K_M.gguf
SHA=3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y build-essential cmake git libcurl4-openssl-dev python3 curl unzip
# AWS CLI v2 pelo instalador oficial. A snap store não respondeu no boot em 12/11.
curl -fsSL -o /tmp/awscliv2.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip
unzip -qo /tmp/awscliv2.zip -d /tmp && /tmp/aws/install --update

[ -d /opt/llama.cpp ] || git clone --depth 1 --branch "$LLAMA_TAG" https://github.com/ggml-org/llama.cpp /opt/llama.cpp
cmake -S /opt/llama.cpp -B /opt/llama.cpp/build -DGGML_NATIVE=ON -DCMAKE_BUILD_TYPE=Release
cmake --build /opt/llama.cpp/build --target llama-server -j "$(nproc)"

mkdir -p /opt/modelos /opt/acaso
curl -fsSL -o "/opt/modelos/$ARQ" "https://huggingface.co/$REPO/resolve/$REV/$ARQ"
echo "$SHA  /opt/modelos/$ARQ" | sha256sum -c -

# Threads = núcleos físicos (a c7i tem 2 vCPU por núcleo). 4 slots paralelos de 4.096 tokens.
NUCLEOS=$(( $(nproc) / 2 ))
cat > /etc/systemd/system/llama.service <<EOF
[Unit]
Description=llama-server (acaso)
After=network.target

[Service]
ExecStart=/opt/llama.cpp/build/bin/llama-server -m /opt/modelos/$ARQ --host 127.0.0.1 --port 8080 \
  -t $NUCLEOS -tb $NUCLEOS -c 16384 -np 4 --jinja
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now llama

for _ in $(seq 1 120); do
  curl -sf http://127.0.0.1:8080/health && break
  sleep 5
done
touch /opt/acaso/pronto
