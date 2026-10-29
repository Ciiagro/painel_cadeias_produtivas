"""
Atualiza o painel da Bovinocultura de leite ATÉ HOJE, de ponta a ponta (substitui a ROTINA_DIARIA.md manual).
Se um passo falha, para: as trocas são "tudo ou nada" e o servidor continua com os dados anteriores.

Uso (Git Bash ou Prompt, qualquer pasta):   python scripts\\atualizar_tudo.py
Ou dê dois cliques em atualizar_leite.bat (na raiz do projeto).

Passos:
  1  receita e despesa da API -> banco local (janela móvel, até hoje) + indicadores mensais (carga completa)
  2  refaz sisateg_receita_despesa (janela recarregada, tudo ou nada)
  3  recria o resumo do leite (resumo_propriedades, resumo_leite_mensal, resumo_despesa_subgrupo)
  4  atualiza municípios/regiões/sindicatos no servidor (Supabase -> municipio_regiao)
  5  copia o resumo para o servidor e recria as views (já com Região e Sindicato)
Antes disto, rode C:\\CIIAGRO2\\integracao_ateg_painel_servidor\\atualizar_visitas.bat (visitas, propriedades e vínculos).
"""
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")
INTEGRACAO = Path(r"C:\CIIAGRO2\integracao_ateg_painel_servidor")
DIAS = 120          # janela da atualização COMPLETA
DIAS_RAPIDO = 45    # janela da atualização RÁPIDA: mês atual + mês anterior


def rodar(titulo, cmd, cwd=RAIZ):
    print(f"\n=== {titulo} ===", flush=True)
    r = subprocess.run(cmd, cwd=str(cwd))
    if r.returncode != 0:
        sys.exit(f"\nERRO em '{titulo}'. Parei aqui; o servidor continua com os dados anteriores.")


def local():
    return psycopg2.connect(host=os.environ.get("LOCAL_DB_HOST", "localhost"), port=os.environ.get("LOCAL_DB_PORT", "5432"),
                            user=os.environ.get("LOCAL_DB_USER", "postgres"), password=os.environ["LOCAL_DB_PASS"],
                            dbname=os.environ.get("LOCAL_DB_NAME", "api_sisateg"))


def refazer_receita_despesa(ini):
    print(f"\n=== 2/5: refazendo sisateg_receita_despesa (de {ini} até hoje) ===", flush=True)
    con = local()
    cur = con.cursor()
    cur.execute("""
        SELECT string_agg(format('%I::%s', attname, format_type(atttypid, atttypmod)), ', ' ORDER BY attnum)
        FROM pg_attribute WHERE attrelid = 'public.sisateg_receita_despesa'::regclass AND attnum > 0 AND NOT attisdropped""")
    sel = cur.fetchone()[0]
    cur.execute("DROP TABLE IF EXISTS public.sisateg_receita_despesa_novo")
    cur.execute(f"CREATE TABLE public.sisateg_receita_despesa_novo AS SELECT {sel} FROM public.sisateg_receita "
                f"UNION ALL SELECT {sel} FROM public.sisateg_despesa")
    cur.execute("SELECT COUNT(*) FROM public.sisateg_receita_despesa_novo WHERE dt_referencia >= %s", (ini,))
    n_novo = cur.fetchone()[0]
    if n_novo == 0:
        con.rollback()
        sys.exit("A tabela nova ficou sem linhas na janela: nada foi trocado.")
    # cópia de segurança da janela que vai ser trocada (mantém as 3 últimas)
    bkp = f"sisateg_receita_despesa_bkp_{date.today():%Y%m%d}"
    cur.execute(f"DROP TABLE IF EXISTS public.{bkp}")
    cur.execute(f"CREATE TABLE public.{bkp} AS SELECT * FROM public.sisateg_receita_despesa WHERE dt_referencia >= %s", (ini,))
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'sisateg_receita_despesa_bkp_%' ORDER BY 1 DESC OFFSET 3")
    for (velho,) in cur.fetchall():
        cur.execute(f"DROP TABLE public.{velho}")
    print(f"  cópia de segurança da janela: public.{bkp}")
    cur.execute("DELETE FROM public.sisateg_receita_despesa WHERE dt_referencia >= %s", (ini,))
    cur.execute("INSERT INTO public.sisateg_receita_despesa SELECT * FROM public.sisateg_receita_despesa_novo WHERE dt_referencia >= %s", (ini,))
    cur.execute("DROP TABLE IF EXISTS public.sisateg_receita_despesa_novo")
    con.commit()
    cur.execute("SELECT MAX(dt_referencia) FROM public.sisateg_receita_despesa")
    print(f"  {n_novo} linhas na janela. Última dt_referencia: {cur.fetchone()[0]}")
    con.close()


def sql_parcial(sql, ini):
    """Versão do SQL que recalcula só os meses >= ini e troca só essas linhas nas 3 tabelas (o histórico antigo fica como está)."""
    ym = ini[:7]
    def troca(txt, a, b, n=1):
        assert txt.count(a) == n, f"trecho do SQL não encontrado ({txt.count(a)}x): {a[:60]}"
        return txt.replace(a, b)
    # não filtra por data do item antes: itens com data antiga podem pertencer a uma visita do mês (o corte é feito depois de mover pelo mês da visita)
    sql = troca(sql, "CREATE INDEX ON tmp_base (id_propriedade, id_visita);",
                f"DELETE FROM tmp_base WHERE dt_referencia < DATE '{ini}';\nCREATE INDEX ON tmp_base (id_propriedade, id_visita);")
    for t in ("resumo_leite_mensal", "resumo_despesa_subgrupo", "resumo_tipo"):
        sql = troca(sql, f"DROP TABLE IF EXISTS public.{t};\n", "")
        sql = troca(sql, f"CREATE TABLE public.{t} AS", f"DROP TABLE IF EXISTS tmp_new_{t};\nCREATE TEMP TABLE tmp_new_{t} AS")
        merge = f"DELETE FROM public.{t} WHERE mes >= '{ym}';\nINSERT INTO public.{t} SELECT * FROM tmp_new_{t};"
        if t == "resumo_leite_mensal":
            sql = troca(sql, "CREATE INDEX ON public.resumo_leite_mensal (id_propriedade);", merge)
            sql = troca(sql, "CREATE INDEX ON public.resumo_leite_mensal (tecnico);\n", "")
            sql = troca(sql, "CREATE INDEX ON public.resumo_leite_mensal (mes);\n", "")
        else:
            sql = troca(sql, f"CREATE INDEX ON public.{t} (id_propriedade, mes);", merge)
    return sql


def criar_resumo(ini=None):
    con = local()
    cur = con.cursor()
    import re
    sql = (RAIZ / "sql" / "criar_resumo_leite_mensal.sql").read_text(encoding="utf-8")
    if ini:
        cur.execute("""SELECT to_regclass('public.resumo_leite_mensal') IS NOT NULL AND to_regclass('public.resumo_despesa_subgrupo') IS NOT NULL
                          AND to_regclass('public.resumo_tipo') IS NOT NULL""")
        if cur.fetchone()[0]:
            sql = sql_parcial(sql, ini)
            print(f"\n=== 3/5: recalculando o resumo do leite só de {ini[:7]} em diante (o histórico antigo fica como está) ===", flush=True)
        else:
            ini = None
    if not ini:
        print("\n=== 3/5: recriando o resumo do leite COMPLETO, todos os meses (leva alguns minutos) ===", flush=True)
    for parte in re.split(r";[ \t]*(?:--[^\n]*)?\n", sql):
        corpo = "\n".join(l for l in parte.splitlines() if l.strip() and not l.strip().startswith("--")).strip()
        if not corpo:
            continue
        t1 = time.time()
        cur.execute(parte.replace("%", "%%"))
        nome = " ".join(corpo.split())[:70]
        seg = time.time() - t1
        print(f"  [{seg:6.1f}s] {nome}", flush=True)
    con.commit()
    cur.execute("""SELECT (SELECT COUNT(*) FROM public.resumo_propriedades), (SELECT COUNT(DISTINCT id_propriedade) FROM public.resumo_leite_mensal),
                          (SELECT COUNT(*) FROM public.resumo_leite_mensal), (SELECT MAX(mes) FROM public.resumo_leite_mensal)""")
    p, c, l, m = cur.fetchone()
    print(f"  propriedades: {p} | com leite: {c} | linhas mensais: {l} | último mês: {m}")
    con.close()


def rodar_opcional(titulo, cmd):
    print(f"\n=== {titulo} ===", flush=True)
    if subprocess.run(cmd, cwd=str(RAIZ)).returncode != 0:
        print("AVISO: não atualizou; o resumo segue com a versão anterior dessas tabelas (não impede o restante).")


def main():
    t0 = time.time()
    py = sys.executable
    rapido = "--rapido" in sys.argv or ("--so-resumo" in sys.argv and "--completo" not in sys.argv)
    dias = DIAS_RAPIDO if rapido else DIAS
    ini = (date.today() - timedelta(days=dias)).replace(day=1).isoformat()
    desde = None
    if "--desde" in sys.argv:   # recarrega a história da fonte a partir de uma data (pega itens lançados depois em meses antigos); recalcula tudo
        desde = sys.argv[sys.argv.index("--desde") + 1]
        date.fromisoformat(desde)
        ini = desde
        rapido = False
    print(f"Modo {'RECARGA DA HISTÓRIA (indicadores pulados)' if desde else 'RÁPIDO (mês atual + mês anterior; sem recarregar os indicadores)' if rapido else 'COMPLETO'}: recarrega a partir de {ini}.")
    if "--so-resumo" in sys.argv:   # pula as cargas (1 e 2): só recalcula o resumo (mostra o tempo de cada comando) e copia para o servidor
        criar_resumo(ini if rapido else None)
        rodar("5/5: copiando para o servidor e recriando as views", [py, "scripts/transferir_resumo.py"])
        print(f"\nPronto em {int(time.time() - t0)} s. Abra o painel na Vercel e dê Ctrl+F5.")
        return
    rodar("1/5: receita (API -> local)", [py, "scripts/carga_incremental.py", "sisateg_receita", "--desde", ini])
    rodar("1/5: despesa (API -> local)", [py, "scripts/carga_incremental.py", "sisateg_despesa", "--desde", ini])
    if rapido or desde:
        print("\n=== 1/5: indicadores mensais: PULADO (rode o completo de vez em quando) ===")
    else:
        rodar_opcional("1/5: indicadores mensais (nome da propriedade e conferência)", [py, "scripts/carga_indicadores_mensais.py"])
    refazer_receita_despesa(ini)
    criar_resumo(ini if rapido else None)
    if (INTEGRACAO / "sincronizar_municipios.py").exists():
        rodar("4/5: regiões e sindicatos (Supabase -> servidor)", [py, str(INTEGRACAO / "sincronizar_municipios.py")], cwd=INTEGRACAO)
    else:
        print("\n(sincronizar_municipios.py não encontrado: a Região só aparece se municipio_regiao já estiver no servidor)")
    rodar("5/5: copiando para o servidor e recriando as views", [py, "scripts/transferir_resumo.py"])
    print(f"\nPronto em {int(time.time() - t0)} s. Abra o painel na Vercel e dê Ctrl+F5.")


if __name__ == "__main__":
    main()
