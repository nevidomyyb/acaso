"""Contratos de entrada e saída (marshmallow). O smorest valida a entrada e gera o OpenAPI a partir deles."""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

# Igual às dimensões de vw_novato_dimensao (db/migrations/versions/0002_indicadores.py); teste confere.
DIMENSOES = ("geral", "tema_grupo", "tema", "familia_modelo", "dispositivo", "idioma_3", "faixa_horaria",
             "resposta_quartil", "recusa_total", "estado_grupo")
GRANULARIDADES = ("mes", "semana", "periodo")


class MetaSchema(Schema):
    request_id = fields.String(metadata={"description": "Identificador da requisição (também no header X-Request-ID)"})
    definicao_versao = fields.String(metadata={"description": "Versão das definições (etl/definicoes.py)"})
    carga_id = fields.Integer(metadata={"description": "Carga da base analítica que gerou os números"})
    dados_de = fields.Date(metadata={"description": "1º dia da base bruta (fuso de São Paulo)"})
    dados_ate = fields.Date(metadata={"description": "Último dia da base bruta (fuso de São Paulo)"})
    carga_em = fields.DateTime(metadata={"description": "Fim da carga (UTC)"})
    fonte = fields.String(metadata={"description": "Objeto da base analítica consultado"})


# ---------- entrada ----------
class PeriodoSchema(Schema):
    pais = fields.String(load_default="Brazil", metadata={"description": "País (BDR-007: só Brazil na entrega)"})
    inicio = fields.Date(load_default=None, metadata={"description": "1º dia da 1ª sessão, inclusive (São Paulo)"})
    fim = fields.Date(load_default=None, metadata={"description": "Último dia da 1ª sessão, inclusive"})

    @validates_schema
    def _ordem(self, dados: dict, **_) -> None:
        if dados.get("inicio") and dados.get("fim") and dados["inicio"] > dados["fim"]:
            raise ValidationError("inicio depois de fim", "inicio")


class CoortesQuerySchema(PeriodoSchema):
    granularidade = fields.String(load_default="mes", validate=validate.OneOf(GRANULARIDADES),
                                  metadata={"description": "mes | semana | periodo (o período todo, por nível)"})
    dimensao = fields.String(load_default="geral", validate=validate.OneOf(DIMENSOES),
                             metadata={"description": "Abre a taxa por nível desta dimensão"})


class EfeitosQuerySchema(Schema):
    pais = fields.String(load_default="Brazil")
    ajuste = fields.String(load_default="ajustado", validate=validate.OneOf(("ajustado", "bruto")),
                           metadata={"description": "ajustado (regressão, mesmo mês e perfil) | bruto (sem ajuste)"})


# ---------- saída ----------
class TaxaSchema(Schema):
    novos = fields.Integer(allow_none=True, metadata={"description": "Novatos elegíveis (denominador)"})
    voltaram = fields.Integer(allow_none=True, metadata={"description": "Novatos com nova sessão em até 7 dias"})
    taxa = fields.Float(allow_none=True, metadata={"description": "voltaram / novos"})
    ic_inf = fields.Float(allow_none=True, metadata={"description": "IC 95% de Wilson, limite inferior"})
    ic_sup = fields.Float(allow_none=True, metadata={"description": "IC 95% de Wilson, limite superior"})
    amostra_suficiente = fields.Boolean(metadata={"description": "Metade do IC ≤ 10 p.p."})


class KpisSchema(Schema):
    meta = fields.Nested(MetaSchema)
    pais = fields.String()
    inicio = fields.Date(allow_none=True)
    fim = fields.Date(allow_none=True)
    retorno_7d = fields.Nested(TaxaSchema)
    recusa_total = fields.Nested(TaxaSchema, metadata={"description": "Novatos com recusa total na 1ª conversa"})


class LinhaCoorteSchema(TaxaSchema):
    coorte = fields.Date(allow_none=True, metadata={"description": "Início da semana/mês; nulo em 'periodo'"})
    nivel = fields.String(metadata={"description": "Nível da dimensão ('todos' em 'geral')"})
    suprimido_k = fields.Boolean(metadata={"description": "Menos de 20 novatos: números ocultos (k-anonimato)"})


class CoortesSchema(Schema):
    meta = fields.Nested(MetaSchema)
    pais = fields.String()
    granularidade = fields.String()
    dimensao = fields.String()
    linhas = fields.List(fields.Nested(LinhaCoorteSchema))


class EfeitoSchema(Schema):
    fator = fields.String()
    rotulo_fator = fields.String()
    nivel = fields.String()
    rotulo_nivel = fields.String()
    referencia = fields.String()
    rotulo_referencia = fields.String()
    n = fields.Integer(allow_none=True, metadata={"description": "Novatos neste nível"})
    efeito_pp = fields.Float(allow_none=True, metadata={"description": "Diferença em p.p. contra a referência"})
    ic_inf = fields.Float(allow_none=True)
    ic_sup = fields.Float(allow_none=True)
    ic_cruza_zero = fields.Boolean(allow_none=True, metadata={"description": "IC inclui o zero: sem evidência"})
    suprimido_k = fields.Boolean()


class EfeitosSchema(Schema):
    meta = fields.Nested(MetaSchema)
    pais = fields.String()
    ajuste = fields.String()
    metodo = fields.String(allow_none=True)
    n_modelo = fields.Integer(allow_none=True, metadata={"description": "Novatos no modelo"})
    efeitos = fields.List(fields.Nested(EfeitoSchema))


class HealthSchema(Schema):
    status = fields.String(metadata={"description": "ok | degradado"})
    banco = fields.String()
    ultima_carga = fields.Dict(allow_none=True)
