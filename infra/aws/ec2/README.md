# EC2 de classificação em CPU (ADR-011)

Classifica tema e recusa com um LLM aberto (Qwen3-8B, llama.cpp) numa EC2 só com CPU. Motivo: a conta não tem cota no Bedrock nem GPU.

## Recursos

| Recurso | Nome | Observação |
|---|---|---|
| Instância | `acaso-classificacao` | c7i.4xlarge (16 vCPU, 32 GB), Ubuntu 24.04, disco de 40 GB |
| Role + instance profile | `acaso-classificacao` | `AmazonSSMManagedInstanceCore` + leitura e gravação só em `s3://<BUCKET>/cpu/*` |
| Security group | `acaso-classificacao` | Sem regra de entrada. O acesso é só por SSM |

A instância se destrói sozinha no prazo do `shutdown` (10 h no boot), porque o `shutdown-behavior` é `terminate`. Para uma rodada longa, reprograme com `classificacao.sh exec "shutdown -h +480"`.

## Modelos

O boot sobe o Qwen3-4B. A chave de cada modelo é a mesma em `classificacao.sh` e em `etl/classificar_cpu.py`. O repositório, a revisão e o SHA-256 ficam fixados no script.

| Chave | Modelo | s/conversa (4 em paralelo) |
|---|---|---|
| `qwen3_4b` | Qwen3-4B-Instruct-2507 Q4_K_M | 4,0 |
| `qwen3_8b` | Qwen3-8B Q4_K_M, sem "thinking" (**escolhido**) | 6,5 |

## Passo a passo

O script usa o perfil padrão do AWS CLI (administrador). Ele não usa as chaves do `.env`.

1. Prepare e envie a entrada: `.venv/bin/python etl/classificar_cpu.py --versao v2 --modelo qwen3_8b [--amostra-n 40] preparar` e depois `enviar`, com os mesmos argumentos.
2. Crie a instância: `infra/aws/ec2/classificacao.sh criar`. O setup leva ~10 min. Se o boot falhar, use `classificacao.sh setup`.
3. Confira o setup: `classificacao.sh pronto`. Espere a resposta `PRONTO`.
4. Troque o modelo: `classificacao.sh modelo qwen3_8b`.
5. Inicie: `classificacao.sh rodar cpu_v2_qwen3_8b_sessao1`. Acompanhe com `classificacao.sh log cpu_v2_qwen3_8b_sessao1`.
6. Colete: `.venv/bin/python etl/classificar_cpu.py --versao v2 --modelo qwen3_8b coletar`. O resultado vai para `data/enriched/temas_v2_qwen3_8b.parquet`.
7. Destrua tudo: `classificacao.sh destruir`.

O executor é retomável e pula os registros já gravados. Se a instância cair, faça assim:
1. Crie outra instância (passos 2 a 4).
2. Copie a saída parcial do S3: `classificacao.sh exec "mkdir -p /opt/acaso/<PASTA> && aws s3 cp s3://<BUCKET>/cpu/<PASTA>/saida.jsonl /opt/acaso/<PASTA>/"`.
3. Rode o passo 5 de novo.
