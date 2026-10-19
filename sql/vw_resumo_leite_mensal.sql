-- RODAR NO SERVIDOR (banco painel_ateg). O script de cópia já roda este arquivo sozinho depois de copiar.
-- Supervisor OFICIAL = public.ranking_tecnicos.ultimo_supervisor (o mesmo do ranking).
-- O supervisor do SisATeG fica em supervisor_sisateg, só para conferência.
CREATE OR REPLACE VIEW public.vw_propriedades AS
SELECT p.id_propriedade, p.propriedade, p.produtor, p.tecnico,
       k.ultimo_supervisor AS supervisor, p.supervisor_sisateg,
       p.municipio, p.uf, p.area_total, p.area_produtiva,
       p.projeto, p.qtd_projetos, p.inicio_projeto, p.fim_projeto, p.status_vinculo, p.motivo_desativacao
FROM public.resumo_propriedades p
LEFT JOIN public.ranking_tecnicos k ON btrim(k.tecnico_responsavel, E' \t\r\n') = p.tecnico;

CREATE OR REPLACE VIEW public.vw_resumo_leite_mensal AS
SELECT v.*, m.mes, m.producao_leite_l, m.receita_bruta, m.despesa_direta,
       (m.receita_bruta - m.despesa_direta) AS margem_bruta
FROM public.vw_propriedades v
JOIN public.resumo_leite_mensal m ON m.id_propriedade = v.id_propriedade;

-- Mantém a permissão do usuário só de leitura (se ele já existir) depois que as views são recriadas.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'painel_leitura') THEN
    GRANT SELECT ON public.vw_propriedades, public.vw_resumo_leite_mensal TO painel_leitura;
  END IF;
END $$;
