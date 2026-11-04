"""Lista as visitas de uma propriedade (cadastro local) e onde cada uma esta no resumo mensal do painel.
Uso:  python scripts/visitas_da_propriedade.py 446027 [mes AAAA-MM]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
con = local(); cur = con.cursor()
pid = sys.argv[1]; mes = sys.argv[2] if len(sys.argv) > 2 else None
cur.execute("""SELECT id_visita, referencia_visita, numero_visita, ordem_visita, dt_visita, dt_exclusao_visita, visita_valida, projeto, tecnico_atual
  FROM public.sisateg_rel_listar_visita WHERE id_propriedade::text = %s AND (%s IS NULL OR referencia_visita = %s)
  ORDER BY referencia_visita DESC, id_visita::bigint""", (pid, mes, mes))
print("id_visita | referencia | numero | ordem | dt_visita | dt_exclusao | valida | projeto | tecnico")
for r in cur.fetchall(): print(" | ".join("" if x is None else str(x) for x in r))
cur.execute("""SELECT mes, id_visita, receita_bruta, despesa_direta, producao_leite_l FROM public.resumo_leite_mensal
  WHERE id_propriedade::text = %s AND (%s IS NULL OR mes::text LIKE %s) ORDER BY mes DESC LIMIT 12""", (pid, mes, (mes or "") + "%"))
print("\nno resumo do painel: mes | id_visita | receita | despesa | producao")
for r in cur.fetchall(): print(" | ".join("" if x is None else str(x) for x in r))
con.close()
