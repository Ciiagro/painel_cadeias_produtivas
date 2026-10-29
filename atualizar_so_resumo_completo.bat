@echo off
rem Recalcula TODOS os meses (sem baixar dados do SisATeG) e copia para o servidor.
cd /d "%~dp0"
python scripts\atualizar_tudo.py --so-resumo --completo
pause
