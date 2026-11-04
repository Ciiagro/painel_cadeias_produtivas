"""As visitas da planilha que o cadastro de leite nao tem: existem com outra atividade/exclusao? Uso: python -u scripts/achar_visitas_planilha.py "tabela (8).xlsx" """
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
import openpyxl, pandas as pd

ws = openpyxl.load_workbook(sys.argv[1]).active
rows = list(ws.iter_rows(values_only=True)); h = rows[0]
iv, ip = h.index("ID Visita"), h.index("ID Propriedade")
ids = [str(r[iv]).strip() for r in rows[1:] if r[iv] and str(r[iv]).strip().isdigit()]
print("Visitas na planilha:", len(ids), "| menor id:", min(map(int, ids)), "| maior id:", max(map(int, ids)), flush=True)
con = local(); cur = con.cursor(); cur.execute("SET statement_timeout = 120000")
cur.execute("CREATE TEMP TABLE pl (idv text)")
cur.executemany("INSERT INTO pl VALUES (%s)", [(i,) for i in ids])
def q(t, sql):
    print(f"\n=== {t} ===", flush=True); cur.execute(sql)
    print(" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall(): print(" | ".join("" if x is None else str(x) for x in r))
q("1) Quantas dessas visitas existem no cadastro (qualquer atividade, excluida ou nao)",
  "SELECT COUNT(*) FILTER (WHERE v.id_visita IS NOT NULL) no_cadastro, COUNT(*) FILTER (WHERE v.id_visita IS NULL) fora_do_cadastro FROM pl LEFT JOIN (SELECT DISTINCT id_visita::text id_visita FROM public.sisateg_rel_listar_visita) v ON v.id_visita = pl.idv")
q("2) As que existem: atividade e se foi excluida",
  "SELECT v.atividade, (v.dt_exclusao_visita IS NOT NULL) excluida, v.referencia_visita ref, COUNT(*) n FROM pl JOIN public.sisateg_rel_listar_visita v ON v.id_visita::text = pl.idv GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 15")
q("3) Faixa de IDs de visita no cadastro, por referencia (para ver se faltam ids)",
  "SELECT referencia_visita ref, MIN(id_visita::bigint) menor, MAX(id_visita::bigint) maior, COUNT(*) n FROM public.sisateg_rel_listar_visita WHERE referencia_visita >= '2026-08' GROUP BY 1 ORDER BY 1")
q("4) Visitas da planilha fora do cadastro: faixa de ids", "SELECT MIN(idv::bigint) menor, MAX(idv::bigint) maior, COUNT(*) n FROM pl WHERE idv NOT IN (SELECT id_visita::text FROM public.sisateg_rel_listar_visita)")
con.close()
