"""Lista as propriedades que estao na planilha mensal do SisATeG e NAO entram na contagem do painel naquele mes.
Uso:  python scripts/propriedades_fora_do_painel.py "BOVINO_03_2026_1.xlsx" 2026-03
Gera: fora_do_painel_AAAA-MM.xlsx (nesta pasta)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
import openpyxl, pandas as pd

if len(sys.argv) < 3:
    sys.exit('Uso: python scripts/propriedades_fora_do_painel.py "planilha.xlsx" 2026-03')
arq, mes = sys.argv[1], sys.argv[2]
ws = openpyxl.load_workbook(arq).active
rows = list(ws.iter_rows(values_only=True)); h = rows[0]
ip, iv, ipr, iat = h.index("ID Propriedade"), h.index("ID Visita"), h.index("Propriedade"), h.index("Ativa?")
iproj = h.index("Projeto")
plan = {}
for r in rows[1:]:
    if r[ip] and str(r[ip]).strip().isdigit():
        plan[str(r[ip]).strip()] = (r[ipr], r[iproj], r[iat], str(r[iv]).strip())
print(f"Propriedades na planilha: {len(plan)}", flush=True)
con = local(); cur = con.cursor()
cur.execute("SET statement_timeout = 120000")
cur.execute("SELECT id_propriedade::text FROM public.resumo_propriedade_mes WHERE mes = %s", (mes,))
painel = {x[0] for x in cur.fetchall()}
print(f"Propriedades do painel em {mes}: {len(painel)}", flush=True)
fora = [k for k in plan if k not in painel]
print(f"Na planilha e fora do painel: {len(fora)}", flush=True)
cur.execute("SELECT id_propriedade::text FROM public.resumo_propriedades")
em_resumo = {x[0] for x in cur.fetchall()}
out = []
for k in fora:
    nome, proj, ativa, idv = plan[k]
    cur.execute("""SELECT atividade, referencia_visita, dt_exclusao_visita, visita_valida, status_propriedade
                   FROM public.sisateg_rel_listar_visita WHERE id_propriedade::text = %s AND id_visita::text = %s LIMIT 1""", (k, idv))
    v = cur.fetchone()
    out.append(dict(id=k, propriedade=nome, projeto=proj, ativa=ativa, id_visita=idv,
                    esta_no_resumo_propriedades=k in em_resumo,
                    visita_no_banco=bool(v), atividade=v[0] if v else None, referencia=v[1] if v else None,
                    visita_excluida=(v[2] is not None) if v else None, visita_valida=v[3] if v else None, status=v[4] if v else None))
con.close()
df = pd.DataFrame(out)
print(df.to_string(index=False))
df.to_excel(f"fora_do_painel_{mes}.xlsx", index=False)
print(f"\nArquivo gerado: fora_do_painel_{mes}.xlsx")
