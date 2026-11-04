"""Mostra TODAS as colunas do cadastro de visitas (banco local) para uma ou mais visitas e para as outras visitas da mesma propriedade no mesmo mes.
Uso:  python scripts/ver_visita_cadastro.py 7262463 9727380"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
con = local(); cur = con.cursor()
ids = [a for a in sys.argv[1:] if a.isdigit()]
cur.execute("SELECT * FROM public.sisateg_rel_listar_visita WHERE id_visita::text = ANY(%s) ORDER BY id_visita::bigint", (ids,))
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print("\n--- visita", r[cols.index("id_visita")], "---")
    for c, v in zip(cols, r):
        if v is not None and str(v).strip() != "": print(f"  {c}: {v}")
con.close()
