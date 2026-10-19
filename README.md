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
