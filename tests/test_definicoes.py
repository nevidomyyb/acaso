"""Testes de definição: cada caso tem resposta conhecida. Se uma definição mudar, um teste quebra."""

from __future__ import annotations

import math
from datetime import timedelta

import duckdb
import pytest
from definicoes import Definicoes, construir, elegiveis
from estatistica import wilson

H = lambda h: timedelta(hours=h)  # noqa: E731
D = lambda d: timedelta(days=d)  # noqa: E731
M = lambda m: timedelta(minutes=m)  # noqa: E731


def rodar(base, caminho, **kw):
    usuarios = construir(duckdb.connect(), base.gravar(caminho), Definicoes(**kw))
    return usuarios.set_index("usuario_id")


def por_ip(usuarios, base_linhas):
    """Mapeia hashed_ip -> linha de usuário (chave padrão = ip)."""
    con = duckdb.connect()
    ips = {r["hashed_ip"] for r in base_linhas}
    mapa = {ip: con.execute("SELECT md5(?)", [ip]).fetchone()[0] for ip in ips}
    return {ip: usuarios.loc[uid] for ip, uid in mapa.items() if uid in usuarios.index}


def test_retorno_basico_e_janela(base):
    b, caminho = base
    b.conversa("A", H(0))
    b.conversa("A", H(0) + M(20))  # mesma sessão (gap 15 min < 30)
    b.conversa("A", D(3))  # volta no dia 3
    b.conversa("B", H(0))
    b.conversa("B", D(8))  # volta depois de 7 dias -> não conta
    b.conversa("Z", D(30))  # fixa o fim da base
    u = por_ip(rodar(b, caminho), b.linhas)
    assert u["A"].voltou_7d and u["A"].primeira_n_conversas == 2
    assert not u["B"].voltou_7d


def test_gap_de_sessao_muda_o_retorno(base):
    b, caminho = base
    b.conversa("C", H(0), duracao_min=10)
    b.conversa("C", M(50))  # 40 min depois do fim da 1ª
    b.conversa("Z", D(30))
    assert por_ip(rodar(b, caminho, gap_sessao_min=30), b.linhas)["C"].voltou_7d
    assert not por_ip(rodar(b, caminho, gap_sessao_min=60), b.linhas)["C"].voltou_7d


def test_regras_de_retorno_diferem(base):
    b, caminho = base
    # 23h50 em São Paulo (02h50 UTC do dia seguinte); a próxima conversa é 20 min depois, em outro dia local
    b.conversa("E", H(13) + M(50))
    b.conversa("E", H(14) + M(10))
    b.conversa("Z", D(30))
    assert not por_ip(rodar(b, caminho, regra_retorno="nova_sessao"), b.linhas)["E"].voltou_7d
    assert not por_ip(rodar(b, caminho, regra_retorno="apos_1h"), b.linhas)["E"].voltou_7d
    assert por_ip(rodar(b, caminho, regra_retorno="dia_seguinte"), b.linhas)["E"].voltou_7d


def test_censura_e_aquecimento(base):
    b, caminho = base
    b.conversa("F", H(0))  # 1ª semana da base
    b.conversa("G", D(20))
    b.conversa("Z", D(25))  # fim da base: G não tem 7 dias observáveis
    u = rodar(b, caminho, aquecimento_semanas=1)
    m = por_ip(u, b.linhas)
    assert m["F"].em_aquecimento and m["F"].observavel_7d
    assert not m["G"].observavel_7d
    assert len(elegiveis(u.reset_index())) == 0  # F em aquecimento, G e Z censurados


def test_filtro_brasil_e_chave_ip_ua(base):
    b, caminho = base
    b.conversa("H", H(0), ua="Chrome-118")
    b.conversa("H", D(2), ua="Chrome-119")  # atualização do navegador
    b.conversa("X", H(0), pais="Portugal")
    b.conversa("Z", D(30))
    por_ip_ = rodar(b, caminho, chave_usuario="ip")
    assert len(por_ip_) == 2  # H e Z; X fora do Brasil
    assert por_ip(por_ip_, b.linhas)["H"].voltou_7d
    por_ip_ua = rodar(b, caminho, chave_usuario="ip_ua")
    assert len(por_ip_ua) == 3  # a mesma pessoa vira dois "novos" (mecanismo do incidente)
    assert por_ip_ua.voltou_7d.sum() == 0


def test_conversa_sem_conteudo_nao_conta_como_uso(base):
    b, caminho = base
    b.conversa("I", H(0), texto="")
    b.conversa("I", D(2))
    b.conversa("Z", D(30))
    u = por_ip(rodar(b, caminho), b.linhas)
    assert not u["I"].voltou_7d  # a 1ª experiência real é a do dia 2
    assert por_ip(rodar(b, caminho, excluir_sem_conteudo=False), b.linhas)["I"].voltou_7d


def test_definicao_invalida():
    with pytest.raises(ValueError):
        Definicoes(chave_usuario="email")


def test_wilson():
    lo, hi = wilson(30, 100)
    assert lo == pytest.approx(0.2189, abs=1e-3) and hi == pytest.approx(0.3958, abs=1e-3)
    assert all(math.isnan(x) for x in wilson(0, 0))


def test_continuar_conversa_aberta_conta_como_retorno(base):
    b, caminho = base
    b.conversa("J", H(0), duracao_min=3 * 24 * 60)  # 1ª resposta no dia 0, 2ª no dia 3 (mesma conversa)
    b.conversa("Z", D(30))
    assert por_ip(rodar(b, caminho, unidade_atividade="turno"), b.linhas)["J"].voltou_7d
    assert not por_ip(rodar(b, caminho, unidade_atividade="conversa"), b.linhas)["J"].voltou_7d


def test_falha_de_coleta_na_janela_tira_do_denominador(base, tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from conftest import T0

    b, caminho = base
    b.conversa("K", H(0))  # janela de 7 dias cobre o dia T0 + 2 (sem coleta)
    b.conversa("L", D(15))  # janela limpa
    b.conversa("Z", D(30))
    dias = [(T0 + D(i)).date() for i in range(31) if i != 2]
    volume = tmp_path / "volume.parquet"
    pq.write_table(pa.table({"dia_utc": dias, "conversas": [1000] * len(dias)}), volume)
    d = Definicoes()
    u = construir(duckdb.connect(), b.gravar(caminho), d, volume_diario=str(volume))
    m = por_ip(u.set_index("usuario_id"), b.linhas)
    assert m["K"].janela_com_lacuna and not m["L"].janela_com_lacuna
    ids = set(elegiveis(u, d).usuario_id)
    assert m["K"].name not in ids and m["L"].name in ids


def test_grupo_tema_cobre_os_11_temas_em_7_grupos():
    # BDR-009: todo tema do prompt tem grupo; nenhum grupo inventado.
    from classificacao import TEMAS
    from definicoes import GRUPO_TEMA, RECUSA_FATOR

    assert set(GRUPO_TEMA) == set(TEMAS)
    assert len(set(GRUPO_TEMA.values())) == 7
    assert RECUSA_FATOR == ("total",)  # BDR-010: parcial fica fora (os dois detectores perdem 7 de 11)
