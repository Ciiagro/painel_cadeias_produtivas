"""Diagnostico no banco LOCAL: por que uma visita nao esta (ou esta em outro mes) no resumo do painel.
Uso:  python scripts/diagnostico_visita.py 9293843 9293842"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402

ids = [a for a in sys.argv[1:] if a.isdigit()]
if not ids:
    sys.exit("Informe o(s) id(s) da visita.")
con = local()
cur = con.cursor()
lista = ",".join(ids)


def q(titulo, sql):
    print(f"\n=== {titulo} ===")
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print(" | ".join(cols))
        for r in rows:
            print(" | ".join("" if v is None else str(v) for v in r))
        if not rows:
            print("(nenhuma linha)")
    except Exception as e:
        con.rollback()
        print("ERRO:", str(e).splitlines()[0])


q("1) Visita no cadastro de visitas (referencia e exclusao)",
  f"SELECT id_visita, id_propriedade, referencia_visita, dt_exclusao_visita FROM public.sisateg_rel_listar_visita WHERE id_visita::text IN ({','.join(repr(i) for i in ids)})")
q("2) Linhas de receita/despesa locais da visita (resumo por data e status)",
  f"SELECT id_visita, id_propriedade, to_char(dt_referencia,'YYYY-MM') mes_item, status_item, tipo_registro, grupo, COUNT(*) n FROM public.sisateg_receita_despesa WHERE id_visita::text IN ({','.join(repr(i) for i in ids)}) GROUP BY 1,2,3,4,5,6 ORDER BY 1,3,4,5,6")
q("3) A propriedade esta em resumo_propriedades?",
  f"SELECT id_propriedade, propriedade, ativa, projeto FROM public.resumo_propriedades WHERE id_propriedade::text IN (SELECT id_propriedade::text FROM public.sisateg_rel_listar_visita WHERE id_visita::text IN ({','.join(repr(i) for i in ids)}))")
q("4) A visita esta no resumo mensal (em qual mes)?",
  f"SELECT mes, id_propriedade, id_visita, receita_bruta, despesa_direta, producao_leite_l FROM public.resumo_leite_mensal WHERE ',' || id_visita || ',' ~ ',({'|'.join(ids)}),'")
con.close()
