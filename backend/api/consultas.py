"""SQL dos endpoints. Só lê views e tabelas da base analítica; regras de IC, amostra e k vêm das funções do banco.

Período (`inicio`, `fim`): dia da 1ª sessão no fuso de São Paulo. Nulo = sem limite.
"""

PERIODO = """
    (%(inicio)s::date IS NULL OR primeira_dia_local >= %(inicio)s::date)
    AND (%(fim)s::date IS NULL OR primeira_dia_local <= %(fim)s::date)
"""

# Taxa de retorno e % de recusa total no período (denominador = novatos elegíveis).
KPIS = f"""
    WITH a AS (
        SELECT count(*)                                AS n,
               count(*) FILTER (WHERE voltou_7d)       AS voltaram,
               count(*) FILTER (WHERE recusa_total)    AS recusas
        FROM primeira_experiencia
        WHERE elegivel AND pais = %(pais)s AND {PERIODO}
    )
    SELECT n, voltaram, voltaram::float8 / nullif(n, 0) AS taxa,
           wilson_inf(voltaram, n) AS ic_inf, wilson_sup(voltaram, n) AS ic_sup,
           amostra_suficiente(voltaram, n) AS amostra_suficiente,
           recusas, recusas::float8 / nullif(n, 0) AS taxa_recusa,
           wilson_inf(recusas, n) AS recusa_ic_inf, wilson_sup(recusas, n) AS recusa_ic_sup,
           amostra_suficiente(recusas, n) AS recusa_amostra_suficiente
    FROM a
"""

# Total por coorte (sem dimensão): a view já traz taxa, IC e amostra. O total aparece mesmo com n < 20.
COORTES_GERAL = """
    SELECT coorte, 'todos' AS nivel, novos, voltaram, taxa, ic_inf, ic_sup, amostra_suficiente,
           FALSE AS suprimido_k
    FROM vw_retorno_coorte
    WHERE pais = %(pais)s AND granularidade = %(granularidade)s
      AND (%(inicio)s::date IS NULL OR coorte >= date_trunc(%(trunc)s, %(inicio)s::date)::date)
      AND (%(fim)s::date IS NULL OR coorte <= %(fim)s::date)
    ORDER BY coorte
"""

# Por nível de uma dimensão (por coorte ou no período todo). k-anonimato: nível com menos de k_minimo()
# novatos volta sem números (o total 'geral' não é suprimido: é o tamanho da coorte, sem atributo).
COORTES_DIMENSAO = f"""
    WITH a AS (
        SELECT CASE %(granularidade)s WHEN 'mes' THEN coorte_mes WHEN 'semana' THEN coorte_semana END AS coorte,
               nivel, count(*) AS novos, count(*) FILTER (WHERE voltou_7d) AS voltaram
        FROM vw_novato_dimensao
        WHERE pais = %(pais)s AND dimensao = %(dimensao)s AND {PERIODO}
        GROUP BY 1, 2
    ),
    k AS (SELECT *, %(dimensao)s <> 'geral' AND novos < k_minimo() AS suprimido_k FROM a)
    SELECT coorte, nivel,
           CASE WHEN NOT suprimido_k THEN novos END                       AS novos,
           CASE WHEN NOT suprimido_k THEN voltaram END                    AS voltaram,
           CASE WHEN NOT suprimido_k THEN voltaram::float8 / novos END    AS taxa,
           CASE WHEN NOT suprimido_k THEN wilson_inf(voltaram, novos) END AS ic_inf,
           CASE WHEN NOT suprimido_k THEN wilson_sup(voltaram, novos) END AS ic_sup,
           NOT suprimido_k AND amostra_suficiente(voltaram, novos)        AS amostra_suficiente,
           suprimido_k
    FROM k
    ORDER BY coorte NULLS FIRST, novos DESC NULLS LAST, nivel
"""

# Efeito de cada fator (resultado_efeitos, gravado pela carga). n < k_minimo() também é suprimido.
EFEITOS = """
    SELECT fator, rotulo_fator, nivel, rotulo_nivel, referencia, rotulo_referencia, metodo, n_modelo,
           n < k_minimo() AS suprimido_k,
           CASE WHEN n >= k_minimo() THEN n END AS n,
           CASE WHEN n < k_minimo() THEN NULL WHEN %(ajuste)s = 'bruto' THEN bruto_pp ELSE ajustado_pp END
               AS efeito_pp,
           CASE WHEN n < k_minimo() THEN NULL WHEN %(ajuste)s = 'bruto' THEN bruto_ic_inf ELSE ajustado_ic_inf END
               AS ic_inf,
           CASE WHEN n < k_minimo() THEN NULL WHEN %(ajuste)s = 'bruto' THEN bruto_ic_sup ELSE ajustado_ic_sup END
               AS ic_sup
    FROM resultado_efeitos
    WHERE pais = %(pais)s
    ORDER BY ordem, nivel
"""
