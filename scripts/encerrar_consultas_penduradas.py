"""Encerra consultas do Postgres local que estao rodando ha mais de 20 segundos (menos esta). Uso: python scripts/encerrar_consultas_penduradas.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_tudo import local  # noqa: E402
con = local(); con.autocommit = True; cur = con.cursor()
cur.execute("""SELECT pid, state, now() - query_start AS ha, left(regexp_replace(query, '\\s+', ' ', 'g'), 90)
  FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()
  AND state <> 'idle' AND now() - query_start > interval '20 seconds' ORDER BY query_start""")
rows = cur.fetchall()
if not rows:
    print("Nenhuma consulta pendurada.")
for pid, st, ha, q in rows:
    print(f"Encerrando pid {pid} ({st}, ha {ha}): {q}")
    cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
con.close()
