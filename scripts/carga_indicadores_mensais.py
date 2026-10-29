"""
Carga COMPLETA (tudo ou nada) das tabelas de indicador mensal do SisATeG (ODBC DSN) -> banco local api_sisateg:
  sisateg_rel_indicador_padrao_mensal   (nome da propriedade usado no resumo)
  sisateg_rel_indicador_leite_mensal    (renda_bruta_leite, usada na conferência com o SisATeG)

Lê a tabela inteira da origem e, numa única transação, esvazia o destino (TRUNCATE, sem CASCADE, para não apagar
outras tabelas por engano) e insere. Se algo falhar, a tabela local continua como estava.
A senha vem do .env (LOCAL_DB_*), não fica escrita aqui.

Uso:  python scripts/carga_indicadores_mensais.py            (as duas tabelas)
      python scripts/carga_indicadores_mensais.py sisateg_rel_indicador_padrao_mensal
"""
import os
import sys
import warnings
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

warnings.filterwarnings("ignore", category=UserWarning)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
TABELAS = ["sisateg_rel_indicador_padrao_mensal", "sisateg_rel_indicador_leite_mensal"]


def main():
    alvo = sys.argv[1:] or TABELAS
    if any(t not in TABELAS for t in alvo):
        sys.exit(f"Tabela não prevista. Use: {', '.join(TABELAS)}")
    if not os.environ.get("LOCAL_DB_PASS"):
        sys.exit("Falta LOCAL_DB_PASS no arquivo .env")
    pg = create_engine(URL.create(
        "postgresql+psycopg2", username=os.environ.get("LOCAL_DB_USER", "postgres"), password=os.environ["LOCAL_DB_PASS"],
        host=os.environ.get("LOCAL_DB_HOST", "localhost"), port=int(os.environ.get("LOCAL_DB_PORT", "5432")),
        database=os.environ.get("LOCAL_DB_NAME", "api_sisateg")))
    odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True)
    erros = 0
    try:
        for t in alvo:
            try:
                print(f"\n== {t}: lendo tudo da API...", flush=True)
                df = pd.read_sql(f"SELECT * FROM {t}", odbc)
                print(f"   {len(df)} linhas lidas.")
                if df.empty:
                    print("   origem vazia: nada foi alterado.")
                    continue
                existe = inspect(pg).has_table(t)
                with pg.begin() as con:   # tudo ou nada
                    if existe:
                        antes = con.execute(text(f'SELECT COUNT(*) FROM public."{t}"')).scalar()
                        if antes and len(df) < 0.5 * antes:
                            raise RuntimeError(f"TRAVA: a API devolveu {len(df)} linhas e o banco tem {antes}; nada foi trocado")
                        con.execute(text(f'TRUNCATE TABLE public."{t}"'))
                    df.to_sql(t, con=con, if_exists="append", index=False, chunksize=5000)
                print(f"   atualizada ({len(df)} linhas).")
            except Exception as e:
                erros += 1
                print(f"   ERRO em {t}: {e}\n   (a tabela local ficou como estava)")
    finally:
        odbc.close()
        pg.dispose()
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
