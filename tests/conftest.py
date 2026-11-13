"""Gera uma base bruta sintética com o mesmo schema (parcial) da WildChat-1M."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "etl"))

T0 = datetime(2023, 11, 6, 13, 0, tzinfo=UTC)  # segunda-feira, 10h em São Paulo

TURNO = pa.struct(
    [
        ("content", pa.string()),
        ("country", pa.string()),
        ("role", pa.string()),
        ("timestamp", pa.timestamp("us", tz="UTC")),
        ("turn_identifier", pa.int64()),
    ]
)
SCHEMA = pa.schema(
    [
        ("conversation_hash", pa.string()),
        ("model", pa.string()),
        ("timestamp", pa.timestamp("us", tz="UTC")),
        ("conversation", pa.list_(TURNO)),
        ("turn", pa.int64()),
        ("language", pa.string()),
        ("toxic", pa.bool_()),
        ("redacted", pa.bool_()),
        ("state", pa.string()),
        ("country", pa.string()),
        ("hashed_ip", pa.string()),
        ("header", pa.struct([("accept-language", pa.string()), ("user-agent", pa.string())])),
    ]
)


class BaseSintetica:
    def __init__(self) -> None:
        self.linhas: list[dict] = []
        self._id = 1000

    def conversa(
        self,
        ip: str,
        inicio: timedelta,
        duracao_min: float = 5,
        ua: str = "UA-1",
        pais: str = "Brazil",
        texto: str = "oi",
        lang: str = "pt-BR",
        modelo: str = "gpt-3.5-turbo-0613",
        idioma: str = "Portuguese",
        estado: str | None = "São Paulo",
        redacted: bool = False,
        resposta: str = "resp",
    ) -> None:
        """Conversa de 2 turnos: o 1º horário é `T0 + inicio`, o último `+ duracao_min`."""
        t1 = T0 + inicio
        t2 = t1 + timedelta(minutes=duracao_min)
        ids = [self._id, self._id + 1, self._id + 2, self._id + 3]
        self._id += 4
        turnos = [
            {"content": texto, "country": pais, "role": "user", "timestamp": None, "turn_identifier": ids[0]},
            {"content": resposta, "country": None, "role": "assistant", "timestamp": t1, "turn_identifier": ids[1]},
            {"content": texto, "country": pais, "role": "user", "timestamp": None, "turn_identifier": ids[2]},
            {"content": resposta, "country": None, "role": "assistant", "timestamp": t2, "turn_identifier": ids[3]},
        ]
        self.linhas.append(
            {
                "conversation_hash": "h",
                "model": modelo,
                "timestamp": t2,
                "conversation": turnos,
                "turn": 2,
                "language": idioma,
                "toxic": False,
                "redacted": redacted,
                "state": estado,
                "country": pais,
                "hashed_ip": ip,
                "header": {"accept-language": lang, "user-agent": ua},
            }
        )

    def gravar(self, caminho: Path) -> str:
        pq.write_table(pa.Table.from_pylist(self.linhas, schema=SCHEMA), caminho)
        return str(caminho)


@pytest.fixture
def base(tmp_path: Path) -> tuple[BaseSintetica, Path]:
    return BaseSintetica(), tmp_path / "bruta.parquet"
