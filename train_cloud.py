import os, io, time, requests
import pandas as pd
from algo_v4 import calc_v4_meta
from algo_v5 import run_evolution
from database import load_db, SUPABASE_URL, _sb_headers

FD_TOKEN = os.environ.get("FD_TOKEN", "d2193c7f2b1e47458dbed1b4e8c10732")

LIGUES = {
    "FL1": "F1", "PL": "E0", "ELC": "E1", "PD": "SP1", "SA": "I1",
    "BL1": "D1", "PPL": "P1", "DED": "N1", "BSA": "BSA", "CL": "CL"
}

def fetch_data(fd_code, csv_code):
    if csv_code not in ("CL", "BSA"):
        for s in ("2526", "2425"):
            try:
                url = "".join(["ht", "tps:", "//", "www.football-data.co.uk/mmz4281/", s, "/", csv_code, ".csv"])
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if r.status_code == 200:
                    df = pd.read_csv(io.StringIO(r.text)).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR', 'B365H', 'B365D', 'B365A'])
                    if len(df) >= 65:
                        return df.reset_index(drop=True), True
            except Exception:
                pass
    url_api = "".join(["ht", "tps:", "//", "api.football-data.org/v4/competitions/", fd_code, "/matches?status=FINISHED"])
    r = requests.get(url_api, headers={"X-Auth-Token": FD_TOKEN}, timeout=25)
    rows = []
    if r.status_code == 200:
        for m in r.json().get("matches", []):
            ft = m.get("score", {}).get("fullTime", {})
            hg, ag = ft.get("home"), ft.get("away")
            if hg is not None and ag is not None:
                rows.append({
                    "HomeTeam": m["homeTeam"].get("shortName") or m["homeTeam"]["name"],
                    "AwayTeam": m["awayTeam"].get("shortName") or m["awayTeam"]["name"],
                    "FTHG": int(hg), "FTAG": int(ag),
                    "FTR": "H" if hg > ag else ("A" if ag > hg else "D")
                })
    return pd.DataFrame(rows), False

def simuler_v4(df, C_val, alpha):
    cap, mise_tot, paris = 100.0, 0.0, 0
    has_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
    for i in range(60, len(df)):
        row = df.iloc[i]
        t3v, t3n, t3d, _, _ = calc_v4_meta(df.iloc[:max(60, (i // 30) * 30)], row["HomeTeam"], row["AwayTeam"], C_val=C_val, alpha=alpha)
        c1_o, cn_o, c2_o = (float(row["B365H"]), float(row["B365D"]), float(row["B365A"])) if has_odds else (2.25, 3.30, 3.10)
        for side, ct, cr in [("H", 1 + t3d / t3v, c1_o * (cn_o - 1) / cn_o), ("A", 1 + t3v / t3d, c2_o * (cn_o - 1) / cn_o)]:
            if cr > ct * 1.10 and 1.90 <= cr <= 3.50 and cap > 1.0:
                mise = min(cap, ((cap * 0.05) * (cr / 2.0)) / (cr - 1.0))
                paris += 1
                mise_tot += mise
                if row["FTR"] == side:
                    cap += mise * (cr - 1.0)
                elif row["FTR"] != "D":
                    cap -= mise
                break
    return paris, round(((cap - 100.0) / max(1.0, mise_tot)) * 100, 1)

if __name__ == "__main__":
    db = load_db()
    if "_v4_meta" not in db or not isinstance(db["_v4_meta"], dict):
        db["_v4_meta"] = {}

    grille = [(0.2, 0.70), (0.5, 0.50), (0.5, 0.80), (1.0, 0.70), (1.0, 0.90), (2.0, 0.85)]
    for fd, csv in LIGUES.items():
        df, real = fetch_data(fd, csv)
        if len(df) >= 65:
            best_score, best_res = -9999.0, None
            for c_try, a_try in grille:
                p_t, roi_t = simuler_v4(df, c_try, a_try)
                score = roi_t if p_t >= 8 else (roi_t - 50.0)
                if score > best_score:
                    best_score = score
                    best_res = (c_try, a_try, p_t, roi_t)

            # Évolution intensive de V5 Darwin dans le Cloud (60 individus x 35 générations)
            best_genome, _ = run_evolution(df.tail(220).reset_index(drop=True), n_pop=60, n_gen=35)

            if best_res:
                bc, ba, bp, broi = best_res
                db["_v4_meta"][fd] = {
                    "C": float(bc),
                    "alpha": round(float(ba), 2),
                    "trained": True,
                    "roi_bt": round(float(broi), 1),
                    "paris_bt": int(bp),
                    "darwin_genes": [round(float(g), 4) for g in best_genome]
                }
                print(f"{fd}: V4(C={bc}, ROI={broi}%) | V5 Darwin ADN sauvegarde")
        if not real:
            time.sleep(6.1)

    r = requests.patch(f"{SUPABASE_URL}/rest/v1/smartstake_users?user_id=eq._v4_meta", headers=_sb_headers(), json={"v4_meta": db["_v4_meta"]}, timeout=15)
    print("Sauvegarde Supabase:", r.status_code)
        
