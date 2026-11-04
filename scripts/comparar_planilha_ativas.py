"""Lista as propriedades que o painel conta como ATIVAS e que NAO estao na planilha mensal do SisATeG.
Uso:  python scripts/comparar_planilha_ativas.py "caminho\\tabela (8).xlsx"
Gera: ativas_fora_da_planilha.xlsx (nesta pasta)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
import openpyxl, pandas as pd

if len(sys.argv) < 2:
    sys.exit('Informe o arquivo da planilha. Ex.: python scripts/comparar_planilha_ativas.py "tabela (8).xlsx"')
ws = openpyxl.load_workbook(sys.argv[1]).active
rows = list(ws.iter_rows(values_only=True)); h = rows[0]
ip = h.index("ID Propriedade")
plan = {str(r[ip]).strip() for r in rows[1:] if r[ip] and str(r[ip]).strip().isdigit()}
print(f"Propriedades na planilha: {len(plan)}")
if not plan:
    sys.exit("Nao li nenhuma propriedade na planilha. Confira se o arquivo e a planilha mensal do SisATeG.")

print("Conectando no banco local...", flush=True)
con = local(); cur = con.cursor()
cur.execute("SET statement_timeout = 120000")
print("Consultando as propriedades ativas...", flush=True)
cur.execute("""
WITH vis AS (
  SELECT DISTINCT ON (id_propriedade::text) id_propriedade::text AS idp, dt_visita AS ultima_visita,
         referencia_visita AS ult_referencia, atividade AS ult_atividade, visita_valida AS ult_valida,
         visita_zero AS ult_zero, status_propriedade AS ult_status
  FROM public.sisateg_rel_listar_visita
  WHERE dt_exclusao_visita IS NULL
  ORDER BY id_propriedade::text, dt_visita DESC NULLS LAST),
 cnt AS (
  SELECT id_propriedade::text AS idp, COUNT(*) FILTER (WHERE referencia_visita >= '2026-05') AS visitas_desde_maio
  FROM public.sisateg_rel_listar_visita WHERE dt_exclusao_visita IS NULL GROUP BY 1)
SELECT p.id_propriedade::text AS id, p.propriedade, p.projeto, p.tecnico, p.municipio,
       p.inicio_projeto, p.fim_projeto, p.status_vinculo, v.ultima_visita, v.ult_referencia, v.ult_atividade,
       v.ult_valida, v.ult_zero, v.ult_status, c.visitas_desde_maio
FROM public.resumo_propriedades p LEFT JOIN vis v ON v.idp = p.id_propriedade::text LEFT JOIN cnt c ON c.idp = p.id_propriedade::text
WHERE p.ativa""")
print("Consulta terminou.", flush=True)
cols = [d[0] for d in cur.description]
df = pd.DataFrame(cur.fetchall(), columns=cols)
con.close()
df["na_planilha"] = df["id"].isin(plan)
fora = df[~df["na_planilha"]].copy()
print(f"Ativas no painel: {len(df)}  |  na planilha: {int(df['na_planilha'].sum())}  |  fora da planilha: {len(fora)}")
print("\n=== Fora da planilha, por projeto ===")
print(fora.groupby("projeto", dropna=False).size().to_string())
fora["ult_visita_mes"] = pd.to_datetime(fora["ultima_visita"], errors="coerce").dt.strftime("%Y-%m")
print("\n=== Fora da planilha, por mes da ultima visita ===")
print(fora.groupby("ult_visita_mes", dropna=False).size().to_string())
print("\n=== Fora da planilha, por ano/mes de INICIO do vinculo ===")
print(fora.groupby(pd.to_datetime(fora["inicio_projeto"], errors="coerce").dt.strftime("%Y-%m"), dropna=False).size().to_string())
for col, tit in [("ult_referencia","referencia da ultima visita"),("ult_atividade","atividade da ultima visita"),("ult_valida","ultima visita valida?"),("ult_zero","ultima visita e visita zero?"),("ult_status","status da propriedade na ultima visita")]:
    print(f"\n=== Fora da planilha: {tit} ===")
    print(fora.groupby(col, dropna=False).size().to_string())
    print(f"--- Na planilha: {tit} ---")
    print(df[df["na_planilha"]].groupby(col, dropna=False).size().sort_values(ascending=False).head(6).to_string())
print("\n=== Na planilha, por mes da ultima visita (para comparar) ===")
dentro = df[df["na_planilha"]].copy()
print(dentro.groupby(pd.to_datetime(dentro["ultima_visita"], errors="coerce").dt.strftime("%Y-%m"), dropna=False).size().tail(8).to_string())
fora.drop(columns=["na_planilha"]).to_excel("ativas_fora_da_planilha.xlsx", index=False)
print("\nArquivo gerado: ativas_fora_da_planilha.xlsx")
