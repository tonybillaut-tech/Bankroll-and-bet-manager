import math
from moteur import fetch_matches

def get_cap(u):
    cap = float(u.get("capital_depart", 20.0))
    for p in u.get("paris", []):
        if p.get("Statut") == "✅ Gagné":
            cap += float(p.get("Gain Visé (€)", 0))
        elif p.get("Statut") == "❌ Perdu":
            cap -= float(p.get("Mise (€)", 0))
    return round(cap, 2)

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
        hg = int(m["FTHG"].values.item())
        ag = int(m["FTAG"].values.item())
        ftr = str(m["FTR"].values.item())
        ch = p.get("Choix", "")
        if ch.startswith("Score "):
            p["Statut"] = "✅ Gagné" if ch == f"Score {hg}-{ag}" else "❌ Perdu"
        elif ch == "Match Nul":
            p["Statut"] = "✅ Gagné" if ftr == "D" else "❌ Perdu"
        elif "(DNB)" in ch:
            p["Statut"] = "✅ Gagné" if ((eq1 in ch and ftr == "H") or (eq2 in ch and ftr == "A")) else ("🔄 Remboursé" if ftr == "D" else "❌ Perdu")
        else:
            p["Statut"] = "✅ Gagné" if ((eq1 in ch and ftr == "H") or (eq2 in ch and ftr == "A")) else "❌ Perdu"
        maj += 1
    return maj
  
