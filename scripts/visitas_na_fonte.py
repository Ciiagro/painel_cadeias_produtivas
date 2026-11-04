"""As visitas da planilha que faltam no cadastro local: como elas estao na FONTE SisATeG? Uso: python -u scripts/visitas_na_fonte.py "tabela (8).xlsx" """
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
import openpyxl, pyodbc, pandas as pd

ws = openpyxl.load_workbook(sys.argv[1]).active
rows = list(ws.iter_rows(values_only=True)); h = rows[0]; iv = h.index("ID Visita")
ids = [str(r[iv]).strip() for r in rows[1:] if r[iv] and str(r[iv]).strip().isdigit()]
con = local(); cur = con.cursor()
cur.execute("SELECT DISTINCT id_visita::text FROM public.sisateg_rel_listar_visita"); tem = {r[0] for r in cur.fetchall()}; con.close()
faltam = [i for i in ids if i not in tem]
print("Visitas da planilha:", len(ids), "| faltam no cadastro local:", len(faltam), flush=True)
odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True); oc = odbc.cursor()
out = []
for k in range(0, len(faltam), 200):
    lote = ",".join(faltam[k:k + 200])
    oc.execute(f"SELECT id_visita, id_propriedade, dt_visita, referencia_visita, atividade, visita_valida, dt_exclusao_visita FROM sisateg_rel_listar_visita WHERE id_visita IN ({lote})")
    out += [tuple(r) for r in oc.fetchall()]
    print(f"  consultadas {min(k + 200, len(faltam))}/{len(faltam)} -> achadas {len(out)}", flush=True)
df = pd.DataFrame(out, columns=["id_visita", "id_propriedade", "dt_visita", "referencia", "atividade", "valida", "dt_exclusao"])
print("\nAchadas na FONTE (tabela de visitas):", len(df), "de", len(faltam))
if len(df):
    print("\n=== por referencia ==="); print(df.groupby("referencia", dropna=False).size().to_string())
    print("\n=== dt_visita vazia? ==="); print(df["dt_visita"].isna().value_counts().to_string())
    d = pd.to_datetime(df["dt_visita"], errors="coerce")
    print("\n=== por mes da dt_visita ==="); print(d.dt.strftime("%Y-%m").value_counts(dropna=False).sort_index().to_string())
    print("\n=== validade ==="); print(df["valida"].value_counts(dropna=False).to_string())
    print("\n=== excluida? ==="); print(df["dt_exclusao"].notna().value_counts().to_string())
