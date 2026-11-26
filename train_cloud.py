import os, io, time, requests
import pandas as pd
from algo_v4 import calc_v4_meta

SUPABASE_ID = "tnvjjzyssyeyvipqltws"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRudmpqenlzc3lleXZpcHFsdHdzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTU1Njk4NTYsImV4cCI6MjExMTE0NTg1Nn0.9VXz2mIHj-jcBfZvZWoTBIF0zSsVb3aDXoKP2P0Q7F8"
SB_URL = f"https://{SUPABASE_ID}.supabase.co/rest/v1/smartstake_users"
FD_TOKEN = os.environ.get("FD_TOKEN", "d2193c7f2b1e47458dbed1b4e8c10732")

LIGUES = {
    "FL1": "F1", "PL": "E0", "ELC": "E1", "PD": "SP1", "SA": "I1",
    "BL1": "D1", "PPL": "P1", "DED": "N1", "BSA": "BSA", "CL": "CL"
}

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}

def fetch_data(fd_code, csv_code):
    if csv_code not in ["CL", "BSA"]:
        for s in ["2526", "2425"]:
            try:
                r = requests.get(f"https://football-data.co.uk{s}/{csv_code}.csv", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if r.status_code == 200:
                    df = pd.read_csv(io.StringIO(r.text)).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR', 'B365H', 'B365D', 'B365A'])
                    if len(df) >= 65:
                        return df.reset_index(drop=True), True
            except Exception:
                pass
    r = requests.get(f"https://football-data.org{fd_code}/matches?status=FINISHED", headers={"X-Auth-Token": FD_TOKEN}, timeout=25)
    rows = []
    if r.status_code == 200:
        for m in r.json().get("matches", []):
            ft = m.get("score", {}).get("fullTime", {})
            hg, ag = ft.get("home"), ft.get("away")
            if hg is not None and ag is not None:
                rows.append({"HomeTeam": m["homeTeam"].get("shortName") or m["homeTeam"]["name"], "AwayTeam": m["awayTeam"].get("shortName") or m["awayTeam"]["name"], "FTHG": int(hg), "FTAG": int(ag), "FTR": "H" if hg > ag else ("A" if ag > hg else "D")})
    return pd.DataFrame(rows), False

def simuler(df, C_val, alpha):
    cap, mise_tot, paris = 100.0, 0.0, 0
    has_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
    for i in range(60, len(df)):
        row = df.iloc[i]
        t3v, t3n, t3d, _, _ = calc_v4_meta(df.iloc[:max(60, (i // 15) * 15)], row["HomeTeam"], row["AwayTeam"], C_val=C_val, alpha=alpha)
        c1_o, cn_o, c2_o = (float(row["B365H"]), float(row["B365D"]), float(row["B365A"])) if has_odds else (2.25, 3.30, 3.10)
        for side, ct, cr in [("H", 1 + t3d / t3v, c1_o * (cn_o - 1) / cn_o), ("A", 1 + t3v / t3d, c2_o * (cn_o - 1) / cn_o)]:
            if cr > ct * 1.08 and 1.90 <= cr <= 3.50 and cap > 1.0:
                mise = min(cap, ((cap * 0.05) * (cr / 2.0)) / (cr - 1.0))
                paris += 1
                mise_tot += mise
                if row["FTR"] == side: cap += mise * (cr - 1.0)
                elif row["FTR"] != "D": cap -= mise
                break
    return paris, round(((cap - 100.0) / max(1.0, mise_tot)) * 100, 1)

if __name__ == "__main__":
    meta = {"capital_depart": 0.0, "paris": [], "is_pro": False, "essai": 0, "pin_hash": ""}
    grille = [(0.2, 0.70), (0.5, 0.50), (0.5, 0.80), (1.0, 0.70), (1.0, 0.90), (2.0, 0.85)]
    for fd, csv in LIGUES.items():
        df, real = fetch_data(fd, csv)
        if len(df) >= 65:
            best = max(((c, a, *simuler(df, c, a)) for c, a in grille), key=lambda x: x[3] if x[2] >= 8 else x[3] - 50.0)
            meta[fd] = {"C": best[0], "alpha": best[1], "trained": True, "roi_bt": best[3], "paris_bt": best[2]}
            print(f"{fd}: C={best[0]} alpha={best[1]} ROI={best[3]}%")
        if not real:
            time.sleep(6.1)
    requests.post(SB_URL, headers=sb_headers(), json=[{"user_id": "_v4_meta", "capital_depart": 0.0, "paris": [], "is_pro": False, "essai": 0, "pin_hash": ""}])
