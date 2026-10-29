@echo off
rem ATUALIZACAO RAPIDA do painel da Bovinocultura de leite: so o mes atual e o anterior (uso do dia a dia).
rem Para pegar correcoes em meses mais antigos, use atualizar_leite_completo.bat (de vez em quando).
cd /d C:\CIIAGRO2\painel_cadeias\Bovinocultura
echo Dica: rode antes C:\CIIAGRO2\integracao_ateg_painel_servidor\atualizar_visitas.bat (visitas, propriedades e vinculos).
echo.
python scripts\atualizar_tudo.py --rapido
if errorlevel 1 (
  echo.
  echo ERRO: o servidor NAO foi atualizado completamente. Veja a mensagem acima.
)
pause
