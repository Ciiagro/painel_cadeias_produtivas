-- RODAR NO SERVIDOR (banco painel_ateg). O script de cópia já roda este arquivo sozinho depois de copiar.
-- Supervisor OFICIAL = public.ranking_tecnicos.ultimo_supervisor (o mesmo do ranking).
-- O supervisor do SisATeG fica em supervisor_sisateg, só para conferência.
-- Tabela de regiões/sindicatos (preenchida por sincronizar_municipios.py, que lê o Supabase). Se ainda não existir, cria vazia.
CREATE TABLE IF NOT EXISTS public.municipio_regiao (
  cod_ibge text, nome text, nome_norm text, regiao_faec text, regiao_sebrae text, regiao_planejamento text, sindicato text);

DROP VIEW IF EXISTS public.vw_tipo;
DROP VIEW IF EXISTS public.vw_despesa_subgrupo;
DROP VIEW IF EXISTS public.vw_resumo_leite_mensal;
DROP VIEW IF EXISTS public.vw_propriedades CASCADE;
CREATE VIEW public.vw_propriedades AS
SELECT p.id_propriedade, p.propriedade, p.produtor, p.tecnico,
       k.ultimo_supervisor AS supervisor, p.supervisor_sisateg,
       p.municipio, p.uf, mr.regiao_faec AS regiao, mr.sindicato, p.area_total, p.area_produtiva,
       p.projeto, p.qtd_projetos, p.inicio_projeto, p.fim_projeto, p.status_vinculo, p.motivo_desativacao, p.ativa
FROM public.resumo_propriedades p
LEFT JOIN (SELECT DISTINCT ON (btrim(tecnico_responsavel, E' \t\r\n')) btrim(tecnico_responsavel, E' \t\r\n') AS tec, ultimo_supervisor FROM public.ranking_tecnicos ORDER BY btrim(tecnico_responsavel, E' \t\r\n'), total_de_visitas DESC NULLS LAST) k ON k.tec = p.tecnico
LEFT JOIN LATERAL (
  SELECT r.regiao_faec, r.sindicato FROM public.municipio_regiao r
  WHERE r.nome_norm = upper(regexp_replace(btrim(translate(p.municipio,
        'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇáàâãäéèêëíìîïóòôõöúùûüç', 'AAAAAEEEEIIIIOOOOOUUUUCaaaaaeeeeiiiiooooouuuuc')), '\s+', ' ', 'g'))
  ORDER BY r.cod_ibge LIMIT 1) mr ON TRUE;

-- Mensal: o técnico e o supervisor são os da ÉPOCA (da visita do mês); se faltar, usa o último supervisor do técnico e depois o da propriedade.
CREATE VIEW public.vw_resumo_leite_mensal AS
SELECT v.id_propriedade, v.propriedade, v.produtor,
       COALESCE(m.tecnico, v.tecnico) AS tecnico,
       COALESCE(m.supervisor, k2.ultimo_supervisor, v.supervisor) AS supervisor,
       v.supervisor_sisateg, v.municipio, v.uf, v.regiao, v.sindicato, v.area_total, v.area_produtiva,
       v.projeto, v.qtd_projetos, v.inicio_projeto, v.fim_projeto, v.status_vinculo, v.motivo_desativacao, v.ativa,
       m.mes, m.id_visita, m.producao_leite_l, m.leite_vendido_l, m.leite_in_natura_rs, m.venda_leite_rs, m.receita_bruta, m.despesa_direta,
       (m.receita_bruta - m.despesa_direta) AS margem_bruta
FROM public.vw_propriedades v
JOIN public.resumo_leite_mensal m ON m.id_propriedade = v.id_propriedade
LEFT JOIN (SELECT DISTINCT ON (btrim(tecnico_responsavel, E' \t\r\n')) btrim(tecnico_responsavel, E' \t\r\n') AS tec, ultimo_supervisor FROM public.ranking_tecnicos ORDER BY btrim(tecnico_responsavel, E' \t\r\n'), total_de_visitas DESC NULLS LAST) k2 ON k2.tec = COALESCE(m.tecnico, v.tecnico);

-- Despesa direta por subgrupo: mesmas colunas de filtro da vw_resumo_leite_mensal + subgrupo e valor.
CREATE VIEW public.vw_despesa_subgrupo AS
SELECT w.id_propriedade, w.propriedade, w.tecnico, w.supervisor, w.projeto, w.municipio, w.regiao, w.sindicato, w.ativa, w.mes,
       d.subgrupo, d.valor
FROM public.vw_resumo_leite_mensal w
JOIN public.resumo_despesa_subgrupo d ON d.id_propriedade = w.id_propriedade AND d.mes = w.mes;

-- Receitas e despesas por tipo (aba "Receitas e despesas"): mesmas colunas de filtro da vw_resumo_leite_mensal.
CREATE VIEW public.vw_tipo AS
SELECT w.id_propriedade, w.propriedade, w.tecnico, w.supervisor, w.projeto, w.municipio, w.regiao, w.sindicato, w.ativa, w.mes,
       d.grupo, d.classe, d.subgrupo, d.valor
FROM public.vw_resumo_leite_mensal w
JOIN public.resumo_tipo d ON d.id_propriedade = w.id_propriedade AND d.mes = w.mes;

-- Mantém a permissão do usuário só de leitura (se ele já existir) depois que as views são recriadas.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'painel_leitura') THEN
    GRANT SELECT ON public.vw_propriedades, public.vw_resumo_leite_mensal, public.vw_despesa_subgrupo, public.vw_tipo TO painel_leitura;
  END IF;
END $$;
