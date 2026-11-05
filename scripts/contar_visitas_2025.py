"""Visitas e propriedades de LEITE por mes de referencia (cadastro local, visitas nao excluidas), de 2024-06 a hoje.
Compare com a coluna 'Na planilha' da aba Conferencia. Uso: python -u scripts/contar_visitas_2025.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
con = local(); cur = con.cursor()
cur.execute("""SELECT referencia_visita mes, COUNT(DISTINCT id_visita) visitas, COUNT(DISTINCT id_propriedade) propriedades
  FROM public.sisateg_rel_listar_visita
  WHERE atividade = 'BOVINOCULTURA DE LEITE' AND dt_exclusao_visita IS NULL AND referencia_visita >= '2023-01'
  GROUP BY 1 ORDER BY 1""")
print("mes | visitas | propriedades")
for r in cur.fetchall(): print(" | ".join(str(x) for x in r))
con.close()
