-- RODAR NO SERVIDOR (banco painel_ateg, "Painel ATEG" no pgAdmin). Só leitura: mostra o que já existe para as abas novas.
SELECT o AS objeto, to_regclass('public.' || o) IS NOT NULL AS existe
FROM unnest(ARRAY['vw_tipo','resumo_tipo','vw_resumo_leite_mensal','vw_ovino_mensal','mv_visitas','municipio_regiao']) AS o
UNION ALL
SELECT table_name || '.' || column_name, true
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name IN ('vw_resumo_leite_mensal','vw_ovino_mensal') AND column_name = 'regiao';
