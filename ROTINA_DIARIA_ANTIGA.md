# Rotina diária do painel de cadeias (passo a passo)

Faça nesta ordem. Cada passo depende do anterior. Não rode duas cargas pesadas ao mesmo tempo.
Melhor horário: cedo, antes do uso, ou no almoço.

## 1) Git Bash: receita e despesa (janela de 120 dias)
```
cd "/c/CIIAGRO2/painel_cadeias"
python scripts/carga_incremental.py sisateg_receita
python scripts/carga_incremental.py sisateg_despesa
```
Termina com "Janela trocada: X linhas antigas -> Y novas." e "Concluído em N s."

## 2) Jupyter: demais tabelas que o painel usa
- Vínculos (`sisateg_vinculo_propriedade`): carga COMPLETA (lê tudo e troca tudo ou nada)
- Visitas (notebook `api_visitas`, primeira célula)
- Indicador padrão mensal (`sisateg_rel_indicador_padrao_mensal`)

## 3) pgAdmin, banco `api_sisateg`: refazer `sisateg_receita_despesa`
Parte A (monta a `_novo` ao lado da atual): arquivo `sql/refazer_receita_despesa.sql`, bloco "PASSO A".

Parte B (troca só a janela recarregada, tudo ou nada):
```sql
BEGIN;
DELETE FROM public.sisateg_receita_despesa
 WHERE dt_referencia >= date_trunc('month', current_date - interval '120 days');
INSERT INTO public.sisateg_receita_despesa
SELECT * FROM public.sisateg_receita_despesa_novo
 WHERE dt_referencia >= date_trunc('month', current_date - interval '120 days');
COMMIT;
DROP TABLE IF EXISTS public.sisateg_receita_despesa_novo;
```

## 4) pgAdmin, banco `api_sisateg`: refazer o resumo
Rodar o arquivo inteiro `sql/criar_resumo_leite_mensal.sql`.
Conferir a última linha: propriedades_ativas, com_leite, linhas_mensais, ultimo_mes.

## 5) Git Bash: copiar para o servidor
```
cd "/c/CIIAGRO2/painel_cadeias"
python scripts/transferir_resumo.py
```
Depois abrir o painel na Vercel e atualizar com Ctrl+F5.

## Uma vez por semana (mudam pouco)
- Propriedades, pessoas e escolaridade (`sisateg_propriedade`, `sisateg_pessoa`, `sisateg_escolaridade`)
- Orientação técnica (`sisateg_orientacao_tecnica`), só se algum outro painel usar

## Observações
- Nada disso altera o histórico anterior a jun/2024 da `sisateg_receita_despesa`.
- Se um passo der erro, as tabelas ficam como estavam (as trocas são "tudo ou nada"). Não siga para o passo seguinte.
- A senha do Postgres NÃO deve ficar escrita nos notebooks/scripts. Está nas pendências trocar.
