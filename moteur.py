import pandas as pd
import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression
import requests, os, urllib3, math
import streamlit as st
from database import load_db, save_db

urllib3.disable_warnings()
FD_TOKEN = st.secrets.get("FD_TOKEN", "d2193c7f2b1e47458dbed1b4e8c10732")

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

def get_v4_params(db: dict, league_code: str) -> dict:
    meta = db.get("_v4_meta", {}) if isinstance(db, dict) else {}
    return meta.get(league_code, {"C": 0.5, "alpha": 0.80, "trained": False, "roi_bt": 0.0, "paris_bt": 0})

def save_v4_params(db: dict, league_code: str, C_val: float, alpha_val: float, roi_bt: float, paris_bt: int):
    if "_v4_meta" not in db or not isinstance(db["_v4_meta"], dict):
        db["_v4_meta"] = {"capital_depart": 0.0, "paris": [], "is_pro": False, "essai": 0, "pin_hash": ""}
    db["_v4_meta"][league_code] = {
        "C": float(C_val),
        "alpha": round(float(alpha_val), 2),
        "trained": True,
        "roi_bt": round(float(roi_bt), 1),
        "paris_bt": int(paris_bt)
    }
    save_db(db)

def fetch_matches(codes):
    fd_code, csv_code = codes
    err_api = ""
    try:
        url = "".join(["ht", "tps:", "//", "api.football-data.org/v4/competitions/", fd_code, "/matches?status=FINISHED"])
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

@st.cache_data(ttl=3600, show_spinner=False)
def train_meta_model(df_hash, df_sub, C_val=0.5):
    X, y = [], []
    label_map = {"H": 0, "D": 1, "A": 2}
    start = max(25, len(df_sub) - 180)
    for i in range(start, len(df_sub)):
        row = df_sub.iloc[i]
        ftr = row["FTR"]
        if ftr not in label_map:
            continue
        hist = df_sub.iloc[:i]
        v2_1, v2_n, v2_2, _, _ = calc_v2(hist, row["HomeTeam"], row["AwayTeam"])
        tot2 = max(1.0, v2_1 + v2_n + v2_2)
        p2 = np.array([v2_1 / tot2, v2_n / tot2, v2_2 / tot2])

        sub_i = (i // 10) * 10
        v3_1, v3_n, v3_2, l1_3, l2_3 = calc_v3_dixon_coles(df_sub.iloc[:max(25, sub_i)], row["HomeTeam"], row["AwayTeam"])
        p3 = np.array([v3_1 / 100.0, v3_n / 100.0, v3_2 / 100.0])

        feat = np.concatenate([p2, p3, p3 - p2, [l1_3 - l2_3]])
        X.append(feat)
        y.append(label_map[ftr])

    if len(set(y)) < 3 or len(X) < 30:
        return None

    clf = LogisticRegression(C=float(C_val), max_iter=300)
    clf.fit(np.array(X), np.array(y))
    return clf

def calc_v4_meta(df, eq1, eq2, C_val=0.5, alpha=0.80):
    sub = df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTR', 'FTHG', 'FTAG']).tail(250).reset_index(drop=True)
    v2_1, v2_n, v2_2, l1_2, l2_2 = calc_v2(sub, eq1, eq2)
    v3_1, v3_n, v3_2, l1_3, l2_3 = calc_v3_dixon_coles(sub, eq1, eq2)

    if len(sub) < 55:
        return v3_1, v3_n, v3_2, l1_3, l2_3

    df_hash = f"meta_{C_val}_{len(sub)}_{sub.iloc[-1]['HomeTeam']}_{sub.iloc[-1]['AwayTeam']}_{sub.iloc[-1]['FTHG']}"
    clf = train_meta_model(df_hash, sub, C_val=C_val)
    if clf is None:
        return v3_1, v3_n, v3_2, l1_3, l2_3

    tot2 = max(1.0, v2_1 + v2_n + v2_2)
    p2 = np.array([v2_1 / tot2, v2_n / tot2, v2_2 / tot2])
        
