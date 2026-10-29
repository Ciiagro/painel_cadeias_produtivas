@echo off
cd /d "%~dp0"
python scripts\consultar_visita.py %*
pause
