-- TESTE (rodar no api_sisateg, F5): só o técnico ALEXSON, set/2026. Não cria tabela.
-- Compare com a planilha do SisATeG: 29 propriedades, produção total 21358.
WITH ids AS (
  SELECT DISTINCT id_propriedade FROM public.propriedades_ativas_na_ateg
  WHERE tecnico_atual ILIKE '%ALEXSON REIS%'
),
base AS (
  SELECT r.* FROM public.sisateg_receita_despesa r
  WHERE r.atividade = 'BOVINOCULTURA DE LEITE' AND r.status_item = 'ATIVO' AND r.tipo_registro = 'PRINCIPAL'
    AND r.dt_referencia BETWEEN DATE '2026-09-01' AND DATE '2026-09-30'
    AND r.id_propriedade IN (SELECT id_propriedade FROM ids)
),
q AS (SELECT id_propriedade, grupo, id_visita, id_item, dt_referencia, subgrupo, item, SUM(valor) AS qtd
      FROM base WHERE tipo_valor='QUANTIDADE' GROUP BY 1,2,3,4,5,6,7),
pr AS (SELECT id_propriedade, grupo, id_visita, id_item, dt_referencia, AVG(valor) AS preco
       FROM base WHERE tipo_valor='VALOR_UNITARIO' GROUP BY 1,2,3,4,5),
v AS (SELECT q.id_propriedade, q.grupo, q.subgrupo, q.item, q.qtd, q.qtd*pr.preco AS valor
      FROM q JOIN pr USING (id_propriedade, grupo, id_visita, id_item, dt_referencia)),
fin AS (
  SELECT id_propriedade,
    COALESCE(SUM(qtd) FILTER (WHERE grupo='Receita' AND item ILIKE 'Venda de leite in natura%'),0)
  + COALESCE(SUM(qtd) FILTER (WHERE grupo='Despesa' AND item ILIKE 'Leite consumido%'),0)
  + COALESCE(SUM(qtd) FILTER (WHERE grupo='Despesa' AND item ILIKE 'Leite para bezerra%'),0) AS producao,
    SUM(valor) FILTER (WHERE grupo='Receita' AND subgrupo NOT ILIKE 'Empr%' AND subgrupo NOT ILIKE 'Investimento%'
       AND (subgrupo <> 'Venda de leite' OR item ILIKE 'Venda de leite in natura%' OR item ILIKE 'Bonifica%')) AS receita,
    SUM(valor) FILTER (WHERE grupo='Despesa' AND subgrupo NOT ILIKE 'Empr%' AND subgrupo NOT ILIKE 'Investimento%'
       AND subgrupo NOT ILIKE 'Aleitamento%' AND item NOT ILIKE 'M_o de obra familiar') AS despesa_direta
  FROM v GROUP BY 1
)
SELECT i.id_propriedade, COALESCE(f.producao,0) AS producao, ROUND(COALESCE(f.receita,0)::numeric,2) AS receita,
       ROUND(COALESCE(f.despesa_direta,0)::numeric,2) AS despesa_direta
FROM ids i LEFT JOIN fin f USING (id_propriedade)
UNION ALL
SELECT NULL, SUM(f.producao), ROUND(SUM(f.receita)::numeric,2), ROUND(SUM(f.despesa_direta)::numeric,2) FROM fin f
ORDER BY 1 NULLS LAST;
