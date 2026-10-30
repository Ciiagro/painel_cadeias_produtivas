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
--   despesa_direta = despesas menos aquisição de bem, empréstimo, "Mão de obra familiar", "Aleitamento artificial" e "Despesas com Formação de Forrageiras perene"
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
-- Lista (pequena, com índice) das visitas EXCLUÍDAS no SisATeG (dt_exclusao_visita preenchida): calculada uma vez e usada nas 3 tabelas abaixo.
-- Visitas só "Inválidas" (sem data de exclusão) continuam valendo: o SisATeG também conta essas na planilha.
DROP TABLE IF EXISTS tmp_visitas_invalidas;
CREATE TEMP TABLE tmp_visitas_invalidas AS
  SELECT DISTINCT id_visita::text AS id FROM public.sisateg_rel_listar_visita
  WHERE dt_exclusao_visita IS NOT NULL;
CREATE INDEX ON tmp_visitas_invalidas (id);
ANALYZE tmp_visitas_invalidas;

-- Filtra a tabela grande UMA vez só; os 3 resumos abaixo usam esta cópia menor (bem mais rápido)
DROP TABLE IF EXISTS tmp_base;
CREATE TEMP TABLE tmp_base AS
SELECT r.* FROM public.sisateg_receita_despesa r
WHERE r.atividade = 'BOVINOCULTURA DE LEITE' AND r.status_item = 'ATIVO' AND r.tipo_registro = 'PRINCIPAL'
  AND r.dt_referencia >= DATE '2024-06-01' AND r.dt_referencia < CURRENT_DATE + 1
  AND NOT EXISTS (SELECT 1 FROM tmp_visitas_invalidas iv WHERE iv.id = r.id_visita::text)
  AND r.id_propriedade IN (SELECT id_propriedade FROM public.resumo_propriedades);
CREATE INDEX ON tmp_base (id_visita, id_item);
ANALYZE tmp_base;
-- Preço ATIVO que só existe como DETALHADO (o SisATeG usa): entra quando o item tem quantidade ativa e NENHUM preço ativo principal
INSERT INTO tmp_base
SELECT r.* FROM public.sisateg_receita_despesa r
WHERE r.atividade = 'BOVINOCULTURA DE LEITE' AND r.status_item = 'ATIVO' AND r.tipo_registro = 'DETALHADO'
  AND r.tipo_valor = 'VALOR_UNITARIO' AND r.valor IS NOT NULL
  AND r.dt_referencia >= DATE '2024-06-01' AND r.dt_referencia < CURRENT_DATE + 1
  AND NOT EXISTS (SELECT 1 FROM tmp_visitas_invalidas iv WHERE iv.id = r.id_visita::text)
  AND r.id_propriedade IN (SELECT id_propriedade FROM public.resumo_propriedades)
  AND EXISTS (SELECT 1 FROM tmp_base q WHERE q.id_visita = r.id_visita AND q.id_item = r.id_item AND q.dt_referencia = r.dt_referencia AND q.tipo_valor = 'QUANTIDADE')
  AND NOT EXISTS (SELECT 1 FROM tmp_base p WHERE p.id_visita = r.id_visita AND p.id_item = r.id_item AND p.dt_referencia = r.dt_referencia AND p.tipo_valor = 'VALOR_UNITARIO');
UPDATE tmp_base SET tipo_registro = 'PRINCIPAL' WHERE tipo_registro = 'DETALHADO';   -- (só as linhas de preço acrescentadas acima eram detalhadas)
-- O mês de cada visita é o da REFERÊNCIA DA VISITA (é assim que a planilha do SisATeG conta); a data do item só vale se a visita não tiver referência
UPDATE tmp_base b SET dt_referencia = to_date(lv.referencia_visita || '-01', 'YYYY-MM-DD')
FROM public.sisateg_rel_listar_visita lv
WHERE lv.id_visita::text = b.id_visita::text AND lv.referencia_visita ~ '^[0-9]{4}-[0-9]{2}$'
  AND ABS(to_date(lv.referencia_visita || '-01', 'YYYY-MM-DD') - b.dt_referencia::date) <= 366;   -- referência muito distante da data do item (ex.: visita de 2023 editada em 2026) é ignorada
-- Visita SEM referência válida: o mês dela passa a ser o mais recente entre os itens dela
UPDATE tmp_base b SET dt_referencia = m.mx
FROM (SELECT b2.id_visita, MAX(b2.dt_referencia) AS mx
      FROM tmp_base b2
      WHERE NOT EXISTS (SELECT 1 FROM public.sisateg_rel_listar_visita lv
                        WHERE lv.id_visita::text = b2.id_visita::text AND lv.referencia_visita ~ '^[0-9]{4}-[0-9]{2}$')
      GROUP BY 1) m
WHERE m.id_visita = b.id_visita AND b.dt_referencia < m.mx;
CREATE INDEX ON tmp_base (id_propriedade, id_visita);
ANALYZE tmp_base;

-- nomes de supervisor sem acento quebrado, para recompor os que vêm corrompidos da origem (calculado UMA vez)
DROP TABLE IF EXISTS tmp_sup_ok;
CREATE TEMP TABLE tmp_sup_ok AS
  SELECT DISTINCT supervisor_atual AS s FROM public.acompanhamento_mensal_visitas
  WHERE supervisor_atual IS NOT NULL AND supervisor_atual NOT LIKE '%&#65533;%'
  UNION
  SELECT DISTINCT supervisor_atual FROM public.propriedades_ativas_na_ateg
  WHERE supervisor_atual IS NOT NULL AND supervisor_atual NOT LIKE '%&#65533;%';
ANALYZE tmp_sup_ok;

-- técnico e supervisor de cada visita (só das visitas que interessam), com índice
DROP TABLE IF EXISTS tmp_av;
CREATE TEMP TABLE tmp_av AS
  SELECT av.id_visita::text AS id,
         MAX(btrim(av.tecnico_responsavel, E' \t\r\n')) AS tecnico,
         MAX(NULLIF(btrim(av.supervisor_atual, E' \t\r\n'), '')) AS sup
  FROM public.acompanhamento_mensal_visitas av
  WHERE av.id_visita::text IN (SELECT DISTINCT id_visita::text FROM tmp_base)
  GROUP BY 1;
CREATE INDEX ON tmp_av (id);
ANALYZE tmp_av;

DROP TABLE IF EXISTS public.resumo_leite_mensal;
-- Etapas (cada uma vira tabela temporária; o tempo de cada uma aparece no .bat)
DROP TABLE IF EXISTS tmp_q;
CREATE TEMP TABLE tmp_q AS
  SELECT id_propriedade, grupo, id_visita, id_item, dt_referencia, subgrupo, item, SUM(valor) AS qtd
  FROM tmp_base WHERE tipo_valor = 'QUANTIDADE' GROUP BY 1,2,3,4,5,6,7;
DROP TABLE IF EXISTS tmp_pr;
CREATE TEMP TABLE tmp_pr AS
  SELECT id_propriedade, grupo, id_visita, id_item, dt_referencia, AVG(valor) AS preco
  FROM tmp_base WHERE tipo_valor = 'VALOR_UNITARIO' GROUP BY 1,2,3,4,5;
CREATE INDEX ON tmp_q (id_propriedade, id_visita, id_item);
CREATE INDEX ON tmp_pr (id_propriedade, id_visita, id_item);
ANALYZE tmp_q;
ANALYZE tmp_pr;
DROP TABLE IF EXISTS tmp_v;
CREATE TEMP TABLE tmp_v AS
  SELECT q.id_propriedade, date_trunc('month', q.dt_referencia)::date AS mes,
         q.grupo, q.subgrupo, q.item, q.qtd, q.qtd * pr.preco AS valor
  FROM tmp_q q JOIN tmp_pr pr USING (id_propriedade, grupo, id_visita, id_item, dt_referencia);
ANALYZE tmp_v;
DROP TABLE IF EXISTS tmp_fin;
CREATE TEMP TABLE tmp_fin AS
  SELECT id_propriedade, mes,
    SUM(qtd) FILTER (WHERE grupo = 'Receita' AND item ILIKE 'Venda de leite in natura%') AS leite_vendido_l,
    SUM(qtd) FILTER (WHERE grupo = 'Despesa' AND item ILIKE 'Leite consumido%') AS leite_consumido_l,
    SUM(qtd) FILTER (WHERE grupo = 'Despesa' AND item ILIKE 'Leite para bezerra%') AS leite_bezerras_l,
    SUM(qtd) FILTER (WHERE grupo = 'Despesa' AND item ILIKE 'Leite de descarte%') AS leite_descarte_l,   -- o SisATeG conta o leite descartado como produzido
    SUM(valor) FILTER (WHERE grupo = 'Receita' AND item ILIKE 'Venda de leite in natura%') AS leite_in_natura_rs,
    SUM(valor) FILTER (WHERE grupo = 'Receita'
         AND (item ILIKE 'Venda de leite in natura%' OR item ILIKE 'Bonifica%')) AS venda_leite_rs,
    SUM(valor) FILTER (WHERE grupo = 'Receita'
         AND subgrupo NOT ILIKE 'Empr%' AND subgrupo NOT ILIKE 'Investimento%'
         AND (subgrupo <> 'Venda de leite' OR item ILIKE 'Venda de leite in natura%' OR item ILIKE 'Bonifica%' OR item ILIKE 'Divis%sobras%')) AS receita_bruta,   -- sobras de cooperativa são receita
    SUM(valor) FILTER (WHERE grupo = 'Despesa'
         AND subgrupo NOT ILIKE 'Empr%' AND subgrupo NOT ILIKE 'Investimento%') AS despesa_total,
    SUM(valor) FILTER (WHERE grupo = 'Despesa'
         AND subgrupo NOT ILIKE 'Empr%' AND subgrupo NOT ILIKE 'Investimento%'
         AND subgrupo NOT ILIKE 'Aleitamento%' AND subgrupo NOT ILIKE 'Despesas com Forma%' AND item NOT ILIKE 'M_o de obra familiar') AS despesa_direta,
    SUM(valor) FILTER (WHERE grupo = 'Despesa' AND item ILIKE 'M_o de obra familiar') AS mao_obra_familiar,
    SUM(valor) FILTER (WHERE grupo = 'Despesa' AND subgrupo ILIKE 'Aleitamento%') AS despesa_aleitamento
  FROM tmp_v GROUP BY 1,2;
DROP TABLE IF EXISTS tmp_tec;
CREATE TEMP TABLE tmp_tec AS
  -- técnico responsável pela visita daquele mês (técnico da época)
  SELECT b.id_propriedade, date_trunc('month', b.dt_referencia)::date AS mes,
         MAX(av.tecnico) AS tecnico,
         MAX(av.sup) AS supervisor_raw   -- supervisor DA ÉPOCA da visita
  FROM tmp_base b
  JOIN tmp_av av ON av.id = b.id_visita::text
  GROUP BY 1, 2;
DROP TABLE IF EXISTS tmp_vis;
CREATE TEMP TABLE tmp_vis AS
  -- visita(s) do mês (normalmente uma); serve para conferir com a planilha do SisATeG
  SELECT id_propriedade, date_trunc('month', dt_referencia)::date AS mes, string_agg(DISTINCT id_visita::text, ',' ORDER BY id_visita::text) AS id_visita
  FROM tmp_base GROUP BY 1, 2;
ANALYZE tmp_fin;
ANALYZE tmp_tec;
ANALYZE tmp_vis;

CREATE TABLE public.resumo_leite_mensal AS
SELECT f.id_propriedade,
       to_char(f.mes, 'YYYY-MM') AS mes,
       t.tecnico,
       CASE WHEN t.supervisor_raw LIKE '%&#65533;%'   -- nome com acento quebrado na origem: recompõe pelo nome certo (sup_ok)
            THEN COALESCE(sc.s, CASE WHEN t.supervisor_raw = 'JOS&#65533; EDILTON LOUSADA J&#65533;NIOR' THEN 'JOSÉ EDILTON LOUSADA JÚNIOR'
                                     ELSE replace(t.supervisor_raw, '&#65533;', '') END)
            ELSE t.supervisor_raw END AS supervisor,
       vm.id_visita,
       ROUND((COALESCE(f.leite_vendido_l,0) + COALESCE(f.leite_consumido_l,0) + COALESCE(f.leite_bezerras_l,0) + COALESCE(f.leite_descarte_l,0))::numeric, 1) AS producao_leite_l,
       ROUND(f.leite_vendido_l::numeric, 1)     AS leite_vendido_l,
       ROUND(f.leite_consumido_l::numeric, 1)   AS leite_consumido_l,
       ROUND(f.leite_bezerras_l::numeric, 1)    AS leite_bezerras_l,
       ROUND(f.leite_descarte_l::numeric, 1)    AS leite_descarte_l,
       ROUND(f.leite_in_natura_rs::numeric, 2)  AS leite_in_natura_rs,
       ROUND(f.venda_leite_rs::numeric, 2)      AS venda_leite_rs,
       ROUND(f.receita_bruta::numeric, 2)       AS receita_bruta,
       ROUND(f.despesa_direta::numeric, 2)      AS despesa_direta,
       ROUND(f.mao_obra_familiar::numeric, 2)   AS mao_obra_familiar,
       ROUND(f.despesa_aleitamento::numeric, 2) AS despesa_aleitamento,
       ROUND(f.despesa_total::numeric, 2)       AS despesa_total
FROM tmp_fin f
LEFT JOIN tmp_tec t ON t.id_propriedade = f.id_propriedade AND t.mes = f.mes
LEFT JOIN tmp_vis vm ON vm.id_propriedade = f.id_propriedade AND vm.mes = f.mes
LEFT JOIN LATERAL (SELECT MAX(k.s) AS s FROM tmp_sup_ok k
                   WHERE t.supervisor_raw LIKE '%&#65533;%' AND k.s LIKE replace(t.supervisor_raw, '&#65533;', '_')) sc ON TRUE;

CREATE INDEX ON public.resumo_leite_mensal (id_propriedade);
CREATE INDEX ON public.resumo_leite_mensal (tecnico);
CREATE INDEX ON public.resumo_leite_mensal (mes);
-- ---------------------------------------------------------------------
-- Despesa direta por SUBGRUPO e mês (mesma regra da despesa_direta acima; a soma dos subgrupos = despesa_direta)
DROP TABLE IF EXISTS public.resumo_despesa_subgrupo;
CREATE TABLE public.resumo_despesa_subgrupo AS
WITH base AS (
  SELECT r.* FROM tmp_base r
  WHERE r.atividade = 'BOVINOCULTURA DE LEITE' AND r.status_item = 'ATIVO' AND r.tipo_registro = 'PRINCIPAL'
    AND r.dt_referencia >= DATE '2024-06-01' AND r.dt_referencia < CURRENT_DATE + 1
    AND NOT EXISTS (SELECT 1 FROM tmp_visitas_invalidas iv WHERE iv.id = r.id_visita::text)   -- fora as visitas excluídas (o SisATeG também não conta)
    AND r.grupo = 'Despesa'
    AND r.id_propriedade IN (SELECT id_propriedade FROM public.resumo_propriedades)
),
q AS (
  SELECT id_propriedade, id_visita, id_item, dt_referencia, subgrupo, item, SUM(valor) AS qtd
  FROM base WHERE tipo_valor = 'QUANTIDADE' GROUP BY 1,2,3,4,5,6
),
pr AS (
  SELECT id_propriedade, id_visita, id_item, dt_referencia, AVG(valor) AS preco
  FROM base WHERE tipo_valor = 'VALOR_UNITARIO' GROUP BY 1,2,3,4
)
SELECT q.id_propriedade, to_char(date_trunc('month', q.dt_referencia), 'YYYY-MM') AS mes, q.subgrupo,
       ROUND(SUM(q.qtd * pr.preco)::numeric, 2) AS valor
FROM q JOIN pr USING (id_propriedade, id_visita, id_item, dt_referencia)
WHERE q.subgrupo NOT ILIKE 'Empr%' AND q.subgrupo NOT ILIKE 'Investimento%'
  AND q.subgrupo NOT ILIKE 'Aleitamento%' AND q.subgrupo NOT ILIKE 'Despesas com Forma%'
  AND q.item NOT ILIKE 'M_o de obra familiar'
GROUP BY 1,2,3;
CREATE INDEX ON public.resumo_despesa_subgrupo (id_propriedade, mes);

-- ---------------------------------------------------------------------
-- Receitas e despesas por TIPO (subgrupo) e classe (mesmo padrão do painel de ovinocaprinocultura): alimenta a aba "Receitas e despesas".
--   classe: Receita bruta | Fora da receita bruta (empréstimo/investimento)
--           Despesa direta | Outras despesas (formação de forrageiras, mão de obra familiar)
--           Aleitamento (fora do total) | Fora das despesas (empréstimo/investimento)
--   Os itens de "preço do leite" (subgrupo Venda de leite que não é leite in natura nem bonificação) não são receita: ficam de fora.
--   Despesa direta e receita bruta daqui = as mesmas do resumo mensal (as regras são idênticas).
DROP TABLE IF EXISTS public.resumo_tipo;
CREATE TABLE public.resumo_tipo AS
WITH base AS (
  SELECT r.* FROM tmp_base r
  WHERE r.atividade = 'BOVINOCULTURA DE LEITE' AND r.status_item = 'ATIVO' AND r.tipo_registro = 'PRINCIPAL'
    AND r.dt_referencia >= DATE '2024-06-01' AND r.dt_referencia < CURRENT_DATE + 1
    AND NOT EXISTS (SELECT 1 FROM tmp_visitas_invalidas iv WHERE iv.id = r.id_visita::text)   -- fora as visitas excluídas (o SisATeG também não conta)
    AND r.grupo IN ('Receita','Despesa')
    AND r.id_propriedade IN (SELECT id_propriedade FROM public.resumo_propriedades)
),
q AS (
  SELECT id_propriedade, id_visita, id_item, dt_referencia, grupo, subgrupo, item, SUM(valor) AS qtd
  FROM base WHERE tipo_valor = 'QUANTIDADE' GROUP BY 1,2,3,4,5,6,7
),
pr AS (
  SELECT id_propriedade, id_visita, id_item, dt_referencia, AVG(valor) AS preco
  FROM base WHERE tipo_valor = 'VALOR_UNITARIO' GROUP BY 1,2,3,4
),
v AS (
  SELECT q.id_propriedade, to_char(date_trunc('month', q.dt_referencia), 'YYYY-MM') AS mes, q.grupo, q.subgrupo,
         CASE WHEN q.grupo = 'Receita' AND (q.subgrupo ILIKE 'Empr%' OR q.subgrupo ILIKE 'Investimento%') THEN 'Fora da receita bruta'
              WHEN q.grupo = 'Receita' THEN 'Receita bruta'
              WHEN q.subgrupo ILIKE 'Empr%' OR q.subgrupo ILIKE 'Investimento%' THEN 'Fora das despesas'
              WHEN q.subgrupo ILIKE 'Aleitamento%' THEN 'Aleitamento (fora do total)'
              WHEN q.subgrupo ILIKE 'Despesas com Forma%' OR q.item ILIKE 'M_o de obra familiar' THEN 'Outras despesas'
              ELSE 'Despesa direta' END AS classe,
         q.qtd * pr.preco AS valor
  FROM q JOIN pr USING (id_propriedade, id_visita, id_item, dt_referencia)
  WHERE NOT (q.grupo = 'Receita' AND q.subgrupo = 'Venda de leite'
             AND NOT (q.item ILIKE 'Venda de leite in natura%' OR q.item ILIKE 'Bonifica%' OR q.item ILIKE 'Divis%sobras%'))
)
SELECT id_propriedade, mes, grupo, classe, subgrupo, ROUND(SUM(valor)::numeric, 2) AS valor
FROM v GROUP BY 1,2,3,4,5;
CREATE INDEX ON public.resumo_tipo (id_propriedade, mes);

-- ---------------------------------------------------------------------
-- Visitas para REVISAR: a referência cadastrada na visita (mês) é diferente do mês dos lançamentos.
-- O SisATeG/planilha conta o mês dos lançamentos; o painel usa a referência da visita (se estiver a até 1 ano de distância).
-- Assim a visita aparece em meses diferentes na planilha e no painel. A correção é no SisATeG (técnico).
DROP TABLE IF EXISTS public.resumo_leite_revisar;
CREATE TABLE public.resumo_leite_revisar AS
SELECT r.id_visita::text AS id_visita, r.id_propriedade,
       MAX(lv.imovel) AS propriedade_visita, MAX(lv.municipio_propriedade) AS municipio_visita,
       MAX(NULLIF(lv.tecnico_atual, '')) AS tecnico, replace(MAX(NULLIF(lv.supervisor_atual, '')), '&#65533;', '') AS supervisor_visita,
       lv.referencia_visita AS mes_visita,
       to_char(MIN(r.dt_referencia), 'YYYY-MM') AS mes_lanc_de, to_char(MAX(r.dt_referencia), 'YYYY-MM') AS mes_lanc_ate,
       CASE WHEN ABS(to_date(lv.referencia_visita || '-01', 'YYYY-MM-DD') - MIN(r.dt_referencia)::date) <= 366
            THEN lv.referencia_visita ELSE to_char(MIN(r.dt_referencia), 'YYYY-MM') END AS mes_painel
FROM public.sisateg_receita_despesa r
JOIN public.sisateg_rel_listar_visita lv ON lv.id_visita::text = r.id_visita::text
WHERE r.atividade = 'BOVINOCULTURA DE LEITE' AND r.status_item = 'ATIVO' AND r.tipo_registro = 'PRINCIPAL'
  AND r.dt_referencia >= DATE '2024-06-01' AND r.dt_referencia < CURRENT_DATE + 1
  AND lv.dt_exclusao_visita IS NULL
  AND lv.referencia_visita ~ '^[0-9]{4}-[0-9]{2}$'
  AND to_char(r.dt_referencia, 'YYYY-MM') <> lv.referencia_visita
  AND r.id_propriedade IN (SELECT id_propriedade FROM public.resumo_propriedades)
GROUP BY r.id_visita::text, r.id_propriedade, lv.referencia_visita;
CREATE INDEX ON public.resumo_leite_revisar (id_propriedade);

ANALYZE public.resumo_propriedades;
ANALYZE public.resumo_leite_mensal;

-- Conferência: propriedades ativas e quantas têm leite lançado
SELECT (SELECT COUNT(*) FROM public.resumo_propriedades) AS propriedades_ativas,
       (SELECT COUNT(DISTINCT id_propriedade) FROM public.resumo_leite_mensal) AS com_leite,
       (SELECT COUNT(*) FROM public.resumo_leite_mensal) AS linhas_mensais,
       (SELECT MAX(mes) FROM public.resumo_leite_mensal) AS ultimo_mes;
