"""Que visitas a planilha mensal usa, e o que as propriedades de FORA tem de diferente. Uso: python -u scripts/comparar_visitas_planilha.py "tabela (8).xlsx" """
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
import openpyxl, pandas as pd

ws = openpyxl.load_workbook(sys.argv[1]).active
rows = list(ws.iter_rows(values_only=True)); h = rows[0]
ip, iv = h.index("ID Propriedade"), h.index("ID Visita")
pl = pd.DataFrame([(str(r[ip]).strip(), str(r[iv]).strip()) for r in rows[1:] if r[ip] and str(r[ip]).strip().isdigit()], columns=["idp", "idv"])
print("Linhas lidas:", len(pl), flush=True)
con = local(); cur = con.cursor(); cur.execute("SET statement_timeout = 120000")
cur.execute("""SELECT id_visita::text idv, id_propriedade::text idp, to_char(dt_visita,'YYYY-MM') mes_visita, referencia_visita ref, mes_referencia_visita mes_ref,
  visita_valida valida, flg_coleta_dados coleta, visita_presencial presencial, visita_virtual virtual, visita_retorno retorno,
  flg_primeira_visita primeira, (id_relatorio_mensal IS NOT NULL) tem_rel_mensal, qtd_lancamentos, qtd_receita_lancada, qtd_despesa_lancada, numero_visita
  FROM public.sisateg_rel_listar_visita WHERE dt_exclusao_visita IS NULL AND atividade = 'BOVINOCULTURA DE LEITE'""")
v = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description]); con.close()
print("Visitas de leite no cadastro:", len(v), flush=True)
m = pl.merge(v, on=["idv", "idp"], how="left", indicator=True)
print("\n=== Visitas da planilha: achadas no cadastro? ===")
print(m["_merge"].value_counts().to_string())
a = m[m["_merge"] == "both"]
print("\n=== Visitas da planilha por mes da data da visita ===")
print(a.groupby("mes_visita").size().to_string())
print("\n=== Visitas da planilha por referencia ===")
print(a.groupby("ref").size().to_string())
plan_ids = set(pl["idp"])
v["na_planilha"] = v["idp"].isin(plan_ids)
# ultima visita por propriedade ativa (qualquer data)
ult = v.sort_values("mes_visita").groupby("idp").tail(1)
for col in ["valida", "coleta", "presencial", "virtual", "retorno", "primeira", "tem_rel_mensal", "numero_visita"]:
    print(f"\n=== {col}: ultima visita, DENTRO x FORA da planilha ===")
    print(pd.crosstab(ult[col].astype(str), ult["na_planilha"]).to_string())
print("\n=== lancamentos da ultima visita (media) ===")
print(ult.groupby("na_planilha")[["qtd_lancamentos", "qtd_receita_lancada", "qtd_despesa_lancada"]].apply(lambda d: d.apply(pd.to_numeric, errors="coerce").mean()).to_string())
