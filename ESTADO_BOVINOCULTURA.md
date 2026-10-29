# Cadeia gravada: Bovinocultura de leite (estado em 21/10/2026)

Para voltar a esta cadeia, é só pedir. Resumo do que está pronto e do que falta.

## O que o painel tem (pasta C:\CIIAGRO2\painel_cadeias, Vercel)
- Filtros em cascata: projeto, supervisor, região (Supabase, via municipio_regiao), técnico, município, propriedade, situação (ativas/inativas) e período De/Até. Abre no último mês FECHADO.
- Todas as propriedades que já tiveram leite (ativas e inativas), com o técnico da época (da visita).
- Cartões com seta e variação; 8 gráficos (receita bruta, despesa direta, venda de leite, preço médio, produção, margem da atividade, margem do leite, produção média por produtor).
- Abas: Gráficos, Destaques do mês (por regras, explica a queda: saídas, entradas, volume, preço), Receitas e despesas (por tipo/subgrupo: receita bruta, despesa direta, outras despesas, aleitamento, investimento e empréstimo; mesmo padrão do painel de ovinocaprinocultura), Causas (entradas/saídas por mês, preço fora da média, despesa direta por subgrupo com variação), Tabela mensal (com preço médio) e botão Baixar Excel respeitando os filtros.
- Cabeçalho novo: faixa com a foto das vacas e o logo do Sistema FAEC SENAR Ceará (imagens embutidas no index.html).

## Regras de cálculo (conferidas com o SisATeG)
- Valor do lançamento = QUANTIDADE x VALOR_UNITARIO. Atividade BOVINOCULTURA DE LEITE, status ATIVO, tipo PRINCIPAL.
- Venda de leite = leite in natura + Bonificação do leite por qualidade.
- Receita bruta = sem empréstimo/investimento; no subgrupo Venda de leite só in natura e bonificação.
- Despesa direta = sem empréstimo, investimento, aleitamento, "Despesas com Formação..." e "Mão de obra familiar". Adler jul/2025 deve dar R$ 446.149,97.
- Preço médio do leite = média dos preços de cada propriedade no mês (leite in natura ÷ litros, SEM bonificação). Adler jul/2025 = R$ 2,22.

## Rotina de atualização
1) Rodar C:\CIIAGRO2\integracao_ateg_painel_servidor\atualizar_visitas.bat (visitas, propriedades, vínculos).
2) Rodar atualizar_leite.bat (nesta pasta): receita/despesa até hoje, refaz sisateg_receita_despesa, recria o resumo, atualiza regiões/sindicatos e copia para o servidor.
3) Git push (se mudou código) e Ctrl+F5 no painel. Rotina manual antiga: ROTINA_DIARIA_ANTIGA.md (só referência).
Obs.: sisateg_rel_indicador_padrao_mensal e sisateg_rel_indicador_leite_mensal são recarregadas por inteiro (scripts/carga_indicadores_mensais.py, dentro do atualizar_leite.bat).

## Pendências desta cadeia
- Conferir os números novos com o banco de verdade (aba Causas, preço médio, despesa por subgrupo) e comparar com o SisATeG.
- Receita do Adler vs R$ 452.088,46 do SisATeG nunca foi reconciliada (tabela candidata: sisateg_rel_indicador_leite_mensal.renda_bruta_leite).
- Destaques: decidir se compara com o primeiro mês do período (hoje) ou sempre com o mês anterior.
- Rotina em dois .bat (feito, ainda NÃO testado em 29/10/2026). Falta: Agendador de Tarefas do Windows.
- Situação por mês (hoje ativa/inativa é a situação de hoje).
- Acesso ao painel (aberto ou com senha), trocar senhas expostas, confirmar supervisor oficial.
