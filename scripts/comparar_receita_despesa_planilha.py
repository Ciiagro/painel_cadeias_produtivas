"""Compara RECEITA e DESPESA da planilha do SisATeG (Excel de um mes) com as do banco (dados da API), por propriedade.
Uso (na pasta do projeto):  python scripts\\comparar_receita_despesa_planilha.py "tabela (8).xlsx" [YYYY-MM]
  - sem o mes, usa o mes que esta na propria planilha (colunas Ano e Mes)
Gera: comparacao_receita_despesa.xlsx (abas: Resumo, Diferencas, Todas)
Planilha: Receitas = receita bruta + venda de bem + recebimento de emprestimo; Despesas Diretas.
Banco:    receita_bruta (+ 'Fora da receita bruta' de resumo_tipo, para ficar igual a coluna Receitas) e despesa_direta."""
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import text
sys.path.insert(0, str(Path(__file__).resolve().parent))
from transferir_resumo import eng  # noqa: E402

if len(sys.argv) < 2:
    sys.exit('Informe a planilha. Ex.: python scripts\\comparar_receita_despesa_planilha.py "tabela (8).xlsx"')
TOL = 1.0  # diferencas de ate R$ 1,00 sao ignoradas

pl = pd.read_excel(sys.argv[1])
pl = pl[pd.to_numeric(pl["ID Propriedade"], errors="coerce").notna()].copy()
pl["id"] = pl["ID Propriedade"].astype(float).astype(int).astype(str)
mes = sys.argv[2] if len(sys.argv) > 2 else f'{int(pl["Ano"].iloc[0])}-{int(pl["Mês"].iloc[0]):02d}'
print(f"Mes: {mes} | linhas na planilha: {len(pl)}", flush=True)
a = pl.groupby("id").agg(propriedade=("Propriedade", "first"), tecnico=("Técnico", "first"),
                         rec_planilha=("Receitas", "sum"), desp_planilha=("Despesas Diretas", "sum")).reset_index()

e = eng("LOCAL")
with e.connect() as c:
    b = pd.DataFrame(c.execute(text("""SELECT id_propriedade::text AS id, SUM(receita_bruta) AS rec_bruta, SUM(despesa_direta) AS desp_banco
                                       FROM public.resumo_leite_mensal WHERE mes = :m GROUP BY 1"""), {"m": mes}).mappings().all(),
                     columns=["id", "rec_bruta", "desp_banco"])
    try:
        f = pd.DataFrame(c.execute(text("""SELECT id_propriedade::text AS id, SUM(valor) AS rec_fora FROM public.resumo_tipo
                                           WHERE mes = :m AND classe = 'Fora da receita bruta' GROUP BY 1"""), {"m": mes}).mappings().all(),
                         columns=["id", "rec_fora"])
    except Exception:
        f = pd.DataFrame(columns=["id", "rec_fora"]); print("Aviso: resumo_tipo indisponivel; receita do banco = so receita bruta.")
if b.empty:
    sys.exit(f"Nenhum dado do mes {mes} no banco local.")
f["rec_fora"] = f["rec_fora"].astype(float)
b = b.merge(f, on="id", how="left").fillna({"rec_fora": 0})
for col in ("rec_bruta", "desp_banco", "rec_fora"):
    b[col] = b[col].astype(float)
b["rec_banco"] = b["rec_bruta"] + b["rec_fora"]

m = a.merge(b, on="id", how="outer", indicator=True)
m["onde"] = m["_merge"].map({"both": "nos dois", "left_only": "so na planilha", "right_only": "so no banco"})
m = m.drop(columns="_merge").fillna({"rec_planilha": 0, "desp_planilha": 0, "rec_banco": 0, "desp_banco": 0, "rec_fora": 0, "rec_bruta": 0})
m["dif_receita"] = (m["rec_banco"] - m["rec_planilha"]).round(2)
m["dif_despesa"] = (m["desp_banco"] - m["desp_planilha"]).round(2)
dif = m[(m["dif_receita"].abs() > TOL) | (m["dif_despesa"].abs() > TOL)].sort_values("dif_receita", key=abs, ascending=False)

res = pd.DataFrame({"": ["Receita", "Despesa direta"],
                    "Planilha": [m["rec_planilha"].sum(), m["desp_planilha"].sum()],
                    "Banco (API)": [m["rec_banco"].sum(), m["desp_banco"].sum()]})
res["Diferenca"] = res["Banco (API)"] - res["Planilha"]
print("\n=== TOTAIS ==="); print(res.round(2).to_string(index=False))
print(f"\nPropriedades: planilha {len(a)} | banco {len(b)} | so na planilha {(m.onde=='so na planilha').sum()} | so no banco {(m.onde=='so no banco').sum()}")
print(f"Propriedades com diferenca (> R$ {TOL:.0f}): {len(dif)}")
cols = ["id", "propriedade", "tecnico", "onde", "rec_planilha", "rec_banco", "dif_receita", "desp_planilha", "desp_banco", "dif_despesa"]
print(dif[cols].head(30).round(2).to_string(index=False))
with pd.ExcelWriter("comparacao_receita_despesa.xlsx") as w:
    res.to_excel(w, sheet_name="Resumo", index=False); dif[cols].to_excel(w, sheet_name="Diferencas", index=False); m[cols].to_excel(w, sheet_name="Todas", index=False)
print("\nArquivo gerado: comparacao_receita_despesa.xlsx")
