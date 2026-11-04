"""Mostra, na FONTE do SisATeG (ODBC), QUANDO cada lancamento foi criado/alterado e o status da visita, so dos itens que mais pesam (leite e despesas).
Uso:  python scripts/consultar_datas.py 9727377 9723757 9288174"""
import os
import sys
import warnings
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
ids = [a for a in sys.argv[1:] if a.isdigit()]
if not ids:
    sys.exit("Informe o(s) id(s) da visita.")
odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True)
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 400)
pd.set_option("display.max_colwidth", 40)
for tabela in ("sisateg_receita", "sisateg_despesa"):
    f = pd.read_sql(f"SELECT * FROM {tabela} WHERE id_visita IN ({','.join(ids)}) AND status_item = 'ATIVO' AND tipo_registro = 'PRINCIPAL'", odbc)
    cols = [c for c in ("id_visita", "status_visita", "item", "tipo_valor", "valor", "id_item_visita", "dt_inclusao_item", "dt_alteracao_item") if c in f.columns]
    print(f"\n=== {tabela}: {len(f)} linhas ATIVAS (as mais recentemente alteradas primeiro) ===")
    f = f[f["tipo_valor"].isin(["QUANTIDADE", "VALOR_UNITARIO"])]
    print(f[cols].sort_values(["id_visita", "dt_alteracao_item"], ascending=[True, False]).groupby("id_visita").head(14).to_string(index=False))
odbc.close()
