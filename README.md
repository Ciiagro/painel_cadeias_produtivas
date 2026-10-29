# Painel de acompanhamento mensal das cadeias

FastAPI + página com gráficos (Chart.js). Mostra, por supervisor e técnico, a evolução mensal de
**receita bruta, produção e margem bruta**, com a variação de um mês para o outro.

Lê apenas a view `public.vw_resumo_leite_mensal` do servidor público (nunca o banco local).
O supervisor vem do ranking (`ranking_tecnicos.ultimo_supervisor`).

## Fluxo dos dados
1. Banco local `api_sisateg`: rodar `sql/criar_resumo_leite_mensal.sql` (cria `resumo_leite_mensal`).
2. `python scripts/transferir_resumo.py` copia o resumo para o servidor público.
3. No servidor público: rodar `sql/vw_resumo_leite_mensal.sql` (view com supervisor do ranking e margem bruta).
4. O painel lê a view.

## Rodar
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # preencha DB_URL (usuário só de leitura) 
uvicorn app.main:app --reload --port 8000
```
Abrir http://localhost:8000

## Próximos passos
- Incluir outras cadeias (coluna `cadeia` no resumo + filtro).
- Agendar os passos 1–2 (Agendador de Tarefas do Windows).
- Publicar o painel no servidor (uvicorn atrás de nginx/Vercel-like).

---
## Estado do projeto e pendências (atualizado em 19/10/2026)

**Já funciona:** painel publicado na Vercel (repositório `Ciiagro/painel_cadeias_produtivas`), lendo as views
`vw_propriedades` e `vw_resumo_leite_mensal` do banco `painel_ateg` com o usuário só de leitura `painel_leitura`.
Conferido contra o relatório do SisATeG para o técnico Alexson em set/2026 (29 propriedades, 21.358 L,
R$ 48.010,46 de receita, R$ 29.797,22 de despesa direta, margem R$ 18.213).

**Rotina de atualização: `atualizar_leite.bat` (ver ESTADO_BOVINOCULTURA.md). Passos que ele executa, nesta ordem:**
1. `python scripts/carga_incremental.py sisateg_receita` e `... sisateg_despesa` (janela móvel de 120 dias; corrige a carga
   antiga que deixava visitas para trás). As demais tabelas da API continuam com os scripts de sempre.
2. Refazer `sisateg_receita_despesa` (receita + despesa empilhadas): `sql/refazer_receita_despesa.sql` (passo A e passo B).
3. Rodar `sql/criar_resumo_leite_mensal.sql` no banco local `api_sisateg`.
4. `python scripts/transferir_resumo.py` (copia as tabelas e recria as views; reaplica a permissão do `painel_leitura`).

**Pendências:**
- Decidir o acesso: painel aberto ou com senha (hoje aberto; mostra nomes de produtores e propriedades).
- Automatizar a rotina diária num comando só + Agendador de Tarefas do Windows (o PC precisa estar ligado).
- Supervisor: o ranking mostra Alexandre de Oliveira Pedroz... para o Alexson, o SisATeG mostra Yarissa Oliveira Lucena
  Feitosa. Confirmar qual é o oficial (o painel usa o do ranking).
- Antes de maio/2025 o histórico pode ter pequenas falhas (<1% das linhas) por causa da carga antiga da API.
- Trocar as senhas que já apareceram em conversa/arquivos antigos (Postgres local no script antigo de carga; senha do servidor).
- Outras cadeias produtivas (há uma coluna `cadeia` na view para isso).
- Conferir outros técnicos/meses contra o relatório do SisATeG.
