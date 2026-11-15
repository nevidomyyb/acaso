"""Etapa `classificacao` do compose, com AWS, EC2 e classificador falsos (nada sai da máquina).

O ponto principal: a infraestrutura da EC2 é destruída sempre, inclusive quando a rodada falha.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ETAPA = RAIZ / "etl" / "etapa_classificacao.sh"
REAL = RAIZ / "data" / "enriched" / "temas_v2_qwen3_8b.parquet"


def executavel(caminho: Path, corpo: str) -> Path:
    caminho.write_text("#!/usr/bin/env bash\n" + corpo)
    caminho.chmod(0o755)
    return caminho


@pytest.fixture
def falsos(tmp_path):
    chamadas = tmp_path / "chamadas.txt"
    arq = tmp_path / "temas.parquet"
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    executavel(bin_ / "aws", 'echo "arn:aws:iam::000000000000:user/acaso-operador"\n')
    ec2 = executavel(tmp_path / "ec2.sh", f"""
echo "ec2 $*" >> {chamadas}
case "$1" in
  pronto) echo PRONTO ;;
  rodar) if [ -n "${{FALHAR_RODAR:-}}" ]; then exit 7; fi ;;
  log) echo "3318/3318 | 6.2 s/registro"; echo "fim: 3318 registros em 341.7 min" ;;
esac
""")
    origem = REAL if REAL.exists() else None
    cls = executavel(tmp_path / "cls.sh", f"""
echo "cls ${{@: -1}}" >> {chamadas}
if [ "${{@: -1}}" = coletar ]; then cp "{origem}" "{arq}"; fi
""")
    env = os.environ | {
        "PATH": f"{bin_}:{RAIZ / '.venv' / 'bin'}:{os.environ['PATH']}",
        "AWS_ACCESS_KEY_ID": "x", "AWS_SECRET_ACCESS_KEY": "y", "ACASO_S3_BUCKET": "z",
        "ACASO_CLS_ARQ": str(arq), "ACASO_CLS_EC2": str(ec2), "ACASO_CLS_CMD": f"bash {cls}",
        "ACASO_CLS_INTERVALO_S": "0", "ACASO_CLS_INTERVALO_BOOT_S": "0",
    }
    if origem is None:
        pytest.skip("precisa do arquivo real de classificação para simular a coleta")
    if not shutil.which("bash"):
        pytest.skip("sem bash")
    return env, chamadas, arq


def rodar(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(ETAPA)], env=env, capture_output=True, text=True, timeout=60)


def test_fluxo_completo_na_ordem_e_destroi_no_fim(falsos):
    env, chamadas, arq = falsos
    r = rodar(env)
    assert r.returncode == 0, r.stderr
    assert chamadas.read_text().split("\n")[:-1] == [
        "cls preparar", "cls enviar", "ec2 criar", "ec2 pronto", "ec2 modelo qwen3_8b",
        "ec2 rodar cpu_v2_qwen3_8b_sessao1", "ec2 log cpu_v2_qwen3_8b_sessao1 2", "cls coletar", "ec2 destruir",
    ]
    assert arq.exists() and "classificação ok" in r.stdout


def test_falha_na_rodada_ainda_destroi_a_ec2(falsos):
    env, chamadas, arq = falsos
    r = rodar(env | {"FALHAR_RODAR": "1"})
    assert r.returncode != 0
    linhas = chamadas.read_text().split("\n")[:-1]
    assert linhas[-1] == "ec2 destruir" and "cls coletar" not in linhas
    assert not arq.exists()


def test_arquivo_existente_nao_toca_na_aws(falsos):
    env, chamadas, _ = falsos
    r = rodar(env | {"ACASO_CLS_ARQ": str(REAL)})
    assert r.returncode == 0 and "classificação ok" in r.stdout
    assert not chamadas.exists()


def test_sem_arquivo_e_sem_credenciais_para_com_mensagem(falsos):
    env, chamadas, _ = falsos
    sem = {k: v for k, v in env.items() if k not in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")}
    r = rodar(sem)
    assert r.returncode == 1 and "git checkout" in r.stderr and "AWS_ACCESS_KEY_ID" in r.stderr
    assert not chamadas.exists()
