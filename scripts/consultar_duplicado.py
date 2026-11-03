"""Mostra, na FONTE do SisATeG (ODBC), as linhas de 'Venda de leite in natura' de uma ou mais visitas com os IDENTIFICADORES e as datas de cada linha.
Serve para saber se a linha repetida e a MESMA entrada (duplicada pela fonte) ou DUAS entradas diferentes (dois lancamentos reais).
Uso:  python scripts/consultar_duplicado.py 10064388 10038259"""
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
    sys.exit("Informe o(s) id(s) da visita. Ex.: python scripts/consultar_duplicado.py 10064388")
odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True)
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)
f = pd.read_sql(f"SELECT * FROM sisateg_receita WHERE id_visita IN ({','.join(ids)}) AND id_item = 1457", odbc)
cols = [c for c in ("id_visita", "id_item_visita", "id_item_visita_principal", "tipo_valor", "valor", "dt_referencia", "dt_inclusao_item", "dt_alteracao_item", "status_item", "@timestamp") if c in f.columns]
f = f.sort_values([c for c in ("id_visita", "tipo_valor", "id_item_visita") if c in f.columns])
print(f[cols].to_string(index=False))
try:   # arquivo para entregar ao tecnico: uma linha por lancamento de leite, com os numeros das linhas
    saida = Path(__file__).resolve().parent.parent / "linhas_repetidas_leite.xlsx"
    f[cols].to_excel(saida, index=False)
    print(f"\nArquivo gerado: {saida}")
except Exception as e:
    print("Nao consegui gerar o Excel:", e)
print("\nSe a coluna id_item_visita tiver o MESMO numero nas duas linhas, e a mesma entrada repetida pela fonte.")
print("Se tiver numeros DIFERENTES (e datas de inclusao diferentes), sao dois lancamentos feitos pelo tecnico.")
odbc.close()
