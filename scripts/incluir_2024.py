"""Inclui 2024-01 em diante SEM baixar nada da fonte: refaz a tabela combinada (sisateg_receita_despesa) a partir das tabelas brutas locais,
recria o resumo completo e copia para o servidor. Uso:  python scripts/incluir_2024.py"""
import subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import atualizar_tudo as t
t0 = time.time()
t.refazer_receita_despesa("2023-01-01")
t.criar_resumo(None)
t.rodar("5/5: copiando para o servidor e recriando as views", [sys.executable, "scripts/transferir_resumo.py"])
print(f"\nPronto em {int(time.time() - t0)} s. Reinicie o painel e dê Ctrl+F5.")
