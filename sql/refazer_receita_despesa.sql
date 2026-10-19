-- RODAR NO BANCO LOCAL api_sisateg, depois de carregar sisateg_receita e sisateg_despesa da API.
-- sisateg_receita_despesa = receita e despesa empilhadas (mesmas colunas; a despesa tem a coluna extra index_name, que não entra).
-- AJUSTE a data de corte (aqui 2026-07-01) para o início da janela que acabou de ser recarregada.
-- Antes do corte, o histórico antigo da sisateg_receita_despesa é mantido como está.

-- PASSO A: monta a tabela nova ao lado da atual, com os mesmos tipos de colunas da atual
DO $$
DECLARE sel text;
BEGIN
  SELECT string_agg(format('%I::%s', attname, format_type(atttypid, atttypmod)), ', ' ORDER BY attnum) INTO sel
  FROM pg_attribute
  WHERE attrelid = 'public.sisateg_receita_despesa'::regclass AND attnum > 0 AND NOT attisdropped;
  EXECUTE 'DROP TABLE IF EXISTS public.sisateg_receita_despesa_novo';
  EXECUTE format('CREATE TABLE public.sisateg_receita_despesa_novo AS SELECT %s FROM public.sisateg_receita UNION ALL SELECT %s FROM public.sisateg_despesa', sel, sel);
END $$;

-- (opcional) conferir por mês: atual x nova
-- WITH o AS (SELECT to_char(dt_referencia,'YYYY-MM') mes, COUNT(*) n FROM public.sisateg_receita_despesa GROUP BY 1),
--      n AS (SELECT to_char(dt_referencia,'YYYY-MM') mes, COUNT(*) n FROM public.sisateg_receita_despesa_novo GROUP BY 1)
-- SELECT COALESCE(o.mes,n.mes) mes, o.n atual, n.n nova FROM o FULL JOIN n ON o.mes=n.mes ORDER BY 1 DESC;

-- PASSO B: troca só da janela recarregada (tudo ou nada)
BEGIN;
DELETE FROM public.sisateg_receita_despesa WHERE dt_referencia >= DATE '2026-07-01';
INSERT INTO public.sisateg_receita_despesa
SELECT * FROM public.sisateg_receita_despesa_novo WHERE dt_referencia >= DATE '2026-07-01';
COMMIT;
DROP TABLE IF EXISTS public.sisateg_receita_despesa_novo;
