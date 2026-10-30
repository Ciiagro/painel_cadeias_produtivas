# Atualização do painel da Bovinocultura de leite (passo a passo)

Pasta do projeto: `C:\CIIAGRO2\painel_cadeias\Bovinocultura`
Use o **Git Bash**, dentro dessa pasta: `cd /c/CIIAGRO2/painel_cadeias/Bovinocultura`
(O Git Bash não roda `.bat` direto. Use os comandos `python scripts/...` abaixo.
No Explorer, os `.bat` funcionam com dois cliques.)

## Qual comando usar

| Quando | Comando | Equivale ao .bat | Tempo |
|---|---|---|---|
| **Todo dia** | `python scripts/atualizar_tudo.py --rapido` | `atualizar_leite.bat` | poucos minutos |
| **Toda semana** | `python scripts/atualizar_tudo.py` (completo, olha 120 dias) | `atualizar_leite_completo.bat` | mais demorado |
| Só mudou o SQL do resumo | `python scripts/atualizar_tudo.py --so-resumo --completo` | `atualizar_so_resumo_completo.bat` | só refaz o resumo |
| Recarregar de 2026 | `python scripts/atualizar_tudo.py --desde 2026-01-01` | `atualizar_historia_2026.bat` | depende do período |
| Recarregar tudo (2024 em diante) | `python scripts/atualizar_tudo.py --desde 2024-06-01` | `atualizar_historia_completa.bat` | 15 a 20 min |

- O **rápido** olha só os últimos 45 dias e recalcula só os meses recentes.
- O SisATeG às vezes lança itens em **meses antigos depois**. Esses só chegam no completo (120 dias) ou no `--desde`.
- Com `--desde` a carga é mês a mês e mostra `AAAA-MM: N linhas`. Dá para ver que não travou.
- Se der erro no meio, rode o mesmo comando de novo. Nada fica pela metade.

## Antes de começar (primeira vez, ou antes de mudança grande)
1. Backup no pgAdmin: botão direito no banco > Backup... > formato Custom.
   - `api_sisateg` (servidor local) -> `C:\backups\api_sisateg_AAAA-MM-DD`
   - `painel_ateg` (servidor Painel ATEG) -> `C:\backups\painel_ateg_AAAA-MM-DD`
2. Confirme que os arquivos de backup existem e não estão com tamanho zero.

## Rotina diária (nesta ordem)
1. Visitas: dois cliques em `C:\CIIAGRO2\integracao_ateg_painel_servidor\atualizar_visitas.bat`.
   Confira "MIGRAÇÃO CONCLUÍDA COM SUCESSO!" e "Visitas distintas no servidor agora".
   (A tabela de visitas define o mês de cada visita. Se estiver desatualizada, algumas visitas somem ou caem no mês errado.)
2. Leite: `python scripts/atualizar_tudo.py --rapido`. Ele faz:
   1/5 receita e despesa do SisATeG (janela móvel, com trava de 50%)
   2/5 refaz `sisateg_receita_despesa` (com cópia de segurança datada; guarda as 3 últimas)
   3/5 recria o resumo do leite (rápido: só os meses recentes)
   4/5 atualiza regiões e sindicatos
   5/5 copia para o servidor e recria as views numa única transação
3. Espere aparecer **"Pronto"**. Não feche a janela.
   Se aparecer `TRAVA`, `ERRO` ou `AVISO`, pare e investigue.
   Mensagens "already exists, skipping" e "does not exist, skipping" são normais.
4. Se mudou código: `git add -A`, `git commit` e `git push origin main`. Depois Ctrl+F5 no painel (Vercel).
   Se rodar o painel local, reinicie o uvicorn antes do Ctrl+F5.

## Rotina semanal
Mesmos passos, com `python scripts/atualizar_tudo.py` (completo).

## Conferir com a planilha do SisATeG
1. Baixe a planilha mensal do SisATeG.
2. No painel, vá em **Conferência**, escolha o mês e suba a planilha (não suba o arquivo `conferencia_AAAA-MM.xlsx` exportado pelo painel).
3. Esperado: **0 diferenças** em receita, despesa e produção.
4. Normal e esperado:
   - "Visitas sem lançamento de leite": visitas com valores zerados, que não entram no painel.
   - Projetos de **Treinamento** não entram no painel nem na conferência.
5. Se aparecer diferença: anote o ID da visita e veja o que o SisATeG tem nela:
   `python scripts/consultar_visita.py <id_visita>`
6. Meses antigos podem ter pequenas diferenças de itens lançados depois no SisATeG. Rode `--desde` do período e confira de novo.

## Casos já conhecidos (não são erro do painel)
- **Sítio Baixas 01 (Oros), set/2026, visita 10064388:** a venda de leite está lançada em duplicidade no SisATeG (valor certo seria R$ 8.910). A planilha mostra R$ 35.640 e o painel R$ 17.820. O técnico deve corrigir no SisATeG. Depois, a recarga do mês acerta.

## Regras do painel (iguais às da planilha do SisATeG)
- Receita = receita bruta + empréstimo + investimento (venda de bem).
- Produção = leite vendido + consumido + bezerras + descarte.
- Só visitas não excluídas; só propriedades ativas; projetos de Treinamento fora.
- Mês da visita = o mês dos LANÇAMENTOS (a data mais recente dos itens da visita), como a planilha do SisATeG. A `referencia_visita` cadastrada não é usada; visitas em que ela difere aparecem na aba Revisar lançamentos.
- Se o item tem quantidade ativa mas não tem preço principal ativo, usa-se o preço detalhado ativo.

## Se der erro
- Nada é trocado no servidor se o passo falhar antes do fim (transação única).
- `TRAVA`: a API devolveu menos de 50% do que já há; confira VPN/ODBC. Só use `--forcar` se for mesmo o caso.
- Erro `Unsupported content type` no ODBC: rode o comando de novo (a carga já tenta 3 vezes por mês).
- Lançamento com data de referência antiga: `python scripts/atualizar_tudo.py --desde AAAA-MM-DD`.
- pgAdmin travado ou lento: veja `pg_stat_activity` e encerre conexões paradas com `pg_terminate_backend(pid)`. Nunca use `DROP ... CASCADE`.
- Rode SQL do banco local (`api_sisateg`) só nele. O servidor é o `painel_ateg`.
- Backup da janela de receita/despesa: tabelas `sisateg_receita_despesa_bkp_AAAAMMDD` no banco local.
