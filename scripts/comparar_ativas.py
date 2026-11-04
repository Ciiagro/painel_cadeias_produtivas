"""Compara as tabelas de 'ativas' do banco LOCAL com a FONTE SisATeG. Uso: python scripts/comparar_ativas.py"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
import pyodbc

con = local(); cur = con.cursor()
odbc = pyodbc.connect(f"DSN={os.environ.get('ODBC_DSN', 'SISATEG')}", autocommit=True); oc = odbc.cursor()

def L(t, sql):
    print(f"\n=== LOCAL: {t} ===")
    try:
        cur.execute(sql); print(" | ".join(d[0] for d in cur.description))
        for r in cur.fetchall(): print(" | ".join("" if v is None else str(v) for v in r))
    except Exception as e:
        con.rollback(); print("ERRO:", str(e).splitlines()[0])

def F(t, sql):
    print(f"\n=== FONTE: {t} ===")
    try:
        oc.execute(sql); print(" | ".join(d[0] for d in oc.description))
        for r in oc.fetchall(): print(" | ".join("" if v is None else str(v) for v in r))
    except Exception as e:
        print("ERRO:", str(e)[:160])

L("vinculos de leite ATIVOS (propriedades)", "SELECT COUNT(DISTINCT id_propriedade) n FROM public.sisateg_vinculo_propriedade WHERE atividade ILIKE '%LEITE%' AND UPPER(status_vinculo)='ATIVO'")
F("vinculos de leite ATIVOS (propriedades)", "SELECT COUNT(DISTINCT id_propriedade) n FROM sisateg_vinculo_propriedade WHERE atividade LIKE '%LEITE%' AND status_vinculo = 'ATIVO'")
L("vinculos por situacao", "SELECT status_vinculo, COUNT(DISTINCT id_propriedade) n FROM public.sisateg_vinculo_propriedade WHERE atividade ILIKE '%LEITE%' GROUP BY 1")
F("vinculos por situacao", "SELECT status_vinculo, COUNT(DISTINCT id_propriedade) n FROM sisateg_vinculo_propriedade WHERE atividade LIKE '%LEITE%' GROUP BY status_vinculo")
L("propriedades_ativas_na_ateg", "SELECT COUNT(DISTINCT id_propriedade) n FROM public.propriedades_ativas_na_ateg")
F("propriedades_ativas_na_ateg", "SELECT COUNT(DISTINCT id_propriedade) n FROM propriedades_ativas_na_ateg")
L("data mais recente no vinculo (local)", "SELECT MAX(\"@timestamp\") ts FROM public.sisateg_vinculo_propriedade")
F("data mais recente no vinculo (fonte)", "SELECT MAX(\"@timestamp\") ts FROM sisateg_vinculo_propriedade")
con.close(); odbc.close()
