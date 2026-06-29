#!/usr/bin/env python3
"""
WC2026 backend — re-entrenamiento del modelo att/def con DECAIMIENTO TEMPORAL.
Pipeline: baja resultados internacionales (1872→hoy, incluye WC2026),
pondera por recencia (half-life configurable) + boost a torneos mayores,
ajusta un Poisson ataque/defensa por equipo (IRLS) y aproxima la posterior
por Laplace (Hessiano cerrado) → exporta POST.json con N draws.
Uso:  python3 retrain.py [half_life_years] [n_draws]
"""
import csv, sys, json, datetime as dt, urllib.request, numpy as np

HALFLIFE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5
NDRAW    = int(sys.argv[2])   if len(sys.argv) > 2 else 400
RIDGE    = 6.0          # fuerza del prior gaussiano (shrinkage jerárquico)
DATA_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"

TEAMS = ["Algeria","Argentina","Australia","Austria","Belgium","Bosnia and Herzegovina","Brazil","Cabo Verde","Canada","Colombia","Croatia","Curaçao","Czechia","Côte d'Ivoire","DR Congo","Ecuador","Egypt","England","France","Germany","Ghana","Haiti","Iran","Iraq","Japan","Jordan","Mexico","Morocco","Netherlands","New Zealand","Norway","Panama","Paraguay","Portugal","Qatar","Saudi Arabia","Scotland","Senegal","South Africa","South Korea","Spain","Sweden","Switzerland","Tunisia","Türkiye","USA","Uruguay","Uzbekistan"]
ALIAS = {"Cape Verde":"Cabo Verde","Czech Republic":"Czechia","Ivory Coast":"Côte d'Ivoire","Turkey":"Türkiye","United States":"USA","DR Congo":"DR Congo","Congo DR":"DR Congo"}
TI = {t:i for i,t in enumerate(TEAMS)}
N  = len(TEAMS)
def norm(x): return ALIAS.get(x, x)

def load():
    try:
        req = urllib.request.Request(DATA_URL, headers={'User-Agent':'Mozilla/5.0'})
        raw = urllib.request.urlopen(req, timeout=30).read().decode()
        rows = list(csv.DictReader(raw.splitlines()))
        print(f"[data] {len(rows)} partidos, último {max(r['date'] for r in rows)}")
        return rows
    except Exception as e:
        sys.exit(f"[error] no pude bajar el dataset: {e}")

def build(rows):
    ref = dt.date.today()
    X=[]; y=[]; w=[]
    BIG = ("FIFA World Cup","Copa América","UEFA Euro","African Cup","Gold Cup",
           "AFC Asian Cup","Confederations","UEFA Nations","Finalissima")
    P = 2 + 2*N                       # [base, home_adv, att(N), def(N)]
    for r in rows:
        h, a = norm(r["home_team"]), norm(r["away_team"])
        if h not in TI or a not in TI: continue
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
            d = dt.date.fromisoformat(r["date"])
        except: continue
        age = (ref - d).days/365.25
        wt  = 0.5 ** (age/HALFLIFE)
        if any(b in r["tournament"] for b in BIG): wt *= 1.6
        # WC2026 in-tournament results carry 10x extra signal
        if d.year == 2026 and "FIFA World Cup" in r["tournament"]: wt *= 10.0
        neutral = r["neutral"].upper()=="TRUE"
        hi, ai = TI[h], TI[a]
        # fila goles local: base + home_adv(si no neutral) + att_h - def_a
        rowH = np.zeros(P); rowH[0]=1
        if not neutral: rowH[1]=1
        rowH[2+hi]=1; rowH[2+N+ai]=-1
        X.append(rowH); y.append(hs); w.append(wt)
        # fila goles visita: base + att_a - def_h
        rowA = np.zeros(P); rowA[0]=1
        rowA[2+ai]=1; rowA[2+N+hi]=-1
        X.append(rowA); y.append(as_); w.append(wt)
    return np.array(X), np.array(y,float), np.array(w), P

def fit(X, y, w, P):
    beta = np.zeros(P)
    ridge = np.ones(P)*RIDGE; ridge[0]=0; ridge[1]=0   # no penalizar base ni home_adv
    R = np.diag(ridge)
    for it in range(60):
        eta = X@beta; mu = np.exp(np.clip(eta,-6,6))
        g = X.T@(w*(y-mu)) - ridge*beta
        W = w*mu
        H = (X.T*W)@X + R
        step = np.linalg.solve(H, g)
        beta += step
        if np.max(np.abs(step)) < 1e-7:
            print(f"[fit] convergió en {it+1} iters"); break
    cov = np.linalg.inv(H)
    return beta, cov

def export(beta, cov):
    L = np.linalg.cholesky(cov + 1e-9*np.eye(len(beta)))
    draws = beta + (L @ np.random.standard_normal((len(beta), NDRAW))).T  # NDRAW x P
    base = draws[:,0]; home = draws[:,1]
    att  = draws[:,2:2+N].T          # N x NDRAW
    deff = draws[:,2+N:2+2*N].T
    POST = {"teams":TEAMS,
            "att":[[round(float(v),4) for v in att[i]] for i in range(N)],
            "deff":[[round(float(v),4) for v in deff[i]] for i in range(N)],
            "base":[round(float(v),4) for v in base],
            "home_adv":[round(float(v),4) for v in home]}
    import os
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "POST.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(POST, open(out, "w"))
    # ranking sanity
    s = att.mean(1)+deff.mean(1)
    order = np.argsort(-s)
    print("[rank] top10:", ", ".join(f"{TEAMS[i]} {s[i]:+.2f}" for i in order[:10]))
    print("[rank] bottom5:", ", ".join(TEAMS[i] for i in order[-5:]))
    print(f"[ok] POST.json escrito · {N} equipos × {NDRAW} draws · half-life {HALFLIFE}a")

if __name__=="__main__":
    rows = load()
    X,y,w,P = build(rows)
    print(f"[data] {len(y)//2} partidos entre las 48 selecciones · peso efectivo {w.sum():.0f}")
    beta,cov = fit(X,y,w,P)
    print(f"[fit] base={beta[0]:.3f} home_adv={beta[1]:.3f}")
    export(beta,cov)
