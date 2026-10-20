-- =====================================================================
-- RODAR NO BANCO LOCAL  api_sisateg   (F5 uma vez; leva alguns minutos)
-- Cria DUAS tabelas:
--   public.resumo_propriedades   -> 1 linha por propriedade ATIVA (todas as atividades): produtor, técnico,
--                                   supervisor (SisATeG), município, áreas, projeto e datas do vínculo.
--   public.resumo_leite_mensal   -> 1 linha por propriedade e mês: produção, receita bruta e despesas do LEITE.
-- Assim o técnico mostra TODAS as suas propriedades; quem não tem leite lançado aparece sem valores.
-- "Ativa" = lista public.propriedades_ativas_na_ateg.
-- Regras do leite (conferidas com o relatório do SisATeG):
--   valor do lançamento = QUANTIDADE x VALOR_UNITARIO (mesma visita e mesmo item)
--   venda_leite_rs = leite vendido (in natura) + Bonificação do leite por qualidade (receita do leite)
--   receita_bruta  = leite vendido (+ bonificação), venda de animal, esterco, volumoso e outras receitas;
--                    NÃO conta empréstimo, venda de bem, nem os itens de preço do leite
--   despesa_direta = despesas menos aquisição de bem, empréstimo, "Mão de obra familiar" e "Aleitamento artificial"
--   producao_leite_l = leite vendido + consumido (mão de obra familiar) + leite para bezerras
-- =====================================================================

DROP TABLE IF EXISTS public.resumo_propriedades;
CREATE TABLE public.resumo_propriedades AS
WITH ativas AS (  -- propriedades ATIVAS que têm vínculo ATIVO de LEITE
  SELECT id_propriedade, MAX(produtor) AS produtor, MAX(NULLIF(tecnico_atual,'')) AS tecnico_a,
         MAX(NULLIF(supervisor_atual,'')) AS supervisor_a
  FROM public.propriedades_ativas_na_ateg
  WHERE id_propriedade::text IN (
        SELECT id_propriedade::text FROM public.sisateg_vinculo_propriedade
        WHERE atividade ILIKE '%LEITE%' AND UPPER(status_vinculo) = 'ATIVO')
  GROUP BY 1
),
leite_ids AS (  -- toda propriedade que já lançou leite (ativa ou não) desde o início da base
  SELECT DISTINCT id_propriedade FROM public.sisateg_receita_despesa
  WHERE atividade = 'BOVINOCULTURA DE LEITE' AND status_item = 'ATIVO' AND tipo_registro = 'PRINCIPAL'
    AND dt_referencia >= DATE '2024-06-01'
),
todas AS (  -- ativas + inativas que têm leite lançado (ativa = TRUE/FALSE)
  SELECT id_propriedade, produtor, tecnico_a, supervisor_a, TRUE AS ativa FROM ativas
  UNION ALL
  SELECT l.id_propriedade, NULL, NULL, NULL, FALSE FROM leite_ids l
  WHERE l.id_propriedade NOT IN (SELECT id_propriedade FROM ativas)
),
acomp AS (
  SELECT id_propriedade, MAX(tecnico_atual) AS tecnico_m, MAX(tecnico_responsavel) AS tecnico_r,
         MAX(supervisor_atual) AS supervisor_m, MAX(produtor) AS produtor_m, MAX(imovel) AS imovel_m
  FROM public.acompanhamento_mensal_visitas
  WHERE id_propriedade IN (SELECT id_propriedade FROM todas) GROUP BY 1
),
nome AS (
  SELECT id_propriedade, MAX(propriedade) AS propriedade
  FROM public.sisateg_rel_indicador_padrao_mensal
  WHERE propriedade IS NOT NULL AND id_propriedade IN (SELECT id_propriedade FROM todas) GROUP BY 1
),
area AS (
  SELECT id_propriedade, MAX(area_total) AS area_total, MAX(area_atividades_produtivas) AS area_produtiva,
         MAX(municipio) AS municipio, MAX(uf) AS uf
  FROM public.dim_propriedade WHERE id_propriedade IN (SELECT id_propriedade FROM todas) GROUP BY 1
),
vinc AS (
  SELECT id_propriedade::text AS idp, id_projeto, projeto, status_vinculo, motivo_desativacao,
         dt_inicio::date AS ini, dt_fim::date AS fim
  FROM public.sisateg_vinculo_propriedade
  WHERE atividade ILIKE '%LEITE%' AND id_propriedade::text IN (SELECT id_propriedade::text FROM todas)
),
vu AS (  -- um vínculo por propriedade: o ATIVO (se houver) de início mais recente
  SELECT DISTINCT ON (idp) idp, id_projeto, projeto, ini, fim, status_vinculo, motivo_desativacao
  FROM vinc
  ORDER BY idp, (UPPER(status_vinculo) = 'ATIVO') DESC, ini DESC, fim DESC NULLS FIRST
),
nproj AS (SELECT idp, COUNT(DISTINCT id_projeto) AS qtd_projetos FROM vinc GROUP BY 1)
SELECT a.id_propriedade,
       COALESCE(n.propriedade, ac.imovel_m) AS propriedade,
       COALESCE(a.produtor, ac.produtor_m) AS produtor,
       btrim(COALESCE(a.tecnico_a, ac.tecnico_m, ac.tecnico_r), E' \t\r\n') AS tecnico,
       COALESCE(a.supervisor_a, ac.supervisor_m)         AS supervisor_sisateg,
       ar.municipio, ar.uf,
       ROUND(ar.area_total::numeric, 2)    AS area_total,
       ROUND(ar.area_produtiva::numeric, 2) AS area_produtiva,
       vu.projeto, np.qtd_projetos,
       vu.ini AS inicio_projeto, vu.fim AS fim_projeto,
       vu.status_vinculo, vu.motivo_desativacao, a.ativa
FROM todas a
LEFT JOIN acomp ac ON ac.id_propriedade = a.id_propriedade
LEFT JOIN nome n   ON n.id_propriedade  = a.id_propriedade
LEFT JOIN area ar  ON ar.id_propriedade = a.id_propriedade
LEFT JOIN vu       ON vu.idp = a.id_propriedade::text
LEFT JOIN nproj np ON np.idp = a.id_propriedade::text;

CREATE INDEX ON public.resumo_propriedades (id_propriedade);
CREATE INDEX ON public.resumo_propriedades (tecnico);

-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS public.resumo_leite_mensal;
CREATE TABLE public.resumo_leite_mensal AS
WITH param AS (
  SELECT DATE '2024-06-01' AS data_inicio, DATE '2026-12-31' AS data_fim
),
base AS (
  SELECT r.*
  FROM public.sisateg_receita_despesa r, param p
  WHERE r.atividade = 'BOVINOCULTURA DE LEITE'
    AND r.status_item = 'ATIVO'
    AND r.tipo_registro = 'PRINCIPAL'
    AND r.dt_referencia BETWEEN p.data_inicio AND p.data_fim
    AND r.id_propriedade IN (SELECT id_propriedade FROM public.resumo_propriedades)
),
q AS (
  SELECT id_propriedade, grupo, id_visita, id_item, dt_referencia, subgrupo, item, SUM(valor) AS qtd
  FROM base WHERE tipo_valor = 'QUANTIDADE' GROUP BY 1,2,3,4,5,6,7
),
pr AS (
  SELECT id_propriedade, grupo, id_visita, id_item, dt_referencia, AVG(valor) AS preco
  FROM base WHERE tipo_valor = 'VALOR_UNITARIO' GROUP BY 1,2,3,4,5
),
v AS (
  SELECT q.id_propriedade, date_trunc('month', q.dt_referencia)::date AS mes,
         q.grupo, q.subgrupo, q.item, q.qtd, q.qtd * pr.preco AS valor
  FROM q JOIN pr USING (id_propriedade, grupo, id_visita, id_item, dt_referencia)
),
tec_mes AS (  -- técnico responsável pela visita daquele mês (técnico da época)
  SELECT b.id_propriedade, date_trunc('month', b.dt_referencia)::date AS mes,
         MAX(btrim(av.tecnico_responsavel, E' \t\r\n')) AS tecnico
  FROM base b
  JOIN public.acompanhamento_mensal_visitas av ON av.id_visita::text = b.id_visita::text
  GROUP BY 1, 2
),
fin AS (
  SELECT id_propriedade, mes,
    SUM(qtd) FILTER (WHERE grupo = 'Receita' AND item ILIKE 'Venda de leite in natura%') AS leite_vendido_l,
    SUM(qtd) FILTER (WHERE grupo = 'Despesa' AND item ILIKE 'Leite consumido%') AS leite_consumido_l,
    SUM(qtd) FILTER (WHERE grupo = 'Despesa' AND item ILIKE 'Leite para bezerra%') AS leite_bezerras_l,
    SUM(valor) FILTER (WHERE grupo = 'Receita'
         AND (item ILIKE 'Venda de leite in natura%' OR item ILIKE 'Bonifica%')) AS venda_leite_rs,
    SUM(valor) FILTER (WHERE grupo = 'Receita'
         AND subgrupo NOT ILIKE 'Empr%' AND subgrupo NOT ILIKE 'Investimento%'
         AND (subgrupo <> 'Venda de leite' OR item ILIKE 'Venda de leite in natura%' OR item ILIKE 'Bonifica%')) AS receita_bruta,
    SUM(valor) FILTER (WHERE grupo = 'Despesa'
         AND subgrupo NOT ILIKE 'Empr%' AND subgrupo NOT ILIKE 'Investimento%') AS despesa_total,
    SUM(valor) FILTER (WHERE grupo = 'Despesa'
         AND subgrupo NOT ILIKE 'Empr%' AND subgrupo NOT ILIKE 'Investimento%'
         AND subgrupo NOT ILIKE 'Aleitamento%' AND item NOT ILIKE 'M_o de obra familiar') AS despesa_direta,
    SUM(valor) FILTER (WHERE grupo = 'Despesa' AND item ILIKE 'M_o de obra familiar') AS mao_obra_familiar,
    SUM(valor) FILTER (WHERE grupo = 'Despesa' AND subgrupo ILIKE 'Aleitamento%') AS despesa_aleitamento
  FROM v GROUP BY 1,2
)
SELECT f.id_propriedade,
       to_char(f.mes, 'YYYY-MM') AS mes,
       t.tecnico,
       ROUND((COALESCE(f.leite_vendido_l,0) + COALESCE(f.leite_consumido_l,0) + COALESCE(f.leite_bezerras_l,0))::numeric, 1) AS producao_leite_l,
       ROUND(f.leite_vendido_l::numeric, 1)     AS leite_vendido_l,
       ROUND(f.leite_consumido_l::numeric, 1)   AS leite_consumido_l,
       ROUND(f.leite_bezerras_l::numeric, 1)    AS leite_bezerras_l,
       ROUND(f.venda_leite_rs::numeric, 2)      AS venda_leite_rs,
       ROUND(f.receita_bruta::numeric, 2)       AS receita_bruta,
       ROUND(f.despesa_direta::numeric, 2)      AS despesa_direta,
       ROUND(f.mao_obra_familiar::numeric, 2)   AS mao_obra_familiar,
       ROUND(f.despesa_aleitamento::numeric, 2) AS despesa_aleitamento,
       ROUND(f.despesa_total::numeric, 2)       AS despesa_total
FROM fin f
LEFT JOIN tec_mes t ON t.id_propriedade = f.id_propriedade AND t.mes = f.mes;

CREATE INDEX ON public.resumo_leite_mensal (id_propriedade);
CREATE INDEX ON public.resumo_leite_mensal (tecnico);
CREATE INDEX ON public.resumo_leite_mensal (mes);
ANALYZE public.resumo_propriedades;
ANALYZE public.resumo_leite_mensal;

-- Conferência: propriedades ativas e quantas têm leite lançado
SELECT (SELECT COUNT(*) FROM public.resumo_propriedades) AS propriedades_ativas,
       (SELECT COUNT(DISTINCT id_propriedade) FROM public.resumo_leite_mensal) AS com_leite,
       (SELECT COUNT(*) FROM public.resumo_leite_mensal) AS linhas_mensais,
       (SELECT MAX(mes) FROM public.resumo_leite_mensal) AS ultimo_mes;
