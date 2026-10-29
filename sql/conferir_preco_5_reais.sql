-- Rodar no banco local api_sisateg (pgAdmin). Mostra os lançamentos de venda de leite in natura com preço unitário R$ 5,00 em setembro/2026.
SELECT id_propriedade, id_visita, dt_referencia, item, valor
FROM public.sisateg_receita_despesa
WHERE atividade = 'BOVINOCULTURA DE LEITE'
  AND tipo_valor = 'VALOR_UNITARIO'
  AND item ILIKE 'Venda de leite in natura%'
  AND valor = 5
  AND dt_referencia >= DATE '2026-09-01'
  AND dt_referencia < DATE '2026-10-01'
ORDER BY id_propriedade, dt_referencia;
