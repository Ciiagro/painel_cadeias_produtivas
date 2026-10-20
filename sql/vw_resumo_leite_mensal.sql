-- RODAR NO SERVIDOR (banco painel_ateg). O script de cópia já roda este arquivo sozinho depois de copiar.
-- Supervisor OFICIAL = public.ranking_tecnicos.ultimo_supervisor (o mesmo do ranking).
-- O supervisor do SisATeG fica em supervisor_sisateg, só para conferência.
DROP VIEW IF EXISTS public.vw_despesa_subgrupo;
DROP VIEW IF EXISTS public.vw_resumo_leite_mensal;
DROP VIEW IF EXISTS public.vw_propriedades CASCADE;
CREATE VIEW public.vw_propriedades AS
SELECT p.id_propriedade, p.propriedade, p.produtor, p.tecnico,
       k.ultimo_supervisor AS supervisor, p.supervisor_sisateg,
       p.municipio, p.uf, p.area_total, p.area_produtiva,
       p.projeto, p.qtd_projetos, p.inicio_projeto, p.fim_projeto, p.status_vinculo, p.motivo_desativacao, p.ativa
FROM public.resumo_propriedades p
LEFT JOIN public.ranking_tecnicos k ON btrim(k.tecnico_responsavel, E' \t\r\n') = p.tecnico;

-- Mensal: o técnico e o supervisor são os da ÉPOCA (da visita do mês); se faltar, usa o da propriedade.
CREATE VIEW public.vw_resumo_leite_mensal AS
SELECT v.id_propriedade, v.propriedade, v.produtor,
       COALESCE(m.tecnico, v.tecnico) AS tecnico,
       COALESCE(k2.ultimo_supervisor, v.supervisor) AS supervisor,
       v.supervisor_sisateg, v.municipio, v.uf, v.area_total, v.area_produtiva,
       v.projeto, v.qtd_projetos, v.inicio_projeto, v.fim_projeto, v.status_vinculo, v.motivo_desativacao, v.ativa,
       m.mes, m.producao_leite_l, m.leite_vendido_l, m.venda_leite_rs, m.receita_bruta, m.despesa_direta,
       (m.receita_bruta - m.despesa_direta) AS margem_bruta
FROM public.vw_propriedades v
JOIN public.resumo_leite_mensal m ON m.id_propriedade = v.id_propriedade
LEFT JOIN public.ranking_tecnicos k2 ON btrim(k2.tecnico_responsavel, E' \t\r\n') = COALESCE(m.tecnico, v.tecnico);

-- Despesa direta por subgrupo: mesmas colunas de filtro da vw_resumo_leite_mensal + subgrupo e valor.
CREATE VIEW public.vw_despesa_subgrupo AS
SELECT w.id_propriedade, w.propriedade, w.tecnico, w.supervisor, w.projeto, w.municipio, w.ativa, w.mes,
       d.subgrupo, d.valor
FROM public.vw_resumo_leite_mensal w
JOIN public.resumo_despesa_subgrupo d ON d.id_propriedade = w.id_propriedade AND d.mes = w.mes;

-- Mantém a permissão do usuário só de leitura (se ele já existir) depois que as views são recriadas.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'painel_leitura') THEN
    GRANT SELECT ON public.vw_propriedades, public.vw_resumo_leite_mensal, public.vw_despesa_subgrupo TO painel_leitura;
  END IF;
END $$;
