# Atualização do painel da Bovinocultura de leite (passo a passo)

Pasta do projeto: `C:\CIIAGRO2\painel_cadeias\Bovinocultura`

## Antes de começar (sempre que mudar algo grande, e na primeira vez)
1. Backup no pgAdmin: botão direito no banco > Backup... > formato Custom.
   - `api_sisateg` (servidor local) -> `C:\backups\api_sisateg_AAAA-MM-DD`
   - `painel_ateg` (servidor Painel ATEG) -> `C:\backups\painel_ateg_AAAA-MM-DD`
2. Confirme que os arquivos de backup existem e não estão com tamanho zero.

## Rotina (nesta ordem)
1. Dois cliques em `C:\CIIAGRO2\integracao_ateg_painel_servidor\atualizar_visitas.bat`.
   Confira "MIGRAÇÃO CONCLUÍDA COM SUCESSO!" e "Visitas distintas no servidor agora".
2. Dois cliques em `atualizar_leite.bat` (nesta pasta). Ele faz:
   - receita e despesa da API até hoje (janela móvel de 120 dias, com trava de 50%)
   - indicadores mensais (carga completa)
   - refaz `sisateg_receita_despesa` (com cópia de segurança datada da janela; guarda as 3 últimas)
   - recria o resumo do leite (de 2024-06-01 até hoje)
   - atualiza regiões e sindicatos (Supabase -> servidor)
   - copia para o servidor e recria as views numa única transação
3. Confira no final: última `dt_referencia`, último mês (`AAAA-MM`), "Pronto em N s".
   Se aparecer `TRAVA`, `ERRO` ou `AVISO`, pare e investigue.
4. Se mudou código: `git push`. Depois Ctrl+F5 no painel (Vercel).

## Conferência
- Alexson, set/2026: 29 propriedades, 21.358 L, R$ 48.010,46 de receita, R$ 29.797,22 de despesa direta, margem R$ 18.213.
- Filtro Região preenchido no painel.

## Se der erro
- Nada é trocado no servidor se o passo falhar antes do fim (transação única).
- `TRAVA`: a API devolveu menos de 50% do que já há; confira VPN/ODBC. Só use `--forcar` se for mesmo o caso.
- Lançamento digitado com data de referência com mais de 120 dias: `python scripts/carga_incremental.py sisateg_receita --desde AAAA-MM-DD` (e `sisateg_despesa`), depois rode `atualizar_leite.bat`.
- Backup da janela de receita/despesa: tabelas `sisateg_receita_despesa_bkp_AAAAMMDD` no banco local.
