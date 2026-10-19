"""Painel de acompanhamento mensal por supervisor/técnico: receita bruta, produção e margem bruta.
Lê SOMENTE a view do servidor público (nunca o banco local)."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _db_url():
    """Usa DB_URL se existir; senão monta a conexão com as mesmas variáveis REMOTE_DB_* do script de cópia."""
    if os.environ.get("DB_URL") and "USUARIO_LEITURA" not in os.environ["DB_URL"]:
        return os.environ["DB_URL"]
    from sqlalchemy.engine import URL
    return URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("REMOTE_DB_USER", "postgres"),
        password=os.environ["REMOTE_DB_PASS"],
        host=os.environ["REMOTE_DB_HOST"],
        port=int(os.environ.get("REMOTE_DB_PORT", "5432")),
        database=os.environ["REMOTE_DB_NAME"],
    )


DB_URL = _db_url()
TABLE = os.environ.get("TABLE_NAME", "public.vw_resumo_leite_mensal")
PROPS = os.environ.get("PROPS_NAME", "public.vw_propriedades")
MES_INICIO = os.environ.get("MES_INICIO", "2024-06")  # início da base completa (YYYY-MM)
if not re.fullmatch(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+", TABLE):
    raise RuntimeError("TABLE_NAME inválido (use schema.nome)")

# Pool pequeno: na Vercel cada instância é efêmera; evita estourar conexões do banco.
engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=2, max_overflow=1, pool_recycle=300,
                       connect_args={"connect_timeout": 10})
app = FastAPI(title="Acompanhamento mensal das cadeias")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/filtros")
def filtros(supervisor: str | None = None, tecnico: str | None = None):
    with engine.connect() as con:
        sups = [r[0] for r in con.execute(text(
            f"SELECT DISTINCT supervisor FROM {PROPS} WHERE supervisor IS NOT NULL ORDER BY 1"))]
        w, p = ["tecnico IS NOT NULL"], {}
        if supervisor:
            w.append("supervisor = :s"); p["s"] = supervisor
        tecs = [r[0] for r in con.execute(text(
            f"SELECT DISTINCT tecnico FROM {PROPS} WHERE {' AND '.join(w)} ORDER BY 1"), p)]
        w2, p2 = ["1=1"], {}
        if supervisor:
            w2.append("supervisor = :s"); p2["s"] = supervisor
        if tecnico:
            w2.append("tecnico = :t"); p2["t"] = tecnico
        props = [{"id": r[0], "nome": r[1]} for r in con.execute(text(
            f"SELECT DISTINCT id_propriedade, COALESCE(propriedade, 'Propriedade ' || id_propriedade) "
            f"FROM {PROPS} WHERE {' AND '.join(w2)} ORDER BY 2"), p2)]
        meses = [r[0] for r in con.execute(text(f"SELECT DISTINCT mes FROM {TABLE} WHERE mes >= :mi ORDER BY 1"), {"mi": MES_INICIO})]
    return {"supervisores": sups, "tecnicos": tecs, "propriedades": props, "meses": meses}


@app.get("/api/propriedade/{id_propriedade}")
def propriedade(id_propriedade: int):
    sql = f"""SELECT DISTINCT propriedade, produtor, tecnico, supervisor, municipio, uf, projeto, qtd_projetos,
                     inicio_projeto, fim_projeto, status_vinculo, area_total, area_produtiva
              FROM {PROPS} WHERE id_propriedade = :i LIMIT 1"""
    with engine.connect() as con:
        r = con.execute(text(sql), {"i": id_propriedade}).first()
    if not r:
        return {}
    d = dict(r._mapping)
    from datetime import date
    ini, fim = d["inicio_projeto"], d["fim_projeto"]
    d["tempo_projeto_meses"] = None
    if ini:
        ate = min(fim, date.today()) if fim else date.today()
        d["tempo_projeto_meses"] = max(0, (ate.year - ini.year) * 12 + (ate.month - ini.month))
    for k in ("inicio_projeto", "fim_projeto"):
        d[k] = d[k].isoformat() if d[k] else None
    return d


@app.get("/api/serie")
def serie(supervisor: str | None = None, tecnico: str | None = None, propriedade: int | None = None,
          de: str | None = Query(None, description="YYYY-MM"), ate: str | None = Query(None, description="YYYY-MM")):
    where, p = ["1=1"], {}
    if supervisor:
        where.append("supervisor = :s"); p["s"] = supervisor
    if tecnico:
        where.append("tecnico = :t"); p["t"] = tecnico
    if propriedade:
        where.append("id_propriedade = :pr"); p["pr"] = propriedade
    p["de"] = max(de or MES_INICIO, MES_INICIO)
    where.append("mes >= :de")
    if ate:
        where.append("mes <= :ate"); p["ate"] = ate
    sql = f"""
        SELECT mes,
               COUNT(DISTINCT id_propriedade)           AS propriedades,
               COALESCE(SUM(producao_leite_l), 0)       AS producao,
               COALESCE(SUM(receita_bruta), 0)          AS receita_bruta,
               COALESCE(SUM(COALESCE(receita_bruta,0) - COALESCE(despesa_direta,0)), 0) AS margem_bruta
        FROM {TABLE} WHERE {' AND '.join(where)}
        GROUP BY mes ORDER BY mes"""
    wp, pp = ["1=1"], {}
    if supervisor:
        wp.append("supervisor = :s"); pp["s"] = supervisor
    if tecnico:
        wp.append("tecnico = :t"); pp["t"] = tecnico
    if propriedade:
        wp.append("id_propriedade = :pr"); pp["pr"] = propriedade
    with engine.connect() as con:
        rows = [dict(r._mapping) for r in con.execute(text(sql), p)]
        total_props = con.execute(text(f"SELECT COUNT(DISTINCT id_propriedade) FROM {PROPS} WHERE {' AND '.join(wp)}"), pp).scalar()
    for r in rows:
        r["propriedades_total"] = int(total_props or 0)
    prev = None
    for r in rows:
        for k in ("producao", "receita_bruta", "margem_bruta"):
            r[k] = float(r[k])
        r["var_receita_pct"] = None if not prev or not prev["receita_bruta"] else round((r["receita_bruta"] / prev["receita_bruta"] - 1) * 100, 1)
        r["var_producao_pct"] = None if not prev or not prev["producao"] else round((r["producao"] / prev["producao"] - 1) * 100, 1)
        r["var_margem_pct"] = None if not prev or not prev["margem_bruta"] else round((r["margem_bruta"] / abs(prev["margem_bruta"]) - 1) * 100, 1)
        prev = r
    return rows


@app.get("/health")
def health():
    return {"ok": True}
