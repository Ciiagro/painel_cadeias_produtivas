"""Propriedades de LEITE com visita (nao excluida) por mes de referencia. Compara com a planilha do SisATeG (set=1802, out=1641). Uso: python -u scripts/contar_props_visita_mes.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
con = local(); cur = con.cursor()
def q(t, sql):
    print(f"\n=== {t} ===", flush=True); cur.execute(sql)
    print(" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall(): print(" | ".join("" if x is None else str(x) for x in r))
q("1) Propriedades de leite com visita, por referencia (todas)", """SELECT referencia_visita mes, COUNT(DISTINCT id_propriedade) propriedades, COUNT(DISTINCT id_visita) visitas
  FROM public.sisateg_rel_listar_visita WHERE atividade = 'BOVINOCULTURA DE LEITE' AND dt_exclusao_visita IS NULL AND referencia_visita >= '2026-01' AND referencia_visita <= '2026-10'
  GROUP BY 1 ORDER BY 1""")
q("2) Mesmo, so propriedades que estao ATIVAS hoje no painel", """SELECT v.referencia_visita mes, COUNT(DISTINCT v.id_propriedade) propriedades_ativas
  FROM public.sisateg_rel_listar_visita v JOIN public.resumo_propriedades p ON p.id_propriedade::text = v.id_propriedade::text AND p.ativa
  WHERE v.atividade = 'BOVINOCULTURA DE LEITE' AND v.dt_exclusao_visita IS NULL AND v.referencia_visita >= '2026-01' AND v.referencia_visita <= '2026-10'
  GROUP BY 1 ORDER BY 1""")
con.close()
