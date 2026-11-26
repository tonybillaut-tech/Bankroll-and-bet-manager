import pandas as pd
import requests, os, urllib3
import streamlit as st
from database import load_db, save_db
from algo_v2 import calc_v2
from algo_v3 import calc_v3_dixon_coles
from algo_v4 import calc_v4_meta

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

from tracker import poisson_score, check_results
