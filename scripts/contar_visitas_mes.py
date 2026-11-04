"""Quantas visitas / propriedades o cadastro local tem por mes de referencia. Uso: python scripts/contar_visitas_mes.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
con = local(); cur = con.cursor()
def q(t, sql):
    print(f"\n=== {t} ===")
    try:
        cur.execute(sql); print(" | ".join(d[0] for d in cur.description))
        for r in cur.fetchall(): print(" | ".join("" if v is None else str(v) for v in r))
    except Exception as e:
        con.rollback(); print("ERRO:", str(e).splitlines()[0])
q("1) Visitas por mes de referencia (nao excluidas)", """SELECT referencia_visita mes, COUNT(DISTINCT id_visita) visitas, COUNT(DISTINCT id_propriedade) propriedades
   FROM public.sisateg_rel_listar_visita WHERE dt_exclusao_visita IS NULL AND referencia_visita >= '2026-05' GROUP BY 1 ORDER BY 1""")
q("2) Colunas da tabela de visitas", "SELECT column_name FROM information_schema.columns WHERE table_name='sisateg_rel_listar_visita' ORDER BY ordinal_position")
q("3) Visita mais recente no cadastro", "SELECT MAX(id_visita::bigint) maior_id_visita FROM public.sisateg_rel_listar_visita")
con.close()
