"""Quantas linhas de receita/despesa de LEITE existem por mes na FONTE do SisATeG (ODBC) e no banco LOCAL, de 2022-11 a 2023-12.
Mostra se a API tem 2024 e o que falta carregar. Uso:  python -u scripts/conferir_fonte_2024.py"""
import os, warnings
from pathlib import Path
import pandas as pd, pyodbc
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
warnings.filterwarnings("ignore")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True)
pg = create_engine(URL.create("postgresql+psycopg2", username=os.environ.get("LOCAL_DB_USER", "postgres"), password=os.environ["LOCAL_DB_PASS"],
                              host=os.environ.get("LOCAL_DB_HOST", "localhost"), port=int(os.environ.get("LOCAL_DB_PORT", "5432")),
                              database=os.environ.get("LOCAL_DB_NAME", "api_sisateg")))
meses = [f"2022-{m:02d}" for m in (11, 12)] + [f"2023-{m:02d}" for m in range(1, 13)]
for tb in ["sisateg_receita", "sisateg_despesa"]:
    print(f"\n=== {tb}: mes | linhas na FONTE | linhas no LOCAL ===", flush=True)
    for m in meses:
        ini = m + "-01"; y, mm = int(m[:4]), int(m[5:]); fim = f"{y + (mm == 12)}-{(mm % 12) + 1:02d}-01"
        q = f"SELECT COUNT(*) FROM {tb} WHERE atividade = 'BOVINOCULTURA DE LEITE' AND status_item = 'ATIVO' AND dt_referencia >= '{ini}' AND dt_referencia < '{fim}'"
        try: f = int(pd.read_sql(q, odbc).iloc[0, 0])
        except Exception as e: f = "ERRO " + str(e)[:60]
        l = int(pd.read_sql(q.replace("COUNT(*)", "COUNT(*)"), pg).iloc[0, 0])
        print(f"{m} | {f} | {l}", flush=True)
