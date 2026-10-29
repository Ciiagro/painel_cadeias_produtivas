@echo off
rem Recarrega a HISTORIA da fonte do SisATeG a partir de 2026-01-01 (pega itens lancados depois em meses antigos), recalcula tudo e copia para o servidor.
cd /d "%~dp0"
python scripts\atualizar_tudo.py --desde 2026-01-01
if errorlevel 1 echo.
if errorlevel 1 echo ERRO: o servidor NAO foi atualizado. Veja a mensagem acima.
pause
