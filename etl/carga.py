"""Carga da base analítica (Postgres) a partir da base bruta. Roda no `docker compose up` e termina.

Passos:
  1. aplica as migrations do Alembic (db/migrations);
  2. registra a execução em `meta_carga` (status 'iniciada'), com o SHA-256 da bruta e da classificação;
  3. constrói a 1ª experiência no DuckDB (etl/definicoes.py + etl/primeira_experiencia.py);
  4. ajusta a regressão (etl/efeitos.py) e monta `resultado_efeitos`;
  5. numa única transação: TRUNCATE + COPY das duas tabelas e `meta_carga` = 'ok'.

Idempotente: cada execução substitui o conteúdo inteiro (a base tem 22 MB), e `meta_carga` guarda o histórico.
Se algo falha, a transação desfaz tudo, a tela continua com a carga anterior e `meta_carga` registra o erro.

Nunca grava texto das conversas, `motivo` do LLM, hashed_ip, user-agent nem a chave md5 da análise (regra 6).

Uso:
    ACASO_DB_URL=postgresql://acaso:acaso_local@localhost:5433/acaso .venv/bin/python etl/carga.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from definicoes import PADRAO, VERSAO_DEFINICOES  # noqa: E402
from efeitos import FATORES, ROTULOS, ajustar, preparar, tabela_efeitos  # noqa: E402
from primeira_experiencia import BRUTA, TEMAS, VOLUME, construir_primeira_experiencia  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PAIS = "Brazil"  # BDR-007
METODO = "regressao_linear_hc1"

# Colunas da `primeira_experiencia` (DuckDB) que vão para o Postgres. Fora: usuario_id (md5 do IP) e estado
# bruto (só o agrupado, com k = 20).
COLUNAS_PE = [
    "primeira_inicio_utc", "coorte_semana", "coorte_mes", "elegivel", "voltou_7d",
    "n_conversas_sessao1", "n_respostas_sessao1", "duracao_sessao1_min",
    "modelo", "familia_modelo", "idioma_3", "dispositivo", "estado_grupo", "redacted",
    "turnos_conversa_1", "tam_msg_usuario_1", "tam_resposta_1",
    "hora_local", "faixa_horaria", "dia_semana", "fim_de_semana",
    "tema", "tema_grupo", "recusa", "recusa_total", "recusa_regex", "recusa_total_sessao",
]
COLUNAS_EFEITOS = [
    "pais", "ordem", "fator", "rotulo_fator", "nivel", "rotulo_nivel", "referencia", "rotulo_referencia", "n",
    "bruto_pp", "bruto_ic_inf", "bruto_ic_sup", "ajustado_pp", "ajustado_ic_inf", "ajustado_ic_sup",
    "metodo", "n_modelo", "definicao_versao",
]


def log(evento: str, **campos: object) -> None:
    """Log estruturado (uma linha JSON por evento): vai para o CloudWatch em produção."""
    print(json.dumps({"ts": datetime.now(UTC).isoformat(timespec="seconds"), "etapa": "carga", "evento": evento}
                     | campos, ensure_ascii=False, default=str), flush=True)


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        while bloco := f.read(1 << 20):
            h.update(bloco)
    return h.hexdigest()


def aplicar_migrations(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    os.environ["ACASO_DB_URL"] = url
    command.upgrade(Config(str(RAIZ / "db" / "alembic.ini")), "head")


def nivel_texto(v: object) -> str:
    """Nível como texto estável na base: booleano vira 'sim'/'nao' (igual a vw_novato_dimensao)."""
    if isinstance(v, bool):
        return "sim" if v else "nao"
    return str(v)


def rotulo(v: object) -> str:
    return ROTULOS.get(v, str(v))


def montar_primeira_experiencia(pe: pd.DataFrame, df: pd.DataFrame, carga_id: int, fuso: str) -> pd.DataFrame:
    """Tabela final: chave substituta, dia local, quartil da 1ª resposta (só elegíveis) e as colunas permitidas."""
    out = pe[COLUNAS_PE].copy()
    out.insert(0, "usuario_sk", range(1, len(out) + 1))  # pe já vem ordenada por início e chave
    out.insert(1, "carga_id", carga_id)
    out.insert(2, "pais", PAIS)
    inicio = pd.to_datetime(out.primeira_inicio_utc, utc=True)
    out.insert(4, "primeira_dia_local", inicio.dt.tz_convert(fuso).dt.date)
    out["resposta_quartil"] = df.resposta_quartil.astype(str).reindex(out.index)  # fora dos elegíveis = nulo
    return out


def montar_efeitos(tab: pd.DataFrame, n_modelo: int) -> pd.DataFrame:
    ordem = {f: i for i, f in enumerate(FATORES)}
    out = pd.DataFrame({
        "pais": PAIS,
        "ordem": tab.fator.map(ordem),
        "fator": tab.fator,
        "rotulo_fator": tab.rotulo,
        "nivel": tab.nivel.map(nivel_texto),
        "rotulo_nivel": tab.nivel.map(rotulo),
        "referencia": tab.referencia.map(nivel_texto),
        "rotulo_referencia": tab.referencia.map(rotulo),
        "n": tab.n,
        "bruto_pp": tab.bruto_pp, "bruto_ic_inf": tab.bruto_ic_inf, "bruto_ic_sup": tab.bruto_ic_sup,
        "ajustado_pp": tab.ajustado_pp, "ajustado_ic_inf": tab.ic_inf, "ajustado_ic_sup": tab.ic_sup,
        "metodo": METODO,
        "n_modelo": n_modelo,
        "definicao_versao": VERSAO_DEFINICOES,
    })
    return out[COLUNAS_EFEITOS]


def linhas(df: pd.DataFrame):
    """Linhas com tipos nativos do Python e None no lugar de NaN/NaT (o COPY do psycopg exige)."""
    colunas = [[None if pd.isna(v) else v for v in df[c].tolist()] for c in df.columns]
    return zip(*colunas, strict=True)


def copiar(cur: psycopg.Cursor, tabela: str, df: pd.DataFrame) -> None:
    with cur.copy(f"COPY {tabela} ({', '.join(df.columns)}) FROM STDIN") as cp:
        for linha in linhas(df):
            cp.write_row(linha)


def rejeitadas(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Quantas conversas e usuários ficaram fora do denominador, por motivo (BDR-006 e BDR-008)."""
    r = con.execute("""
        SELECT
            (SELECT count(*) FILTER (WHERE sem_conteudo) FROM conversas)                     AS conversas_sem_conteudo,
            (SELECT count(*) FILTER (WHERE NOT observavel_7d) FROM usuarios)                 AS usuarios_censurados,
            (SELECT count(*) FILTER (WHERE observavel_7d AND janela_com_lacuna) FROM usuarios)
                                                                                             AS usuarios_falha_coleta
    """).df().iloc[0]
    return {k: int(v) for k, v in r.items()}


def executar(url: str, bruta: Path = BRUTA, temas: Path = TEMAS, volume: Path | None = VOLUME,
             memoria: str = "1GB") -> int:
    t0 = time.time()
    aplicar_migrations(url)
    log("migrations aplicadas")
    temas_df = pd.read_parquet(temas, columns=["versao_prompt", "modelo"])
    versao_cls = "/".join(sorted({f"{v}:{m}" for v, m in temas_df.dropna().itertuples(index=False)}))
    meta = {
        "definicao_versao": VERSAO_DEFINICOES, "pais": PAIS,
        "bruta_arquivo": bruta.name, "bruta_sha256": sha256(bruta),
        "bruta_revisao": _revisao(bruta),
        "classificacao_arquivo": temas.name, "classificacao_sha256": sha256(temas),
        "classificacao_versao": versao_cls,
    }
    with psycopg.connect(url, autocommit=True) as c:
        carga_id = c.execute(
            f"INSERT INTO meta_carga (status, {', '.join(meta)}) VALUES ('iniciada', {', '.join(['%s'] * len(meta))})"
            " RETURNING carga_id", list(meta.values())).fetchone()[0]
    log("iniciada", carga_id=carga_id, **meta)

    try:
        con = duckdb.connect()
        con.execute(f"SET memory_limit = '{memoria}'; SET TimeZone = 'UTC'")
        pe = construir_primeira_experiencia(con, str(bruta), str(temas),
                                            volume_diario=str(volume) if volume and volume.exists() else None)
        df = preparar(pe)
        res = ajustar(df)
        tab_pe = montar_primeira_experiencia(pe, df, carga_id, PADRAO.fuso)
        tab_ef = montar_efeitos(tabela_efeitos(df, res), int(res.nobs))
        conversas_lidas, dados_de, dados_ate = con.execute(f"""
            SELECT count(*), min(timezone('{PADRAO.fuso}', inicio_utc))::DATE,
                   max(timezone('{PADRAO.fuso}', fim_utc))::DATE
            FROM conversas""").fetchone()
        rej = rejeitadas(con)
        log("calculada", usuarios=len(tab_pe), elegiveis=int(tab_pe.elegivel.sum()),
            retorno_7d=round(float(df.y.mean()), 4), efeitos=len(tab_ef), rejeitadas=rej)

        with psycopg.connect(url) as c, c.cursor() as cur:  # uma transação: tudo ou nada
            cur.execute("TRUNCATE primeira_experiencia, resultado_efeitos")
            copiar(cur, "primeira_experiencia", tab_pe)
            copiar(cur, "resultado_efeitos", tab_ef.assign(carga_id=carga_id))
            cur.execute("""
                UPDATE meta_carga SET status = 'ok', fim_utc = now(), duracao_s = %s, conversas_lidas = %s,
                       usuarios_gravados = %s, elegiveis = %s, efeitos_gravados = %s, rejeitadas = %s,
                       dados_de = %s, dados_ate = %s
                WHERE carga_id = %s""",
                (round(time.time() - t0, 1), conversas_lidas, len(tab_pe), int(tab_pe.elegivel.sum()),
                 len(tab_ef), json.dumps(rej), dados_de, dados_ate, carga_id))
    except Exception as e:
        with psycopg.connect(url, autocommit=True) as c:
            c.execute("UPDATE meta_carga SET status = 'erro', fim_utc = now(), erro = %s WHERE carga_id = %s",
                      (f"{type(e).__name__}: {e}"[:2000], carga_id))
        log("erro", carga_id=carga_id, erro=f"{type(e).__name__}: {e}")
        raise
    log("ok", carga_id=carga_id, duracao_s=round(time.time() - t0, 1))
    return carga_id


def _revisao(bruta: Path) -> str | None:
    """Revisão do WildChat-1M de onde o recorte saiu (manifesto do recorte), para a rastreabilidade."""
    man = bruta.with_suffix(".manifest.json")
    if not man.exists():
        return None
    return (json.loads(man.read_text()).get("fonte") or {}).get("revision")


def main() -> int:
    url = os.environ.get("ACASO_DB_URL")
    if not url:
        print("defina ACASO_DB_URL (ex.: postgresql://acaso:acaso_local@localhost:5433/acaso)", file=sys.stderr)
        return 2
    executar(url, memoria=os.environ.get("ACASO_DUCKDB_MEMORIA", "1GB"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
