"""Por que o painel mostra mais propriedades ativas do que o SisATeG. Uso: python scripts/analise_ativas.py [YYYY-MM]  (padrao: 2026-10)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402

mes = sys.argv[1] if len(sys.argv) > 1 else "2026-10"
con = local(); cur = con.cursor()

def q(titulo, sql, params=None):
    print(f"\n=== {titulo} ===")
    try:
        cur.execute(sql, params) if params else cur.execute(sql)
        cols = [d[0] for d in cur.description]
        print(" | ".join(cols))
        for r in cur.fetchall():
            print(" | ".join("" if v is None else str(v) for v in r))
    except Exception as e:
        con.rollback(); print("ERRO:", str(e).splitlines()[0])

q("1) Painel: propriedades ATIVAS (card)", "SELECT COUNT(DISTINCT id_propriedade) AS ativas FROM public.resumo_propriedades WHERE ativa")
q("2) Ativas por projeto", "SELECT projeto, COUNT(*) n FROM public.resumo_propriedades WHERE ativa GROUP BY 1 ORDER BY 2 DESC")
q("3) Ativas por situacao do vinculo", "SELECT status_vinculo, COUNT(*) n FROM public.resumo_propriedades WHERE ativa GROUP BY 1 ORDER BY 2 DESC")
q("4) Ativas por ano do FIM do vinculo (fim_projeto)", "SELECT COALESCE(to_char(fim_projeto,'YYYY'),'sem fim') ano_fim, COUNT(*) n FROM public.resumo_propriedades WHERE ativa GROUP BY 1 ORDER BY 1")
q(f"5) Ativas com fim do projeto ANTES de {mes}-01", "SELECT COUNT(*) n FROM public.resumo_propriedades WHERE ativa AND fim_projeto < (%s || '-01')::date", (mes,))
q(f"6) Ativas com inicio do projeto DEPOIS de {mes}-30", "SELECT COUNT(*) n FROM public.resumo_propriedades WHERE ativa AND inicio_projeto > (%s || '-01')::date + 31", (mes,))
q(f"7) Ativas com visita (nao excluida) em {mes}", """SELECT COUNT(DISTINCT p.id_propriedade) n FROM public.resumo_propriedades p
   JOIN public.sisateg_rel_listar_visita v ON v.id_propriedade::text = p.id_propriedade::text
   WHERE p.ativa AND v.referencia_visita = %s AND v.dt_exclusao_visita IS NULL""", (mes,))
q(f"8) Ativas SEM visita em {mes}", """SELECT COUNT(*) n FROM public.resumo_propriedades p WHERE p.ativa AND NOT EXISTS (
   SELECT 1 FROM public.sisateg_rel_listar_visita v WHERE v.id_propriedade::text = p.id_propriedade::text
   AND v.referencia_visita = %s AND v.dt_exclusao_visita IS NULL)""", (mes,))
q(f"9) Ativas SEM visita em {mes}, por projeto", """SELECT p.projeto, COUNT(*) n FROM public.resumo_propriedades p WHERE p.ativa AND NOT EXISTS (
   SELECT 1 FROM public.sisateg_rel_listar_visita v WHERE v.id_propriedade::text = p.id_propriedade::text
   AND v.referencia_visita = %s AND v.dt_exclusao_visita IS NULL) GROUP BY 1 ORDER BY 2 DESC""", (mes,))
q("10) Tabela de origem propriedades_ativas_na_ateg", "SELECT COUNT(*) linhas, COUNT(DISTINCT id_propriedade) propriedades FROM public.propriedades_ativas_na_ateg")
con.close()
