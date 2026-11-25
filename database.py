import requests, json, os, base64
import streamlit as st

REPO_NAME = "Bankroll-and-bet-manager"
DB_FILE = "smartstake_users.json"
GH_API = "https://" + f"://github.com{REPO_NAME}/contents/{DB_FILE}"

GH_TOKEN = st.secrets.get("GH_TOKEN", "")
SUPABASE_ID = st.secrets.get("SUPABASE_ID", "tnvjjzyssyeyvipqltws").strip()
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "").strip()
SUPABASE_URL = "https://" + f"{SUPABASE_ID}.supabase.co" if SUPABASE_ID else ""

def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def load_db():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/smartstake_users?select=*"
            r = requests.get(url, headers=_sb_headers(), timeout=8)
            if r.status_code == 200:
                return {
                    row["user_id"]: {
                        "capital_depart": row.get("capital_depart", 20.0),
                        "paris": row.get("paris", []),
                        "is_pro": row.get("is_pro", False),
                        "essai": row.get("essai", 0)
                    }
                    for row in r.json()
                }
        except Exception:
            pass

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
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/smartstake_users"
            payload = [
                {
                    "user_id": uid,
                    "capital_depart": float(udata.get("capital_depart", 20.0)),
                    "paris": udata.get("paris", []),
                    "is_pro": bool(udata.get("is_pro", False)),
                    "essai": int(udata.get("essai", 0))
                }
                for uid, udata in data.items()
            ]
            if payload:
                r = requests.post(url, headers=_sb_headers(), json=payload, timeout=8)
                if r.status_code in (200, 201):
                    return
        except Exception:
            pass

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
          
