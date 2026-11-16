"""Testes de regressão do incidente da §4.2 (docs/INCIDENTE.md).

Cada teste monta um caso com resposta conhecida e mostra o defeito no código de referência e a correção.
O último bloco protege o NOSSO produto: a chave do usuário não pode voltar a depender do user-agent.
"""

from __future__ import annotations

from datetime import timedelta

import duckdb
import pandas as pd
import pytest
from conftest import BaseSintetica
from definicoes import CHAVES_USUARIO, PADRAO, construir
from incidente import TABELA, carregar, coortes, criar_tabela

H = lambda h: timedelta(hours=h)  # noqa: E731
D = lambda d: timedelta(days=d)  # noqa: E731
JANELA = ("2023-10-30", "2023-12-31")


def endpoint(bruta: str, corrigida: bool) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")  # o servidor do cliente roda em UTC
    criar_tabela(con, corrigida)
    carregar(con, bruta, corrigida)
    return coortes(con, *JANELA, corrigida)


def totais(df: pd.DataFrame) -> tuple[int, int]:
    return int(df.novos.sum()), int(df.voltaram_7d.sum())


@pytest.mark.parametrize("corrigida, esperado", [(False, (2, 0)), (True, (1, 1))])
def test_troca_de_user_agent_nao_cria_usuario_novo(base, corrigida, esperado):
    """A mesma pessoa (mesmo IP) volta 2 dias depois com o navegador atualizado."""
    b, caminho = base
    b.conversa("A", H(0), ua="Chrome/119")
    b.conversa("A", D(2), ua="Chrome/120")
    assert totais(endpoint(b.gravar(caminho), corrigida)) == esperado


@pytest.mark.parametrize("corrigida, esperado", [(False, (3, 0)), (True, (1, 1))])
def test_user_agent_por_conversa_gera_a_assinatura_do_incidente(base, corrigida, esperado):
    """O mecanismo que reproduz o incidente: cada conversa com um user-agent único vira um 'novo' que nunca volta."""
    b, caminho = base
    for dia in range(3):
        b.conversa("A", D(dia), ua=f"App/2.0 sessao/{dia}")
    assert totais(endpoint(b.gravar(caminho), corrigida)) == esperado


@pytest.mark.parametrize("corrigida, semana", [(False, "2023-11-20"), (True, "2023-11-13")])
def test_semana_pelo_primeiro_turno_e_no_fuso_de_sao_paulo(base, corrigida, semana):
    """Começa domingo 19/11 às 19h em São Paulo (22h UTC) e termina segunda 01h UTC.

    A referência usa o último turno, em UTC: cai na semana de 20/11. O certo é o 1º turno em São Paulo: 13/11.
    """
    b, caminho = base
    b.conversa("A", D(13) + H(9), duracao_min=180)  # T0 = segunda 06/11 13h UTC
    df = endpoint(b.gravar(caminho), corrigida)
    assert df.semana.dt.strftime("%Y-%m-%d").tolist() == [semana]


@pytest.mark.parametrize("corrigida, voltaram", [(False, 1), (True, 0)])
def test_retorno_de_outro_pais_nao_conta(base, corrigida, voltaram):
    """O EXISTS do retorno sem filtro de país conta uma conversa de Portugal como retorno ao produto no Brasil."""
    b, caminho = base
    b.conversa("A", H(0))
    b.conversa("A", D(2), pais="Portugal")
    assert totais(endpoint(b.gravar(caminho), corrigida)) == (1, voltaram)


@pytest.mark.parametrize("corrigida, horas", [(False, 0.2), (True, 30.0)])
def test_conversa_que_continua_no_dia_seguinte_atualiza_o_ultimo_turno(tmp_path, corrigida, horas):
    """Carga diária: no dia 1 a conversa tem 12 min; no dia 2 ela continua até 30 h depois do início.

    `ON CONFLICT DO NOTHING` ignora a 2ª chegada e o último turno fica com o valor do dia 1.
    """
    dia1, dia2 = BaseSintetica(), BaseSintetica()  # mesmos identificadores: é a mesma conversa
    dia1.conversa("A", H(0), duracao_min=12)
    dia2.conversa("A", H(0), duracao_min=30 * 60)
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    criar_tabela(con, corrigida)
    carregar(con, dia1.gravar(tmp_path / "dia1.parquet"), corrigida)
    carregar(con, dia2.gravar(tmp_path / "dia2.parquet"), corrigida)
    duracao = con.execute(f"""
        SELECT date_diff('second', min(list_min(list_transform(conversation, lambda t: t.timestamp))), max(u)) / 3600
        FROM (SELECT ultimo_turno AS u FROM {TABELA}), read_parquet('{tmp_path / "dia1.parquet"}')
    """).fetchone()[0]
    assert duracao == pytest.approx(horas, abs=0.01)


# ---------- o nosso produto (BDR-001) ----------
def test_chave_padrao_do_produto_e_o_ip_sem_user_agent():
    """Se alguém trocar a chave padrão para IP + user-agent, este teste quebra (é o incidente)."""
    assert PADRAO.chave_usuario == "ip"
    assert CHAVES_USUARIO[PADRAO.chave_usuario] == "hashed_ip"


def test_nossa_carga_conta_uma_pessoa_com_user_agent_variando(base):
    b, caminho = base
    b.conversa("A", H(0), ua="Chrome/119")
    for dia in (2, 3, 4):
        b.conversa("A", D(dia), ua=f"App/2.0 sessao/{dia}")
    b.conversa("Z", D(30))  # fixa o fim da base: a janela de 7 dias de A fica observável
    usuarios = construir(duckdb.connect(), b.gravar(caminho), PADRAO)
    a = usuarios[usuarios.usuario_id == duckdb.connect().execute("SELECT md5('A')").fetchone()[0]]
    assert len(a) == 1 and bool(a.voltou_7d.iloc[0])
