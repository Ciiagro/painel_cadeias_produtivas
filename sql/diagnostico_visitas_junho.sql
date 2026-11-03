-- RODAR NO BANCO LOCAL (api_sisateg). Só leitura. Visitas que estão na planilha de 2025-06 e faltam no painel:
-- 7091175 (propriedade 446008, P.A BOM SUCESSO, ativa = Não) e 7167135 (propriedade 446027, P.A EMASA, ativa = Sim)

-- 1) A visita: referência, exclusão, status
SELECT * FROM public.sisateg_rel_listar_visita WHERE id_visita::text IN ('7091175','7167135');

-- 2) Os lançamentos delas, por filtro que o painel usa (atividade, status, tipo)
SELECT id_visita, id_propriedade, atividade, status_item, tipo_registro, tipo_valor,
       MIN(dt_referencia) AS ref_min, MAX(dt_referencia) AS ref_max, COUNT(*) AS linhas
FROM public.sisateg_receita_despesa
WHERE id_visita::text IN ('7091175','7167135')
GROUP BY 1,2,3,4,5,6 ORDER BY 1,3,4,5,6;

-- 3) As propriedades estão na lista de propriedades do painel?
SELECT * FROM public.resumo_propriedades WHERE id_propriedade::text IN ('446008','446027');
