import pandas as pd
import requests, json, os, urllib3, math

urllib3.disable_warnings()
FD_TOKEN = "d2193c7f2b1e47458dbed1b4e8c10732"
DB_FILE = "smartstake_users.json"

CHAMPIONNATS = {
    "🇫🇷 Ligue 1": ("FL1", "F1"), "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": ("PL", "E0"),
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship": ("ELC", "E1"), "🇪🇸 La Liga": ("PD", "SP1"),
    "🇮🇹 Serie A": ("SA", "I1"), "🇩🇪 Bundesliga": ("BL1", "D1"),
    "🇵🇹 Primeira Liga": ("PPL", "P1"), "🇳🇱 Eredivisie": ("DED", "N1"),
    "🇧🇷 Brasileirão": ("BSA", "BSA"), "🇪🇺 Ligue des Champions": ("CL", "CL")
}

def load_db():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: pass
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception: pass

def get_cap(u):
    cap = float(u.get("capital_depart", 20.0))
    for p in u.get("paris", []):
        if p.get("Statut") == "✅ Gagné": cap += float(p.get("Gain Visé (€)", 0))
        elif p.get("Statut") == "❌ Perdu": cap -= float(p.get("Mise (€)", 0))
    return round(cap, 2)

def fetch_matches(codes):
    fd_code, csv_code = codes
    if os.path.exists(f"{csv_code}.csv"):
        try:
            df = pd.read_csv(f"{csv_code}.csv")
            if {'HomeTeam', 'AwayTeam', 'FTR'}.issubset(df.columns): return df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTR']), ""
        except Exception: pass
    try:
        url = "/".join(["https://football-data.org", "v4", "competitions", fd_code, "matches?status=FINISHED"])
        r = requests.get(url, headers={"X-Auth-Token": FD_TOKEN}, timeout=25, verify=False)
        if r.status_code == 200:
            rows = []
            for m in r.json().get("matches", []):
                ft = m.get("score", {}).get("fullTime", {})
                hg, ag = ft.get("home"), ft.get("away")
                if hg is not None and ag is not None:
                    ftr = "H" if hg > ag else ("A" if ag > hg else "D")
                    rows.append({"HomeTeam": m["homeTeam"].get("shortName") or m["homeTeam"]["name"], "AwayTeam": m["awayTeam"].get("shortName") or m["awayTeam"]["name"], "FTHG": int(hg), "FTAG": int(ag), "FTR": ftr})
            if rows: return pd.DataFrame(rows), ""
        return pd.DataFrame(), f"HTTP {r.status_code}"
    except Exception as e: return pd.DataFrame(), str(e)

def calc_v2(df, eq1, eq2):
    def st_t(t):
        g = df[(df['HomeTeam'] == t) | (df['AwayTeam'] == t)].tail(6)
        v = len(g[((g['HomeTeam'] == t) & (g['FTR'] == 'H')) | ((g['AwayTeam'] == t) & (g['FTR'] == 'A'))])
        n = len(g[g['FTR'] == 'D']); d = len(g) - v - n; dom, bp, bc = 0.0, [], []
        for _, r in g.iterrows():
            is_h = (r['HomeTeam'] == t)
            if {'FTHG', 'FTAG'}.issubset(g.columns) and pd.notna(r['FTHG']) and pd.notna(r['FTAG']):
                hg, ag = float(r['FTHG']), float(r['FTAG'])
                dom += (hg - ag) * (0.15 if is_h else -0.15); bp.append(hg if is_h else ag); bc.append(ag if is_h else hg)
            if {'HST', 'AST'}.issubset(g.columns) and pd.notna(r['HST']) and pd.notna(r['AST']):
                dom += (float(r['HST']) - float(r['AST'])) * (0.04 if is_h else -0.04)
        return v, n, d, dom, (sum(bp)/len(bp) if bp else 1.2), (sum(bc)/len(bc) if bc else 1.2)
    def sl(t, h=True):
        s = df[df['HomeTeam'] == t].tail(3) if h else df[df['AwayTeam'] == t].tail(3)
        v = len(s[s['FTR'] == ('H' if h else 'A')]); n = len(s[s['FTR'] == 'D'])
        return v, n, len(s) - v - n
    g1v, g1n, g1d, dom1, bp1, bc1 = st_t(eq1); g2v, g2n, g2d, dom2, bp2, bc2 = st_t(eq2)
    hv, hn, hd = sl(eq1, True); av, an, ad = sl(eq2, False)
    l1, l2 = max(0.3, (bp1 + bc2)/2), max(0.3, (bp2 + bc1)/2)
    return max(0.1, (g1v + g2d) - (hv + ad) + (dom1 - dom2)), max(0.1, (g1n + g2n) - (hn + an)), max(0.1, (g1d + g2v) - (hd + av) + (dom2 - dom1)), l1, l2

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
        if not df.empty: cache[c] = df.tail(30)
    for p in paris:
        if p.get("Statut") != "⏳ En cours" or "-" not in p.get("Match", ""): continue
        eq1, eq2 = p["Match"].split("-", 1)
        df = cache.get(p.get("Code"))
        if df is None: continue
        m = df[(df["HomeTeam"] == eq1) & (df["AwayTeam"] == eq2)].tail(1)
        if m.empty: continue
        hg, ag, ftr, ch = int(m.iloc[0]["FTHG"]), int(m.iloc[0]["FTAG"]), m.iloc[0]["FTR"], p.get("Choix", "")
        if ch.startswith("Score "): p["Statut"] = "✅ Gagné" if ch == f"Score {hg}-{ag}" else "❌ Perdu"
        elif ch == "Match Nul": p["Statut"] = "✅ Gagné" if ftr == "D" else "❌ Perdu"
        elif "(DNB)" in ch:
            win = (eq1 in ch and ftr == "H") or (eq2 in ch and ftr == "A")
            p["Statut"] = "✅ Gagné" if win else ("🔄 Remboursé" if ftr == "D" else "❌ Perdu")
        else:
            win = (eq1 in ch and ftr == "H") or (eq2 in ch and ftr == "A")
            p["Statut"] = "✅ Gagné" if win else "❌ Perdu"
        maj += 1
    return maj
    
