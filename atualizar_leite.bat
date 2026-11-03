@echo off
rem ATUALIZACAO do painel da Bovinocultura de leite (uso do dia a dia): recarrega os ULTIMOS 6 MESES, para pegar lancamentos feitos depois em meses recentes.
rem Se estiver com pressa, use atualizar_leite_rapido.bat (so o mes atual e o anterior).
cd /d C:\CIIAGRO2\painel_cadeias\Bovinocultura
echo Dica: rode antes C:\CIIAGRO2\integracao_ateg_painel_servidor\atualizar_visitas.bat (visitas, propriedades e vinculos).
echo.
python scripts\atualizar_tudo.py --meses 6
if errorlevel 1 (
  echo.
  echo ERRO: o servidor NAO foi atualizado completamente. Veja a mensagem acima.
)
pause
