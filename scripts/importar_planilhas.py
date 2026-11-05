"""Importa as planilhas mensais do SisATeG (Excel) para o banco, SEM usar a API.
Uso (na pasta do projeto):
   python scripts/importar_planilhas.py                 -> importa todos os .xlsx da pasta planilhas\\ e move para planilhas\\importadas\\
   python scripts/importar_planilhas.py "outubro.xlsx"  -> importa so esse arquivo
   opcoes: --destino LOCAL|REMOTE (padrao REMOTE = servidor painel_ateg)   --manter (nao move o arquivo depois)
Regras:
 - o mes vem das colunas Mes/Ano da propria planilha; reimportar o mesmo mes SUBSTITUI as linhas daquele mes (nao duplica);
 - Supervisor e Tecnico ficam como estao em cada linha (os da EPOCA da visita);
 - tabela criada: public.planilha_leite_mensal (uma linha por ID Visita) e a view public.vw_planilha_leite."""
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect, text

PASTA = Path(__file__).resolve().parent.parent
TABELA = "planilha_leite_mensal"
TEXTO = {"uf", "municipio", "propriedade", "produtor", "grupo", "supervisor", "tecnico", "ativ_exploratoria", "projeto", "mes", "arquivo_origem"}


def nome_coluna(c):
    s = unicodedata.normalize("NFKD", str(c)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s)).strip("_")


def ler_planilha(caminho):
    df = pd.read_excel(caminho, dtype=object)
    df.columns = [nome_coluna(c) for c in df.columns]
    for c in ("id_propriedade", "id_visita", "mes", "ano"):
        if c not in df.columns:
            raise ValueError(f"A planilha nao tem a coluna esperada: {c}")
    df["id_visita"] = pd.to_numeric(df["id_visita"], errors="coerce")
    df["id_propriedade"] = pd.to_numeric(df["id_propriedade"], errors="coerce")
    df = df[df["id_visita"].notna() & df["id_propriedade"].notna()].copy()   # tira linhas de rodape/total
    meses = (pd.to_numeric(df["ano"], errors="coerce").astype("Int64").astype(str) + "-"
             + pd.to_numeric(df["mes"], errors="coerce").astype("Int64").astype(str).str.zfill(2)).unique()
    if len(meses) != 1:
        raise ValueError(f"A planilha deve ter UM mes so; achei: {list(meses)}")
    df["mes"] = meses[0]
    df = df.drop(columns=["ano"])
    df["id_visita"] = df["id_visita"].astype("int64")
    df["id_propriedade"] = df["id_propriedade"].astype("int64")
    if "ativa" in df.columns:   # "Sim"/"Nao" -> verdadeiro/falso
        df["ativa"] = df["ativa"].astype(str).str.strip().str.lower().isin(["sim", "s", "true", "1"])
    for c in df.columns:
        if c in TEXTO:
            df[c] = df[c].astype(object).where(df[c].isna(), df[c].astype(str).str.strip())   # tira espacos e TAB no fim (ex.: "ADLER ...\t")
        elif c not in ("id_visita", "id_propriedade", "ativa"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.drop_duplicates("id_visita", keep="last")
    df["arquivo_origem"] = Path(caminho).name
    df["importado_em"] = datetime.now().replace(microsecond=0)
    return df, meses[0]


def importar(df, mes, engine):
    with engine.begin() as con:
        existe = inspect(con).has_table(TABELA)
        if existe:   # planilha nova com coluna nova: acrescenta a coluna na tabela
            atuais = {c["name"] for c in inspect(con).get_columns(TABELA)}
            for c in df.columns:
                if c not in atuais:
                    tipo = "TEXT" if c in TEXTO else ("TIMESTAMP" if c == "importado_em" else ("BOOLEAN" if c == "ativa" else "NUMERIC"))
                    con.execute(text(f'ALTER TABLE {TABELA} ADD COLUMN "{c}" {tipo}'))
            antes = con.execute(text(f"DELETE FROM {TABELA} WHERE mes = :m"), {"m": mes}).rowcount
        else:
            antes = 0
        df.to_sql(TABELA, con, if_exists="append", index=False, method="multi", chunksize=300)
        con.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{TABELA}_visita ON {TABELA} (id_visita)"))
        con.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{TABELA}_mes ON {TABELA} (mes)"))
    return antes


def criar_view(engine):
    """View para o painel: uma linha por visita, com os mesmos nomes de filtro do painel (receita e despesa como no SisATeG)."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as con:
        con.execute(text("DROP VIEW IF EXISTS public.vw_planilha_leite"))
        con.execute(text(f"""CREATE VIEW public.vw_planilha_leite AS
            SELECT id_propriedade, id_visita, mes, propriedade, produtor, municipio, uf, supervisor, tecnico, projeto, ativa,
                   producao_leite_mes AS producao_leite_l, receitas AS receita, receitas_venda_leite AS venda_leite_rs,
                   despesas_diretas AS despesa_direta, (COALESCE(receitas,0) - COALESCE(despesas_diretas,0)) AS margem_bruta
            FROM public.{TABELA}"""))


def main():
    args = [a for a in sys.argv[1:]]
    destino = "REMOTE"
    if "--destino" in args:
        i = args.index("--destino"); destino = args[i + 1].upper(); del args[i:i + 2]
    manter = "--manter" in args
    args = [a for a in args if a != "--manter"]
    arquivos = [Path(a) for a in args] or sorted((PASTA / "planilhas").glob("*.xlsx"))
    arquivos = [a for a in arquivos if not a.name.startswith("~$")]
    if not arquivos:
        sys.exit("Nenhuma planilha. Coloque os .xlsx do SisATeG na pasta 'planilhas' (ou informe o arquivo).")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from transferir_resumo import eng   # noqa: E402
    engine = eng(destino)
    for a in arquivos:
        try:
            df, mes = ler_planilha(a)
            subst = importar(df, mes, engine)
            print(f"OK  {a.name}: mes {mes}, {len(df)} visitas, {df['id_propriedade'].nunique()} propriedades"
                  + (f" (substituiu {subst} linhas do mes)" if subst else ""))
            if not manter and a.parent == PASTA / "planilhas":
                (PASTA / "planilhas" / "importadas").mkdir(exist_ok=True)
                shutil.move(str(a), str(PASTA / "planilhas" / "importadas" / a.name))
        except Exception as ex:
            print(f"ERRO {a.name}: {ex}")
    criar_view(engine)
    with engine.connect() as con:
        for r in con.execute(text(f"SELECT mes, COUNT(*) v, COUNT(DISTINCT id_propriedade) p, ROUND(SUM(receitas)::numeric,2) rec, ROUND(SUM(despesas_diretas)::numeric,2) dsp FROM {TABELA} GROUP BY mes ORDER BY mes")
                              if engine.dialect.name == "postgresql" else
                              text(f"SELECT mes, COUNT(*) v, COUNT(DISTINCT id_propriedade) p, ROUND(SUM(receitas),2) rec, ROUND(SUM(despesas_diretas),2) dsp FROM {TABELA} GROUP BY mes ORDER BY mes")):
            print(f"  {r[0]}: {r[1]} visitas | {r[2]} propriedades | receitas {r[3]} | despesas diretas {r[4]}")


if __name__ == "__main__":
    main()
