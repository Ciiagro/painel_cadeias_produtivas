-- RODAR NO SERVIDOR (banco painel_ateg), com o usuário administrador. Cria um usuário SÓ DE LEITURA para o painel publicado.
-- Troque TROQUE_ESTA_SENHA por uma senha forte e NOVA (não use a do postgres) antes de rodar.
CREATE ROLE painel_leitura LOGIN PASSWORD 'ranes%2015';
GRANT CONNECT ON DATABASE painel_ateg TO painel_leitura;
GRANT USAGE ON SCHEMA public TO painel_leitura;
-- As views rodam com a permissão do dono; o painel só precisa ler as duas views:
GRANT SELECT ON public.vw_propriedades, public.vw_resumo_leite_mensal TO painel_leitura;
-- Depois de cada cópia (o script recria as views), reaplique:
--   GRANT SELECT ON public.vw_propriedades, public.vw_resumo_leite_mensal TO painel_leitura;
