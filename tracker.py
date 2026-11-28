import math
from moteur import fetch_matches

def get_cap(u):
    cap = float(u.get("capital_depart") or 20.0)
    paris = u.get("paris") if isinstance(u.get("paris"), list) else []
    for p in paris:
        st_p = str(p.get("Statut", ""))
        mise = float(p.get("Mise (€)", p.get("Mise", 0.0)) or 0.0)
        cote = float(p.get("Cote", 1.0) or 1.0)
        if "✅" in st_p or "Gagné" in st_p:
            cap += mise * (cote - 1.0)
        elif "❌" in st_p or "Perdu" in st_p or "⏳" in st_p or "cours" in st_p:
            cap -= mise
    return round(cap, 2)

def poisson_score(l1, l2, g1, g2):
    p1 = (math.exp(-l1) * (l1 ** g1)) / math.factorial(g1)
    p2 = (math.exp(-l2) * (l2 ** g2)) / math.factorial(g2)
    prob = max(0.001, p1 * p2)
    return round(1.0 / prob, 2), round(prob * 100, 1)

def check_results(paris):
    if not isinstance(paris, list):
        return []
    codes = {p.get("Code") for p in paris if p.get("Statut") == "⏳ En cours" and p.get("Code")}
    cache = {}
    for c in codes:
        df, _ = fetch_matches((c, ""))
        if not df.empty:
            cache[c] = df.tail(40)
    for p in paris:
        if p.get("Statut") != "⏳ En cours":
            continue
        match_str = str(p.get("Match", ""))
        if " vs " in match_str:
            eq1, eq2 = [x.strip() for x in match_str.split(" vs ", 1)]
        elif "-" in match_str:
            eq1, eq2 = [x.strip() for x in match_str.split("-", 1)]
        else:
            continue
        df = cache.get(p.get("Code"))
        if df is None:
            continue
        m = df[(df["HomeTeam"] == eq1) & (df["AwayTeam"] == eq2)].tail(1)
        if m.empty:
            continue
        hg = int(m["FTHG"].values.item())
        ag = int(m["FTAG"].values.item())
        ftr = str(m["FTR"].values.item())
        ch = str(p.get("Pronostic") or p.get("Choix") or "")
        if ch.startswith("Score "):
            p["Statut"] = "✅ Gagné" if ch == f"Score {hg}-{ag}" else "❌ Perdu"
        elif "Nul" in ch:
            p["Statut"] = "✅ Gagné" if ftr == "D" else "❌ Perdu"
        elif "DNB" in ch:
            p["Statut"] = "✅ Gagné" if ((eq1 in ch and ftr == "H") or (eq2 in ch and ftr == "A")) else ("🔄 Remboursé" if ftr == "D" else "❌ Perdu")
        else:
            p["Statut"] = "✅ Gagné" if ((eq1 in ch and ftr == "H") or (eq2 in ch and ftr == "A")) else "❌ Perdu"
    return paris
