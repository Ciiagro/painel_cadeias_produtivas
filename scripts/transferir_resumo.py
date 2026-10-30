"""
Copia public.resumo_leite_mensal do PostgreSQL LOCAL (api_sisateg) para o servidor PÚBLICO (painel_ateg),
substituindo a tabela inteira (tudo ou nada: se der erro, a tabela antiga do servidor continua).

Configuração: arquivo .env na pasta do projeto (NÃO vai para o Git). Veja .env.example.
Instalar uma vez:   pip install pandas sqlalchemy psycopg2-binary python-dotenv
Rodar (na pasta do projeto):   python scripts\\transferir_resumo.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ESQUEMA = "public"


def eng(prefixo, padrao_host=None, padrao_porta="5432"):
    senha = os.environ.get(f"{prefixo}_DB_PASS")
    nome = os.environ.get(f"{prefixo}_DB_NAME")
    if not senha or not nome:
        sys.exit(f"Faltam {prefixo}_DB_PASS e/ou {prefixo}_DB_NAME no arquivo .env")
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ.get(f"{prefixo}_DB_USER", "postgres"),
        password=senha,
        host=os.environ.get(f"{prefixo}_DB_HOST", padrao_host),
        port=int(os.environ.get(f"{prefixo}_DB_PORT", padrao_porta)),
        database=nome,
    )
    return create_engine(url)


def copiar(origem, con, tabela, indices, permite_vazia=False):
    df = pd.read_sql(f"SELECT * FROM {ESQUEMA}.{tabela}", origem)
    print(f"{tabela}: lidas {len(df)} linhas do banco local.")
    if df.empty and not permite_vazia:
        sys.exit(f"{tabela} vazia no local: nada foi copiado.")
    tmp = f"{tabela}_novo"
    df.to_sql(tmp, con, schema=ESQUEMA, if_exists="replace", index=False, chunksize=2000, method="multi")
    con.execute(text(f'DROP TABLE IF EXISTS "{ESQUEMA}"."{tabela}" CASCADE'))
    con.execute(text(f'ALTER TABLE "{ESQUEMA}"."{tmp}" RENAME TO "{tabela}"'))
    for col in indices:
        con.execute(text(f'CREATE INDEX ON "{ESQUEMA}"."{tabela}" ({col})'))


def main():
    origem = eng("LOCAL", padrao_host="localhost")
    destino = eng("REMOTE")
    sql = (Path(__file__).resolve().parent.parent / "sql" / "vw_resumo_leite_mensal.sql").read_text(encoding="utf-8")
    # TUDO numa única transação: tabelas novas + views. Se qualquer parte falhar, o servidor fica exatamente como estava
    # (antes as views eram recriadas depois, e uma falha deixava o painel sem views).
    with destino.begin() as con:
        copiar(origem, con, "resumo_propriedades", ["id_propriedade", "tecnico"])
        copiar(origem, con, "resumo_leite_mensal", ["id_propriedade", "mes"])
        copiar(origem, con, "resumo_despesa_subgrupo", ["id_propriedade", "mes"])
        copiar(origem, con, "resumo_tipo", ["id_propriedade", "mes"])
        copiar(origem, con, "resumo_leite_revisar", ["id_propriedade"], permite_vazia=True)
        con.exec_driver_sql(sql.replace("%", "%%"))
    print("Copia concluida e views recriadas no servidor.")


if __name__ == "__main__":
    main()
