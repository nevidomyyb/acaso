"""Fatores da 1ª experiência: conteúdo da 1ª conversa, volume da 1ª sessão, k-anonimato do estado."""

from __future__ import annotations

from datetime import timedelta

import duckdb
import pandas as pd
from definicoes import PADRAO, construir, elegiveis
from primeira_experiencia import criar_primeira_experiencia

M = lambda m: timedelta(minutes=m)  # noqa: E731
D = lambda d: timedelta(days=d)  # noqa: E731
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"


def montar(base, tmp_path, temas: dict[int, tuple[str, str]], k: int = 20):
    """`temas`: índice da conversa em b.linhas -> (tema, recusa)."""
    b, caminho = base
    linhas = [
        {"conversa_id": str(b.linhas[i]["conversation"][0]["turn_identifier"]), "tema": t, "recusa": r,
         "recusa_regex": r == "total"}
        for i, (t, r) in temas.items()
    ]
    arq = tmp_path / "temas.parquet"
    pd.DataFrame(linhas).to_parquet(arq, index=False)
    con = duckdb.connect()
    usuarios = construir(con, b.gravar(caminho), PADRAO)
    pe = criar_primeira_experiencia(con, str(arq), k=k)
    return usuarios, pe.set_index("usuario_id")


def test_conteudo_da_primeira_conversa_e_volume_da_sessao(base, tmp_path):
    b, _ = base
    b.conversa("A", M(0), modelo="gpt-4-1106-preview", idioma="English", ua=IPHONE)  # 1ª conversa
    b.conversa("A", M(10))  # mesma sessão: conta no volume, não no conteúdo
    b.conversa("A", D(2))  # retorno
    b.conversa("Z", D(30))  # alonga a base: A fica observável por 7 dias
    _, pe = montar(base, tmp_path, {0: ("estudo_escola", "nao"), 1: ("conteudo_adulto", "total"), 2: ("outro", "nao")})
    a = pe.iloc[0]
    assert a.familia_modelo == "gpt-4" and a.idioma_3 == "ingles" and a.dispositivo == "mobile"
    assert a.tema == "estudo_escola" and a.tema_grupo == "tarefa_conhecimento"
    assert not a.recusa_total and a.recusa_total_sessao  # BDR-010: só a 1ª conversa
    assert a.n_conversas_sessao1 == 2 and a.n_respostas_sessao1 == 4 and a.duracao_sessao1_min == 15
    assert a.voltou_7d and a.elegivel


def test_horario_local_de_sao_paulo(base, tmp_path):
    b, _ = base
    b.conversa("A", M(0))  # T0 = segunda 13h UTC = 10h em São Paulo
    b.conversa("B", D(5) + timedelta(hours=11))  # domingo 00h UTC = sábado 21h em São Paulo
    _, pe = montar(base, tmp_path, {0: ("saudacao_teste", "nao"), 1: ("saudacao_teste", "nao")})
    a, s = pe.iloc[0], pe.iloc[1]
    assert (a.hora_local, a.faixa_horaria, a.dia_semana, a.fim_de_semana) == (10, "manha", 1, False)
    assert (s.hora_local, s.faixa_horaria, s.dia_semana, s.fim_de_semana) == (21, "noite", 6, True)  # dia local


def test_estado_com_poucos_usuarios_elegiveis_vira_outros(base, tmp_path):
    b, _ = base
    b.conversa("B", M(0))  # São Paulo
    b.conversa("C", M(60))  # São Paulo
    b.conversa("D", M(120), estado="Acre")  # 1 usuário só
    b.conversa("E", M(180), estado=None)
    b.conversa("Z", D(30))  # São Paulo, mas não observável: não conta para o k
    temas = {i: ("outro", "nao") for i in range(5)}
    _, pe = montar(base, tmp_path, temas, k=2)
    assert list(pe.estado_grupo) == ["São Paulo", "São Paulo", "outros", "outros", "São Paulo"]


def test_elegivel_e_o_mesmo_denominador_das_definicoes(base, tmp_path):
    b, _ = base
    for i, ip in enumerate("ABCD"):
        b.conversa(ip, D(i * 3))
    b.conversa("A", D(1))
    usuarios, pe = montar(base, tmp_path, {i: ("outro", "nao") for i in range(5)})
    assert set(pe.index[pe.elegivel]) == set(elegiveis(usuarios).usuario_id)
