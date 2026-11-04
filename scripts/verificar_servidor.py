"""Confere no SERVIDOR (painel_ateg) se a tabela/view nova do cartao Propriedades ativas existem e quanto dao. Uso: python -u scripts/verificar_servidor.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from transferir_resumo import eng  # noqa: E402
from sqlalchemy import text
e = eng("REMOTE")
def q(t, sql):
    print(f"\n=== {t} ===", flush=True)
    try:
        with e.connect() as c:
            r = c.execute(text(sql)); print(" | ".join(r.keys()))
            for row in r: print(" | ".join("" if x is None else str(x) for x in row))
    except Exception as ex:
        print("ERRO:", str(ex).splitlines()[0])
q("1) A tabela e a view existem?", "SELECT to_regclass('public.resumo_propriedade_mes') AS tabela, to_regclass('public.vw_propriedade_mes') AS view")
q("2) Linhas da tabela por mes (ultimos meses)", "SELECT mes, COUNT(DISTINCT id_propriedade) propriedades FROM public.resumo_propriedade_mes WHERE mes >= '2026-07' GROUP BY 1 ORDER BY 1")
q("3) Pela view (so ativas), mes 2026-10", "SELECT mes, COUNT(DISTINCT id_propriedade) propriedades FROM public.vw_propriedade_mes WHERE ativa AND mes = '2026-10' AND COALESCE(projeto,'') NOT ILIKE 'TREINAMENTO%' GROUP BY 1")
q("4) Ultima atualizacao do resumo no servidor", "SELECT MAX(mes) ultimo_mes, COUNT(*) linhas FROM public.resumo_leite_mensal")
