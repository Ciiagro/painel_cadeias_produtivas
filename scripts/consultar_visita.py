"""Mostra TUDO o que a FONTE do SisATeG (ODBC) tem para uma ou mais visitas, para comparar com o banco local.
Uso:  python scripts\\consultar_visita.py 9395327 9723758
Mostra, para cada visita, os itens de despesa e receita na fonte e quantos itens o banco local tem."""
import os
import sys
import warnings
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

warnings.filterwarnings("ignore")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
ids = [a for a in sys.argv[1:] if a.isdigit()]
if not ids:
    sys.exit("Informe o(s) id(s) da visita. Ex.: python scripts\\consultar_visita.py 9395327")
lista = ",".join(ids)

odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True)
pg = create_engine(URL.create("postgresql+psycopg2", username=os.environ.get("LOCAL_DB_USER", "postgres"), password=os.environ["LOCAL_DB_PASS"],
                              host=os.environ.get("LOCAL_DB_HOST", "localhost"), port=int(os.environ.get("LOCAL_DB_PORT", "5432")),
                              database=os.environ.get("LOCAL_DB_NAME", "api_sisateg")))
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 500)
pd.set_option("display.max_colwidth", 45)
CAND = ["id_visita", "status_item", "tipo_registro", "grupo", "subgrupo", "item", "tipo_valor", "id_item", "dt_referencia", "valor"]

for tabela in ("sisateg_despesa", "sisateg_receita"):
    print(f"\n================ FONTE (ODBC): {tabela} ================")
    f = pd.read_sql(f"SELECT * FROM {tabela} WHERE id_visita IN ({lista})", odbc)
    cols = [c for c in CAND if c in f.columns]
    print(f"{len(f)} linhas na fonte | colunas: {', '.join(f.columns)}")
    if len(f):
        print(f[cols].sort_values([c for c in ("id_visita", "grupo", "item", "tipo_valor") if c in cols]).to_string(index=False))
    loc = pd.read_sql(f"SELECT COUNT(*) AS n FROM public.{tabela} WHERE id_visita IN ({lista})", pg)
    print(f"--> linhas no banco LOCAL ({tabela}): {int(loc['n'][0])}")
odbc.close()
