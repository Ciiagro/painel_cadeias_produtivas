"""Onde as linhas de uma visita existem: banco LOCAL (3 tabelas) e FONTE SisATeG (ODBC).
Uso:  python scripts/consultar_origem.py 10224780 10165758"""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402

ids = [a for a in sys.argv[1:] if a.isdigit()]
if not ids:
    sys.exit("Informe o(s) id(s) da visita.")
lista = ",".join(repr(i) for i in ids)
TABELAS = ["sisateg_receita_despesa", "sisateg_receita", "sisateg_despesa"]


def mostra(titulo, cols, rows):
    print(f"\n=== {titulo} ===")
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join("" if v is None else str(v) for v in r))
    if not rows:
        print("(nenhuma linha)")


con = local()
cur = con.cursor()
for t in TABELAS:
    try:
        cur.execute(f"SELECT id_visita, MIN(dt_referencia), MAX(dt_referencia), COUNT(*) FROM public.{t} WHERE id_visita::text IN ({lista}) GROUP BY 1 ORDER BY 1")
        mostra(f"LOCAL {t}", ["id_visita", "dt_ref_min", "dt_ref_max", "linhas"], cur.fetchall())
    except Exception as e:
        con.rollback()
        print(f"\n=== LOCAL {t} === ERRO:", str(e).splitlines()[0])
con.close()

try:
    import pyodbc
    odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True)
    c = odbc.cursor()
    for t in TABELAS:
        try:
            c.execute(f"SELECT id_visita, MIN(dt_referencia), MAX(dt_referencia), COUNT(*) FROM {t} WHERE id_visita IN ({lista}) GROUP BY id_visita ORDER BY id_visita")
            rows = c.fetchall()
            mostra(f"FONTE SisATeG {t}", ["id_visita", "dt_ref_min", "dt_ref_max", "linhas"], rows)
        except Exception as e:
            print(f"\n=== FONTE {t} === ERRO:", str(e)[:200])
    odbc.close()
except Exception as e:
    print("\nNao consegui abrir a fonte (ODBC):", str(e)[:200])
