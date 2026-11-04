"""Visitas "gemeas": mesma propriedade, mesmo mes de referencia e mesmo numero_visita (a mais antiga foi refeita no SisATeG com outro ID).
Lista as duas, marca qual fica (a de maior id_visita) e conta por mes. Uso:  python -u scripts/visitas_duplicadas.py > gemeas.txt"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
con = local(); cur = con.cursor()
cur.execute("""SELECT referencia_visita, id_propriedade, numero_visita, COUNT(*) n,
       string_agg(id_visita::text, ' , ' ORDER BY id_visita::bigint) ids, MAX(imovel) imovel
  FROM public.sisateg_rel_listar_visita
  WHERE atividade = 'BOVINOCULTURA DE LEITE' AND dt_exclusao_visita IS NULL AND referencia_visita >= '2024-06'
  GROUP BY 1, 2, 3 HAVING COUNT(*) > 1 ORDER BY 1, 2""")
rows = cur.fetchall()
por = {}
for r in rows: por[r[0]] = por.get(r[0], 0) + 1
print("=== Quantidade de propriedades com visitas gemeas, por mes ===")
for m in sorted(por): print(m, por[m])
print("\n=== Detalhe (mes | propriedade | numero_visita | ids (o ultimo é o que fica) | imovel) ===")
for r in rows: print(f"{r[0]} | {r[1]} | {r[2]} | {r[4]} | {r[5]}")
con.close()
