# Imagem acaso-etl: serviços bruta, classificacao e carga do docker-compose.yml.
FROM python:3.13-slim

# curl + unzip: só a etapa de classificação usa, para instalar o AWS CLI quando precisa refazer na EC2
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY etl/requirements.txt etl/requirements.txt
RUN pip install --no-cache-dir -r etl/requirements.txt

COPY etl/ etl/
COPY db/ db/
COPY infra/aws/ec2/ infra/aws/ec2/

ENV PYTHONPATH=/app/etl \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
