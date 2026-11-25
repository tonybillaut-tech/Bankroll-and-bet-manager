import pandas as pd
import numpy as np
from scipy.optimize import minimize
import requests, json, os, urllib3, math, base64, io
import streamlit as st

urllib3.disable_warnings()

REPO_NAME = "Bankroll-and-bet-manager"
DB_FILE = "smartstake_users.json"
GH_API = f"https://github.com{REPO_NAME}/contents/{DB_FILE}"

FD_TOKEN = st.secrets.get("FD_TOKEN", "d2193c7f2b1e47458dbed1b4e8c10732")
GH_TOKEN = st.secrets.get("GH_TOKEN", "")

CHAMPIONNATS = {
    "🇫🇷 Ligue 1": ("FL1", "F1"),
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": ("PL", "E0"),
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship": ("ELC", "E1"),
    "🇪🇸 La Liga": ("PD", "SP1"),
    "🇮🇹 Serie A": ("SA", "I1"),
    "🇩🇪 Bundesliga": ("BL1", "D1"),
    "🇵🇹 Primeira Liga": ("PPL", "P1"),
    "🇳🇱 Eredivisie": ("DED", "N1"),
    "🇧🇷 Brasileirão": ("BSA", "BSA"),
    "🇪🇺 Ligue des Champions": ("CL", "CL")
}

def load_db():
    if GH_TOKEN:
        try:
            r = requests.get(GH_API, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=10)
            if r.status_code == 200:
                return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
        except Exception:
            pass
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    if GH_TOKEN:
        try:
            hdrs = {"Authorization": f"token {GH_TOKEN}"}
            g = requests.get(GH_API, headers=hdrs, timeout=10)
            sha = g.json().get("sha") if g.status_code == 200 else None
            b64 = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")
            payload = {"message": "Update bankroll", "content": b64}
            if sha:
                payload["sha"] = sha
            requests.put(GH_API, headers=hdrs, json=payload, timeout=10)
        except Exception:
            pass

def get_cap(u):
    cap = float(u.get("capital_depart", 20.0))
    for p in u.get("paris", []):
        if p.get("Statut") == "✅ Gagné":
            cap += float(p.get("Gain Visé (€)", 0))
        elif p.get("Statut") == "❌ Perdu":
            cap -= float(p.get("Mise (€)", 0))
    return round(cap, 2)

def fetch_matches(codes):
    fd_code, csv_code = codes
    err_api = ""
    try:
        url = f"https://football-data.org{fd_code}/matches?status=FINISHED"
        r = requests.get(url, headers={"X-Auth-Token": FD_TOKEN}, timeout=25, verify=False)
        if r.status_code == 200:
            rows = []
            for m in r.json().get("matches", []):
                ft = m.get("score", {}).get("fullTime", {})
                hg, ag = ft.get("home"), ft.get("away")
                if hg is not None and ag is not None:
                    ftr = "H" if hg > ag else ("A" if ag > hg else "D")
                    rows.append({
                        "HomeTeam": m["homeTeam"].get("shortName") or m["homeTeam"]["name"],
                        "AwayTeam": m["awayTeam"].get("shortName") or m["awayTeam"]["name"],
                        "FTHG": int(hg),
                        "FTAG": int(ag),
                        "FTR": ftr
                    })
            if rows:
                return pd.DataFrame(rows), ""
        else:
            err_api = f"HTTP {r.status_code}"
    except Exception as e:
        err_api = str(e)

    if csv_code and os.path.exists(f"{csv_code}.csv"):
        try:
            df = pd.read_csv(f"{csv_code}.csv")
            if {'HomeTeam', 'AwayTeam', 'FTR'}.issubset(df.columns):
                return df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTR']), ""
        except Exception:
            pass

    return pd.DataFrame(), err_api

def calc_v2(df, eq1, eq2):
    def st_t(t):
        g = df[(df['HomeTeam'] == t) | (df['AwayTeam'] == t)].tail(6)
        v = len(g[((g['HomeTeam'] == t) & (g['FTR'] == 'H')) | ((g['AwayTeam'] == t) & (g['FTR'] == 'A'))])
        n = len(g[g['FTR'] == 'D'])
        d = len(g) - v - n
        dom, bp, bc = 0.0, [], []
        for _, r in g.iterrows():
            is_h = (r['HomeTeam'] == t)
            if {'FTHG', 'FTAG'}.issubset(g.columns) and pd.notna(r['FTHG']) and pd.notna(r['FTAG']):
                hg, ag = float(r['FTHG']), float(r['FTAG'])
                dom += (hg - ag) * (0.15 if is_h else -0.15)
                bp.append(hg if is_h else ag)
                bc.append(ag if is_h else hg)
            if {'HST', 'AST'}.issubset(g.columns) and pd.notna(r['HST']) and pd.notna(r['AST']):
                dom += (float(r['HST']) - float(r['AST'])) * (0.04 if is_h else -0.04)
        return v, n, d, dom, (sum(bp) / len(bp) if bp else 1.2), (sum(bc) / len(bc) if bc else 1.2)

    def sl(t, h=True):
        s = df[df['HomeTeam'] == t].tail(3) if h else df[df['AwayTeam'] == t].tail(3)
        v = len(s[s['FTR'] == ('H' if h else 'A')])
        n = len(s[s['FTR'] == 'D'])
        return v, n, len(s) - v - n

    g1v, g1n, g1d, dom1, bp1, bc1 = st_t(eq1)
    g2v, g2n, g2d, dom2, bp2, bc2 = st_t(eq2)
    hv, hn, hd = sl(eq1, True)
    av, an, ad = sl(eq2, False)
    l1 = max(0.3, (bp1 + bc2) / 2)
    l2 = max(0.3, (bp2 + bc1) / 2)
    return (
        max(0.1, (g1v + g2d) - (hv + ad) + (dom1 - dom2)),
        max(0.1, (g1n + g2n) - (hn + an)),
        max(0.1, (g1d + g2v) - (hd + av) + (dom2 - dom1)),
        l1,
        l2
    )

@st.cache_data(ttl=3600, show_spinner=False)
def fit_dixon_coles(df_hash, teams, home_idx, away_idx, hg, ag, weights):
    n_teams = len(teams)

    def rho_correction(x, y, l1, l2, rho):
        if x == 0 and y == 0:
            return max(0.01, 1.0 - (l1 * l2 * rho))
        elif x == 0 and y == 1:
            return max(0.01, 1.0 + (l1 * rho))
        elif x == 1 and y == 0:
            return max(0.01, 1.0 + (l2 * rho))
        elif x == 1 and y == 1:
            return max(0.01, 1.0 - rho)
        return 1.0

    def loss_func(params):
        att = params[:n_teams]
        defn = params[n_teams:2*n_teams]
        home_adv = params[2*n_teams]
        rho = params[2*n_teams + 1]

        att = att - np.mean(att)

        l1 = np.exp(att[home_idx] + defn[away_idx] + home_adv)
        l2 = np.exp(att[away_idx] + defn[home_idx])

        ll = weights * (hg * np.log(l1 + 1e-9) - l1 + ag * np.log(l2 + 1e-9) - l2)
        corr = np.array([rho_correction(int(x), int(y), a, b, rho) for x, y, a, b in zip(hg, ag, l1, l2)])
        ll += weights * np.log(corr)

        reg = 0.05 * (np.sum(att**2) + np.sum(defn**2))
        return -np.sum(ll) + reg

    init_params = np.zeros(2 * n_teams + 2)
    init_params[2 * n_teams] = 0.25
    init_params[2 * n_teams + 1] = -0.05

    bounds = [(-2.5, 2.5)] * (2 * n_teams) + [(-0.5, 1.0), (-0.3, 0.3)]
    res = minimize(loss_func, init_params, method="L-BFGS-B", bounds=bounds, options={"maxiter": 120})

    p = res.x
    att = p[:n_teams] - np.mean(p[:n_teams])
    defn = p[n_teams:2*n_teams]
    return dict(zip(teams, att)), dict(zip(teams, defn)), float(p[2*n_teams]), float(p[2*n_teams + 1])

def calc_v3_dixon_coles(df, eq1, eq2):
    sub = df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']).tail(250).reset_index(drop=True)
    if len(sub) < 20 or eq1 not in sub['HomeTeam'].values or eq2 not in sub['AwayTeam'].values:
        return calc_v2(df, eq1, eq2)

    teams = sorted(list(set(sub['HomeTeam']).union(set(sub['AwayTeam']))))
    t_map = {t: i for i, t in enumerate(teams)}

    home_idx = sub['HomeTeam'].map(t_map).values
    away_idx = sub['AwayTeam'].map(t_map).values
    hg = sub['FTHG'].astype(float).values
    ag = sub['FTAG'].astype(float).values

    n = len(sub)
    weights = np.exp(-0.006 * np.arange(n - 1, -1, -1))
    df_hash = f"{n}_{sub.iloc[-1]['HomeTeam']}_{sub.iloc[-1]['AwayTeam']}_{hg[-1]}_{ag[-1]}"

    att, defn, home_adv, rho = fit_dixon_coles(df_hash, teams, home_idx, away_idx, hg, ag, weights)

    l1 = max(0.25, math.exp(att[eq1] + defn[eq2] + home_adv))
    l2 = max(0.25, math.exp(att[eq2] + defn[eq1]))

    p_v, p_n, p_d = 0.0, 0.0, 0.0
    for x in range(8):
        px = (math.exp(-l1) * (l1 ** x)) / math.factorial(x)
        for y in range(8):
            py = (math.exp(-l2) * (l2 ** y)) / math.factorial(y)
            tau = 1.0
            if x == 0 and y == 0:
                tau = max(0.01, 1.0 - l1 * l2 * rho)
            elif x == 0 and y == 1:
                tau = max(0.01, 1.0 + l1 * rho)
            elif x == 1 and y == 0:
                tau = max(0.01, 1.0 + l2 * rho)
            elif x == 1 and y == 1:
                tau = max(0.01, 1.0 - rho)

            prob = px * py * tau
            if x > y:
                p_v += prob
            elif x == y:
                p_n += prob
            else:
                p_d += prob

    tot = max(0.001, p_v + p_n + p_d)
    return (p_v / tot) * 100.0, (p_n / tot) * 100.0, (p_d / tot) * 100.0, l1, l2

def poisson_score(l1, l2, g1, g2):
    p1 = (math.exp(-l1) * (l1 ** g1)) / math.factorial(g1)
    p2 = (math.exp(-l2) * (l2 ** g2)) / math.factorial(g2)
    prob = max(0.001, p1 * p2)
    return round(1.0 / prob, 2), round(prob * 100, 1)

def check_results(paris):
    maj = 0
    codes = {p.get("Code") for p in paris if p.get("Statut") == "⏳ En cours" and p.get("Code")}
    cache = {}
    for c in codes:
        df, _ = fetch_matches((c, ""))
        if not df.empty:
            cache[c] = df.tail(30)
    for p in paris:
        if p.get("Statut") != "⏳ En cours" or "-" not in p.get("Match", ""):
            continue
        eq1, eq2 = p["Match"].split("-", 1)
        df = cache.get(p.get("Code"))
        if df is None:
            continue
        m = df[(df["HomeTeam"] == eq1) & (df["AwayTeam"] == eq2)].tail(1)
        if m.empty:
            continue
    
