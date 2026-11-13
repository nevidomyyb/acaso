"""Classificação em CPU (ADR-004): seleção da 1ª sessão, prompt, schema e leitura da saída do llama-server."""

from __future__ import annotations

import json
from datetime import timedelta

import duckdb
from classificacao import SCHEMA, TEMAS, ler_sistema
from classificar_cpu import (
    MODELOS,
    corpo_cpu,
    ids_primeira_sessao,
    interpretar_cpu,
    montar,
)

M = lambda m: timedelta(minutes=m)  # noqa: E731
D = lambda d: timedelta(days=d)  # noqa: E731


def test_seleciona_so_conversas_da_primeira_sessao(base):
    b, caminho = base
    b.conversa("A", M(0))  # 1ª sessão de A
    b.conversa("A", M(20))  # mesma sessão (gap < 30 min)
    b.conversa("A", D(2))  # retorno: 2ª sessão, fica fora
    b.conversa("B", D(1))  # 1ª sessão de B
    b.conversa("C", D(1), texto="")  # sem conteúdo (BDR-008): não é uso, fica fora
    ids = ids_primeira_sessao(duckdb.connect(), b.gravar(caminho), None)
    primeiros = [str(linha["conversation"][0]["turn_identifier"]) for linha in b.linhas]
    assert ids == {primeiros[0], primeiros[1], primeiros[3]}


def test_prompt_pede_json_e_traz_a_taxonomia_inteira():
    s = ler_sistema("v2")
    assert "objeto JSON" in s  # o llama-server não tem chamada de ferramenta
    assert all(t in s for t in TEMAS) and all(f"`{r}`" in s for r in ("nao", "parcial", "total"))


def test_corpo_forca_schema_e_limita_motivo():
    corpo = corpo_cpu({"msg_usuario": "oi", "msg_assistente": "olá"}, "sistema")
    schema = corpo["response_format"]["json_schema"]["schema"]
    assert schema == SCHEMA and schema["properties"]["motivo"]["maxLength"] > 0
    assert corpo["temperature"] == 0 and corpo["messages"][0]["role"] == "system"


def test_corpo_do_qwen3_8b_desliga_o_thinking():
    extra = MODELOS["qwen3_8b"]["extra"]
    corpo = corpo_cpu({"msg_usuario": "oi", "msg_assistente": "olá"}, "sistema", extra)
    assert corpo["chat_template_kwargs"] == {"enable_thinking": False} and "response_format" in corpo


def test_interpreta_saida_valida_invalida_e_erro():
    uso = {"prompt_tokens": 900, "completion_tokens": 40}
    ok = {"motivo": "pede código", "tema": "programacao_tecnologia", "recusa": "nao", "confianca": 0.9}
    r = interpretar_cpu({"conteudo": json.dumps(ok), "uso": uso})
    assert r["tema"] == "programacao_tecnologia" and r["input_tokens"] == 900 and "erro" not in r
    assert "erro" in interpretar_cpu({"conteudo": '{"tema": "inventado"}', "uso": uso})
    assert "erro" in interpretar_cpu({"conteudo": "{corta", "uso": uso, "fim": "length"})
    assert interpretar_cpu({"erro": "URLError: timeout"})["erro"].startswith("URLError")


def test_montar_aplica_regra_do_vazio_e_marca_ausentes():
    sel = [
        {"conversa_id": "1", "msg_usuario": "  ", "msg_assistente": "Olá!"},
        {"conversa_id": "2", "msg_usuario": "traduza", "msg_assistente": "Claro"},
        {"conversa_id": "3", "msg_usuario": "oi", "msg_assistente": "Olá"},
    ]
    ok = {"motivo": "tradução", "tema": "traducao_reescrita", "recusa": "nao", "confianca": 0.8}
    rotulo = MODELOS["qwen3_4b"]["rotulo"]
    df = montar(sel, {"2": {"recordId": "2", "conteudo": json.dumps(ok), "uso": {}, "segundos": 3.1}}, "v1", rotulo)
    assert list(df.fonte) == ["regra_vazio", "llm", "llm"]
    assert df.loc[1, "modelo"] == rotulo and df.loc[1, "segundos"] == 3.1
    assert df.loc[2, "erro"] == "ausente na saída"


def test_jsonl_com_separador_unicode_nao_quebra_a_linha(tmp_path):
    # U+2028 aparece no texto de conversas reais; str.splitlines() cortaria o JSON ao meio.
    from llm_runner import ler_jsonl

    regs = [{"recordId": "1", "body": {"t": "linha\u2028outra\u2029fim"}}, {"recordId": "2", "body": {}}]
    arq = tmp_path / "entrada.jsonl"
    # Grava o caractere cru (como ensure_ascii=False fazia): é o caso que quebrava.
    arq.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in regs))
    assert len(arq.read_text().splitlines()) > len(regs)  # o defeito original existe neste arquivo
    assert ler_jsonl(arq) == regs
