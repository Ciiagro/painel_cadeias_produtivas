"""
Carga do SisATeG (ODBC/DSN) -> PostgreSQL local, com JANELA MÓVEL e troca segura.

Por que: a carga antiga começava da maior dt_referencia já salva. Lançamentos digitados depois com data
antiga (ou uma carga interrompida no meio) ficavam de fora para sempre. Aqui, a cada execução, recarregamos
os últimos N dias inteiros: lê tudo da janela numa tabela temporária e SÓ DEPOIS (numa única transação)
apaga a janela da tabela final e insere. Se der erro antes, a tabela final fica intacta.

Uso (Git Bash, na pasta do projeto):
    python scripts/carga_incremental.py sisateg_receita_despesa
    python scripts/carga_incremental.py sisateg_receita_despesa --dias 200
    python scripts/carga_incremental.py sisateg_receita_despesa --desde 2026-07-01   # carga mínima desde a data

.env (LOCAL_DB_HOST/PORT/NAME/USER/PASS, igual ao transferir_resumo.py). DSN do ODBC: variavel ODBC_DSN (padrão SISATEG).
Instalar: pip install pandas sqlalchemy psycopg2-binary pyodbc python-dotenv
"""
import argparse
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
COLUNA_DATA = "dt_referencia"
CHUNK = 5000


def engine_local():
    senha = os.environ.get("LOCAL_DB_PASS")
    nome = os.environ.get("LOCAL_DB_NAME", "api_sisateg")
    if not senha:
        sys.exit("Falta LOCAL_DB_PASS no arquivo .env")
    return create_engine(URL.create(
        "postgresql+psycopg2", username=os.environ.get("LOCAL_DB_USER", "postgres"), password=senha,
        host=os.environ.get("LOCAL_DB_HOST", "localhost"), port=int(os.environ.get("LOCAL_DB_PORT", "5432")),
        database=nome))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tabela")
    ap.add_argument("--dias", type=int, default=120, help="janela móvel em dias (padrão 120)")
    ap.add_argument("--desde", help="YYYY-MM-DD: sobrescreve a janela")
    a = ap.parse_args()
    if not a.tabela.replace("_", "").isalnum():
        sys.exit("nome de tabela inválido")

    t0 = time.time()
    ini = a.desde or (date.today() - timedelta(days=a.dias)).replace(day=1).isoformat()  # começa no dia 1 do mês
    fim = (date.today() + timedelta(days=1)).isoformat()
    tmp = f"{a.tabela}__carga_tmp"
    print(f"Tabela {a.tabela}: recarregando {COLUNA_DATA} de {ini} até {fim}")

    pg = engine_local()
    odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True)

    # 1) lê TUDO da janela para uma tabela temporária (a final ainda não é tocada)
    with pg.begin() as con:
        con.execute(text(f'DROP TABLE IF EXISTS "{tmp}"'))
    total = 0
    q = f"SELECT * FROM {a.tabela} WHERE {COLUNA_DATA} >= '{ini}' AND {COLUNA_DATA} < '{fim}'"
    for i, chunk in enumerate(pd.read_sql(q, odbc, chunksize=CHUNK), 1):
        chunk.to_sql(tmp, pg, if_exists="append", index=False, method="multi", chunksize=1000)
        total += len(chunk)
        print(f"  bloco {i}: {total} linhas lidas")
    odbc.close()
    if total == 0:
        with pg.begin() as con:
            con.execute(text(f'DROP TABLE IF EXISTS "{tmp}"'))
        sys.exit("A API não devolveu nada na janela: tabela final mantida sem alteração.")

    # 2) troca atômica: apaga a janela da final e insere o que veio (tudo ou nada)
    cols = ", ".join(f'"{c}"' for c in pd.read_sql(f'SELECT * FROM "{tmp}" LIMIT 0', pg).columns)
    with pg.begin() as con:
        existe = con.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{a.tabela}"}).scalar()
        if existe:
            apagadas = con.execute(text(f'DELETE FROM "{a.tabela}" WHERE {COLUNA_DATA} >= :i'), {"i": ini}).rowcount
            con.execute(text(f'INSERT INTO "{a.tabela}" ({cols}) SELECT {cols} FROM "{tmp}"'))
            con.execute(text(f'DROP TABLE "{tmp}"'))
            print(f"Janela trocada: {apagadas} linhas antigas -> {total} novas.")
        else:
            con.execute(text(f'ALTER TABLE "{tmp}" RENAME TO "{a.tabela}"'))
            print(f"Tabela criada com {total} linhas.")
    pg.dispose()
    print(f"Concluído em {int(time.time() - t0)} s.")


if __name__ == "__main__":
    main()
