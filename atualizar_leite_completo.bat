@echo off
rem ATUALIZACAO COMPLETA do painel da Bovinocultura de leite: janela de 120 dias + indicadores mensais (mais demorada).
rem Use de vez em quando (ex.: 1 vez por semana) ou quando mudar uma regra de calculo.
cd /d C:\CIIAGRO2\painel_cadeias\Bovinocultura
echo Dica: rode antes C:\CIIAGRO2\integracao_ateg_painel_servidor\atualizar_visitas.bat (visitas, propriedades e vinculos).
echo.
python scripts\atualizar_tudo.py 
if errorlevel 1 (
  echo.
  echo ERRO: o servidor NAO foi atualizado completamente. Veja a mensagem acima.
)
pause
