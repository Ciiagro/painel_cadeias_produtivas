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


def _where(supervisor=None, tecnico=None, projeto=None, propriedade=None, situacao=None, municipio=None):
    """Monta WHERE + parâmetros para os filtros (mesmas colunas nas duas views)."""
    w, p = ["1=1"], {}
    if supervisor:
        w.append("supervisor = :s"); p["s"] = supervisor
    if tecnico:
        w.append("tecnico = :t"); p["t"] = tecnico
    if projeto:
        w.append("projeto = :pj"); p["pj"] = projeto
    if propriedade:
        w.append("id_propriedade = :pr"); p["pr"] = propriedade
    if municipio:
        w.append("municipio = :mu"); p["mu"] = municipio
    if situacao == "ativa":
        w.append("ativa")
    elif situacao == "inativa":
        w.append("NOT ativa")
    return w, p


@app.get("/api/filtros")
def filtros(supervisor: str | None = None, tecnico: str | None = None, projeto: str | None = None,
            municipio: str | None = None, situacao: str | None = None):
    """Listas dos filtros. Cada lista respeita TODOS os outros filtros já escolhidos (filtros em cascata)."""
    escolhidos = {"supervisor": supervisor, "tecnico": tecnico, "projeto": projeto, "municipio": municipio}
    with engine.connect() as con:
        def lista(coluna):
            outros = {k: v for k, v in escolhidos.items() if k != coluna}
            w, p = _where(situacao=situacao, **outros)
            w.append(f"{coluna} IS NOT NULL")
            return [r[0] for r in con.execute(text(
                f"SELECT DISTINCT {coluna} FROM {TABLE} WHERE {' AND '.join(w)} ORDER BY 1"), p)]
        projetos, sups, tecs, muns = lista("projeto"), lista("supervisor"), lista("tecnico"), lista("municipio")
        w2, p2 = _where(supervisor, tecnico, projeto, None, situacao, municipio)
        props = [{"id": r[0], "nome": r[1]} for r in con.execute(text(
            f"SELECT DISTINCT id_propriedade, COALESCE(propriedade, 'Propriedade ' || id_propriedade) "
            f"FROM {TABLE} WHERE {' AND '.join(w2)} ORDER BY 2"), p2)]
        meses = [r[0] for r in con.execute(text(f"SELECT DISTINCT mes FROM {TABLE} WHERE mes >= :mi ORDER BY 1"), {"mi": MES_INICIO})]
    return {"projetos": projetos, "supervisores": sups, "tecnicos": tecs, "municipios": muns, "propriedades": props, "meses": meses}


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
          projeto: str | None = None, situacao: str | None = None, municipio: str | None = None,
          de: str | None = Query(None, description="YYYY-MM"), ate: str | None = Query(None, description="YYYY-MM")):
    where, p = _where(supervisor, tecnico, projeto, propriedade, situacao, municipio)
    p["de"] = max(de or MES_INICIO, MES_INICIO)
    where.append("mes >= :de")
    if ate:
        where.append("mes <= :ate"); p["ate"] = ate
    sql = f"""
        SELECT mes,
               COUNT(DISTINCT id_propriedade)           AS propriedades,
               COALESCE(SUM(producao_leite_l), 0)       AS producao,
               COALESCE(SUM(receita_bruta), 0)          AS receita_bruta,
               COALESCE(SUM(venda_leite_rs), 0)         AS venda_leite,
               COALESCE(SUM(despesa_direta), 0)         AS despesa_direta,
               COALESCE(SUM(COALESCE(receita_bruta,0) - COALESCE(despesa_direta,0)), 0) AS margem_bruta,
               COALESCE(SUM(COALESCE(venda_leite_rs,0) - COALESCE(despesa_direta,0)), 0) AS margem_leite,
               COUNT(DISTINCT produtor)                 AS produtores
        FROM {TABLE} WHERE {' AND '.join(where)}
        GROUP BY mes ORDER BY mes"""
    wp, pp = _where(supervisor, tecnico, projeto, propriedade, None, municipio)
    # o card conta as propriedades ativas hoje; no filtro 'Inativas' conta as inativas
    wp.append("NOT ativa" if situacao == "inativa" else "ativa")
    with engine.connect() as con:
        rows = [dict(r._mapping) for r in con.execute(text(sql), p)]
        total_props = con.execute(text(f"SELECT COUNT(DISTINCT id_propriedade) FROM {PROPS} WHERE {' AND '.join(wp)}"), pp).scalar()
    for r in rows:
        r["propriedades_total"] = int(total_props or 0)
    prev = None
    for r in rows:
        for k in ("producao", "receita_bruta", "venda_leite", "despesa_direta", "margem_bruta", "margem_leite"):
            r[k] = float(r[k])
        r["producao_media_produtor"] = round(r["producao"] / r["produtores"], 1) if r["produtores"] else 0
        r["var_receita_pct"] = None if not prev or not prev["receita_bruta"] else round((r["receita_bruta"] / prev["receita_bruta"] - 1) * 100, 1)
        r["var_venda_leite_pct"] = None if not prev or not prev["venda_leite"] else round((r["venda_leite"] / prev["venda_leite"] - 1) * 100, 1)
        r["var_despesa_pct"] = None if not prev or not prev["despesa_direta"] else round((r["despesa_direta"] / prev["despesa_direta"] - 1) * 100, 1)
        r["var_producao_pct"] = None if not prev or not prev["producao"] else round((r["producao"] / prev["producao"] - 1) * 100, 1)
        r["var_margem_pct"] = None if not prev or not prev["margem_bruta"] else round((r["margem_bruta"] / abs(prev["margem_bruta"]) - 1) * 100, 1)
        r["var_margem_leite_pct"] = None if not prev or not prev["margem_leite"] else round((r["margem_leite"] / abs(prev["margem_leite"]) - 1) * 100, 1)
        r["var_prod_media_pct"] = None if not prev or not prev["producao_media_produtor"] else round((r["producao_media_produtor"] / prev["producao_media_produtor"] - 1) * 100, 1)
        prev = r
    return rows


@app.get("/api/destaques")
def destaques(supervisor: str | None = None, tecnico: str | None = None, propriedade: int | None = None,
              projeto: str | None = None, situacao: str | None = None, municipio: str | None = None,
              ate: str | None = Query(None, description="YYYY-MM"),
              de: str | None = Query(None, description="YYYY-MM")):
    """Destaques automáticos do mês de referência (por regras, sem IA): comparam o mês com o anterior,
    dentro dos filtros escolhidos. Se o último mês ainda está em andamento, usa o mês anterior (fechado)."""
    from datetime import date
    where, p = _where(supervisor, tecnico, projeto, propriedade, situacao, municipio)
    wsql = " AND ".join(where)
    sub = {"mi": MES_INICIO}
    sql_m = f"SELECT DISTINCT mes FROM {TABLE} WHERE mes >= :mi "
    if ate:
        sql_m += "AND mes <= :ate "; sub["ate"] = ate
    sql_m += "ORDER BY mes DESC LIMIT 4"
    with engine.connect() as con:
        meses = [r[0] for r in con.execute(text(sql_m), sub)]
        if not meses:
            return {}
        parcial = meses[0] == date.today().strftime("%Y-%m") and len(meses) > 1
        i = 1 if parcial else 0
        m = meses[i]
        a = meses[i + 1] if len(meses) > i + 1 else None
        if de and de < m:  # período escolhido: compara o mês final com o primeiro mês com dados do período
            a0 = con.execute(text(f"SELECT MIN(mes) FROM {TABLE} WHERE mes >= :mi AND mes >= :de AND mes < :m"),
                             {"mi": MES_INICIO, "de": de, "m": m}).scalar()
            if a0:
                a = a0
        pm = {**p, "m": m, "a": a or "0000-00"}
        t = con.execute(text(f"""
            SELECT COALESCE(SUM(receita_bruta) FILTER (WHERE mes = :m), 0)  AS rb,
                   COALESCE(SUM(receita_bruta) FILTER (WHERE mes = :a), 0)  AS rb_a,
                   COALESCE(SUM(producao_leite_l) FILTER (WHERE mes = :m), 0) AS pr,
                   COALESCE(SUM(producao_leite_l) FILTER (WHERE mes = :a), 0) AS pr_a,
                   COALESCE(SUM(COALESCE(receita_bruta,0) - COALESCE(despesa_direta,0)) FILTER (WHERE mes = :m), 0) AS mg,
                   COALESCE(SUM(COALESCE(receita_bruta,0) - COALESCE(despesa_direta,0)) FILTER (WHERE mes = :a), 0) AS mg_a
            FROM {TABLE} WHERE {wsql} AND mes IN (:m, :a)"""), pm).mappings().first()
        out = {"mes": m, "anterior": a, "parcial_ignorado": parcial,
               "total": {k: float(v) for k, v in dict(t).items()}, "entidade": None}
        if propriedade:   # uma propriedade só: não há ranking a mostrar
            return out
        if tecnico:
            ent_sql = "COALESCE(propriedade, 'Propriedade ' || id_propriedade) || COALESCE(' - ' || produtor, '')"
            out["entidade"] = "propriedade"
        else:
            ent_sql = "tecnico"
            out["entidade"] = "técnico"
        rows = [dict(r._mapping) for r in con.execute(text(f"""
            SELECT {ent_sql} AS nome,
                   COALESCE(SUM(receita_bruta) FILTER (WHERE mes = :m), 0) AS rb,
                   COALESCE(SUM(receita_bruta) FILTER (WHERE mes = :a), 0) AS rb_a,
                   COALESCE(SUM(producao_leite_l) FILTER (WHERE mes = :m), 0) AS pr,
                   COALESCE(SUM(producao_leite_l) FILTER (WHERE mes = :a), 0) AS pr_a
            FROM {TABLE} WHERE {wsql} AND mes IN (:m, :a) GROUP BY 1"""), pm) if r[0] is not None]

        def ranking(campo, ant, n=3):
            itens = [{"nome": r["nome"], "atual": float(r[campo]), "anterior": float(r[ant]),
                      "delta": float(r[campo]) - float(r[ant])} for r in rows]
            for it in itens:
                it["pct"] = round(it["delta"] / it["anterior"] * 100, 1) if it["anterior"] else None
            quedas = sorted([x for x in itens if x["delta"] < 0], key=lambda x: x["delta"])[:n]
            altas = sorted([x for x in itens if x["delta"] > 0], key=lambda x: -x["delta"])[:n]
            return {"quedas": quedas, "altas": altas}
        out["receita"] = ranking("rb", "rb_a")
        out["producao"] = ranking("pr", "pr_a")

        props = [dict(r._mapping) for r in con.execute(text(f"""
            SELECT id_propriedade, MAX(propriedade) AS nome, MAX(produtor) AS produtor, MAX(tecnico) AS tecnico,
                   COALESCE(SUM(COALESCE(receita_bruta,0) - COALESCE(despesa_direta,0)) FILTER (WHERE mes = :m), 0) AS mg,
                   COALESCE(SUM(receita_bruta) FILTER (WHERE mes = :m), 0) AS rb,
                   COALESCE(SUM(producao_leite_l) FILTER (WHERE mes = :m), 0) AS pr,
                   COALESCE(SUM(producao_leite_l) FILTER (WHERE mes = :a), 0) AS pr_a,
                   COALESCE(SUM(receita_bruta) FILTER (WHERE mes = :a), 0) AS rb_a,
                   MAX(CASE WHEN ativa THEN 1 ELSE 0 END) AS ativa_n,
                   MAX(fim_projeto) AS fim, MAX(motivo_desativacao) AS motivo
            FROM {TABLE} WHERE {wsql} AND mes IN (:m, :a) GROUP BY id_propriedade"""), pm)]

        def rot(x):
            return (x["nome"] or f"Propriedade {x['id_propriedade']}") + (f" - {x['produtor']}" if x["produtor"] else "")
        neg = sorted([x for x in props if float(x["mg"]) < 0 and float(x["pr"]) > 0], key=lambda x: float(x["mg"]))
        out["margem_negativa"] = {"total": len(neg), "lista": [
            {"nome": rot(x), "tecnico": x["tecnico"], "valor": float(x["mg"])} for x in neg[:5]]}
        par = sorted([x for x in props if float(x["pr_a"]) > 0 and float(x["pr"]) == 0], key=lambda x: -float(x["rb_a"]))
        out["pararam"] = {"total": len(par), "lista": [
            {"nome": rot(x), "tecnico": x["tecnico"], "valor": float(x["rb_a"]), "litros": float(x["pr_a"]),
             "ativa": bool(x["ativa_n"]), "fim": (str(x["fim"])[:10] if x["fim"] else None), "motivo": x["motivo"]}
            for x in par[:6]]}

        # Por que a receita e a produção mudaram: separa o efeito de quem saiu, de quem entrou,
        # da variação de litros e da variação de receita por litro nas propriedades que continuam.
        b = {"saidas": [0.0, 0.0, 0], "entradas": [0.0, 0.0, 0], "volume": [0.0, 0.0, 0], "preco": [0.0, 0.0, 0], "outros": [0.0, 0.0, 0]}
        for x in props:
            rb, rb_a, pr, pr_a = float(x["rb"]), float(x["rb_a"]), float(x["pr"]), float(x["pr_a"])
            if pr_a > 0 and pr > 0:
                p_a, p_n = rb_a / pr_a, rb / pr
                b["volume"][0] += (pr - pr_a) * p_a; b["volume"][1] += pr - pr_a; b["volume"][2] += 1
                b["preco"][0] += (p_n - p_a) * pr; b["preco"][2] += 1
            elif pr_a > 0 and pr == 0:
                b["saidas"][0] += rb - rb_a; b["saidas"][1] += -pr_a; b["saidas"][2] += 1
            elif pr_a == 0 and pr > 0:
                b["entradas"][0] += rb - rb_a; b["entradas"][1] += pr; b["entradas"][2] += 1
            else:
                b["outros"][0] += rb - rb_a
        out["explicacao"] = {k: {"receita": round(v[0], 2), "litros": round(v[1], 1), "qtd": v[2]} for k, v in b.items()}
        qd = sorted([x for x in props if float(x["pr_a"]) >= 500 and 0 < float(x["pr"]) < float(x["pr_a"]) * 0.8],
                    key=lambda x: float(x["pr"]) - float(x["pr_a"]))
        out["queda_forte_producao"] = {"total": len(qd), "lista": [
            {"nome": rot(x), "tecnico": x["tecnico"], "atual": float(x["pr"]), "anterior": float(x["pr_a"]),
             "pct": round((float(x["pr"]) / float(x["pr_a"]) - 1) * 100, 1)} for x in qd[:5]]}
    return out

DESP = os.environ.get("DESP_NAME", "public.vw_despesa_subgrupo")


@app.get("/api/causas")
def causas(supervisor: str | None = None, tecnico: str | None = None, propriedade: int | None = None,
           projeto: str | None = None, situacao: str | None = None, municipio: str | None = None,
           de: str | None = Query(None, description="YYYY-MM"), ate: str | None = Query(None, description="YYYY-MM")):
    """Aba 'Causas' (por regras, sem IA): quando as propriedades entraram/saíram, preço do leite fora do normal
    e despesa direta por subgrupo. Tudo dentro dos filtros escolhidos."""
    from datetime import date
    where, p = _where(supervisor, tecnico, projeto, propriedade, situacao, municipio)
    wsql = " AND ".join(where)
    pp = {**p, "mi": MES_INICIO}
    cate = ""
    if ate:
        cate = " AND mes <= :ate"; pp["ate"] = ate
    de_ = max(de or MES_INICIO, MES_INICIO)
    with engine.connect() as con:
        meses = [r[0] for r in con.execute(text(f"SELECT DISTINCT mes FROM {TABLE} WHERE {wsql} AND mes >= :mi{cate} ORDER BY mes"), pp)]
        if not meses:
            return {}
        # mês de referência = último mês fechado da BASE TODA (não do filtro): assim, ao filtrar só as inativas,
        # quem parou de lançar continua aparecendo como "saída". Se o mais recente é o mês atual, usa o anterior.
        gl = [r[0] for r in con.execute(text(f"SELECT DISTINCT mes FROM {TABLE} WHERE mes >= :mi{cate} ORDER BY mes DESC LIMIT 2"),
                                          {k: v for k, v in pp.items() if k in ("mi", "ate")})]
        m = gl[0]
        if m == date.today().strftime("%Y-%m") and len(gl) > 1:
            m = gl[1]
        meses = [x for x in meses if x <= m]
        if not meses:
            return {}
        no_periodo = [x for x in meses if x >= de_]
        if de and de < m and no_periodo and no_periodo[0] < m:
            a = no_periodo[0]
        else:
            a = meses[-2] if len(meses) > 1 else None
        pp["m"] = m

        # ---- 1) Entradas e saídas (primeiro/último mês com leite de cada propriedade)
        base = f"""SELECT id_propriedade, propriedade, tecnico, ativa, fim_projeto, motivo_desativacao, mes,
                          producao_leite_l AS pr, receita_bruta AS rb
                   FROM {TABLE} WHERE {wsql} AND mes >= :mi AND mes <= :m"""
        ult = con.execute(text(f"""SELECT id_propriedade, propriedade, tecnico, ativa, fim_projeto, motivo_desativacao, mes, rb FROM (
                 SELECT b.*, ROW_NUMBER() OVER (PARTITION BY id_propriedade ORDER BY mes DESC) AS rn
                 FROM ({base}) b WHERE pr > 0) x WHERE rn = 1"""), pp).mappings().all()
        pri = con.execute(text(f"""SELECT id_propriedade, propriedade, tecnico, mes, rb FROM (
                 SELECT b.*, ROW_NUMBER() OVER (PARTITION BY id_propriedade ORDER BY mes ASC) AS rn
                 FROM ({base}) b WHERE pr > 0) x WHERE rn = 1"""), pp).mappings().all()
        primeiro_mes_base = meses[0]
        saidas = [r for r in ult if r["mes"] < m and r["mes"] >= de_]
        entradas = [r for r in pri if r["mes"] >= de_ and r["mes"] > primeiro_mes_base]

        def por_mes(linhas):
            d = {}
            for r in linhas:
                x = d.setdefault(r["mes"], {"mes": r["mes"], "qtd": 0, "receita": 0.0})
                x["qtd"] += 1; x["receita"] += float(r["rb"] or 0)
            return [d[k] for k in sorted(d)]

        def lista(linhas, saida):
            out = []
            for r in sorted(linhas, key=lambda r: -(float(r["rb"] or 0)))[:12]:
                o = {"nome": r["propriedade"], "tecnico": r["tecnico"], "mes": r["mes"], "receita": float(r["rb"] or 0)}
                if saida:
                    o["ativa"] = bool(r["ativa"]); o["motivo"] = r["motivo_desativacao"]
                    o["fim"] = str(r["fim_projeto"]) if r["fim_projeto"] else None
                out.append(o)
            return out

        mov = {"saidas": {"total": len(saidas), "receita": sum(float(r["rb"] or 0) for r in saidas),
                          "por_mes": por_mes(saidas), "lista": lista(saidas, True)},
               "entradas": {"total": len(entradas), "receita": sum(float(r["rb"] or 0) for r in entradas),
                            "por_mes": por_mes(entradas), "lista": lista(entradas, False)}}

        # ---- 2) Preço do leite (venda de leite + bonificação ÷ litros vendidos)
        # Mesmo cálculo do SisATeG: preço de cada propriedade no mês = leite in natura (R$) ÷ litros vendidos
        # (SEM a bonificação) e, depois, a MÉDIA SIMPLES entre as propriedades.
        por_mes_p = {}
        for r in con.execute(text(f"""SELECT mes, id_propriedade, propriedade, tecnico, SUM(leite_in_natura_rs) AS rs, SUM(leite_vendido_l) AS l
                 FROM {TABLE} WHERE {wsql} AND mes >= :mi AND mes <= :m AND leite_vendido_l > 0
                 GROUP BY mes, id_propriedade, propriedade, tecnico"""), pp).mappings():
            if r["l"] and float(r["l"]) > 0 and r["rs"] is not None:
                por_mes_p.setdefault(r["mes"], []).append(r)
        serie_preco = []
        for mes_ in sorted(por_mes_p):
            if mes_ >= de_:
                ps = [float(x["rs"]) / float(x["l"]) for x in por_mes_p[mes_]]
                serie_preco.append({"mes": mes_, "preco": sum(ps) / len(ps)})
        props = por_mes_p.get(m, [])
        media = (sum(float(r["rs"]) / float(r["l"]) for r in props) / len(props)) if props else None
        fora = []
        if media and len(props) > 1:
            for r in props:
                pr_ = float(r["rs"]) / float(r["l"])
                dev = (pr_ / media - 1) * 100
                if abs(dev) >= 15:
                    fora.append({"nome": r["propriedade"], "tecnico": r["tecnico"], "preco": pr_, "dev": round(dev, 1), "litros": float(r["l"])})
        acima = sorted([x for x in fora if x["dev"] > 0], key=lambda x: -x["dev"])[:8]
        abaixo = sorted([x for x in fora if x["dev"] < 0], key=lambda x: x["dev"])[:8]
        preco = {"serie": serie_preco, "media": media, "mes": m, "acima": acima, "abaixo": abaixo, "total_fora": len(fora), "n": len(props)}

        # ---- 3) Despesa direta por subgrupo
        pd_ = {**p, "mi": MES_INICIO, "m": m, "a": a or "0000-00", "de": de_}
        rows = con.execute(text(f"""SELECT subgrupo,
                   COALESCE(SUM(valor) FILTER (WHERE mes >= :de AND mes <= :m), 0) AS total,
                   COALESCE(SUM(valor) FILTER (WHERE mes = :m), 0) AS vm,
                   COALESCE(SUM(valor) FILTER (WHERE mes = :a), 0) AS va
                 FROM {DESP} WHERE {wsql} AND mes >= :mi AND mes <= :m GROUP BY subgrupo"""), pd_).mappings().all()
        rows = sorted(rows, key=lambda r: -float(r["total"] or 0))
        tot_geral = sum(float(r["total"] or 0) for r in rows) or 1
        desp = [{"nome": r["subgrupo"], "total": float(r["total"] or 0), "pct": float(r["total"] or 0) / tot_geral * 100,
                 "vm": float(r["vm"] or 0), "va": float(r["va"] or 0)} for r in rows if float(r["total"] or 0) > 0]
    return {"mes": m, "anterior": a, "de": de_, "movimento": mov, "preco": preco,
            "despesa": {"total": tot_geral if desp else 0, "itens": desp}}



@app.get("/health")
def health():
    return {"ok": True}
