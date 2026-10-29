@echo off
rem Recarrega TODA a historia da fonte do SisATeG desde 2024-06-01 (inicio do painel), recalcula tudo e copia para o servidor. Demora (rode quando puder esperar).
cd /d "%~dp0"
python scripts\atualizar_tudo.py --desde 2024-06-01
if errorlevel 1 echo.
if errorlevel 1 echo ERRO: o servidor NAO foi atualizado. Veja a mensagem acima.
pause
