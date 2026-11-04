"""Conta linhas por mes (dt_referencia) nas tabelas brutas: LOCAL x FONTE SisATeG.
Uso:  python scripts/contar_mes.py            (ultimos 6 meses)"""
import os, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402

hoje = date.today()
meses = []
a, m = hoje.year, hoje.month
for _ in range(6):
    meses.append((date(a, m, 1), date(a + (m == 12), m % 12 + 1, 1)))
    m -= 1
    if m == 0:
        a, m = a - 1, 12
meses.reverse()
import pyodbc
odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True)
c = odbc.cursor()
con = local(); cur = con.cursor()
print("tabela | mes | local | fonte")
for t in ["sisateg_receita", "sisateg_despesa"]:
    for i, f in meses:
        cur.execute(f"SELECT COUNT(*) FROM public.{t} WHERE dt_referencia >= %s AND dt_referencia < %s", (i, f))
        l = cur.fetchone()[0]
        try:
            c.execute(f"SELECT COUNT(*) FROM {t} WHERE dt_referencia >= '{i}' AND dt_referencia < '{f}'")
            s = c.fetchone()[0]
        except Exception as e:
            s = "ERRO " + str(e)[:60]
        print(f"{t} | {i:%Y-%m} | {l} | {s}")
