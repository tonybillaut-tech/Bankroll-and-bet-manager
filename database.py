import requests, hashlib
import streamlit as st

SUPABASE_ID = "tnvjjzyssyeyvipqltws"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRudmpqenlzc3lleXZpcHFsdHdzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTU1Njk4NTYsImV4cCI6MjExMTE0NTg1Nn0.9VXz2mIHj-jcBfZvZWoTBIF0zSsVb3aDXoKP2P0Q7F8"
SUPABASE_URL = "".join(["ht", "tps:", "//", SUPABASE_ID, ".supa", "base.", "co"])

def hash_pin(pin: str) -> str:
    if not pin:
        return ""
    return hashlib.sha256(f"smartstake_salt_{pin.strip()}".encode("utf-8")).hexdigest()

def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def load_db():
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/smartstake_users?select=*", headers=_sb_headers(), timeout=8)
        if r.status_code == 200:
            db = {}
            for row in r.json():
                uid = row["user_id"]
                if uid == "_v4_meta":
                    db["_v4_meta"] = row.get("v4_meta") or {}
                else:
                    db[uid] = {
                        "capital_depart": row.get("capital_depart", 20.0),
                        "paris": row.get("paris", []),
                        "is_pro": row.get("is_pro", False),
                        "essai": row.get("essai", 0),
                        "pin_hash": row.get("pin_hash", "")
                    }
            return db
    except Exception:
        pass
    return {}

def save_db(data):
    try:
        payload = []
        for uid, udata in data.items():
            if uid == "_v4_meta":
                payload.append({
                    "user_id": "_v4_meta",
                    "capital_depart": 0.0,
                    "paris": [],
                    "is_pro": False,
                    "essai": 0,
                    "pin_hash": "",
                    "v4_meta": udata
                })
            else:
                payload.append({
                    "user_id": uid,
                    "capital_depart": float(udata.get("capital_depart", 20.0)),
                    "paris": udata.get("paris", []),
                    "is_pro": bool(udata.get("is_pro", False)),
                    "essai": int(udata.get("essai", 0)),
                    "pin_hash": str(udata.get("pin_hash", "")),
                    "v4_meta": {}
                })
        if payload:
            requests.post(f"{SUPABASE_URL}/rest/v1/smartstake_users?on_conflict=user_id", headers=_sb_headers(), json=payload, timeout=8)
    except Exception:
        pass

def redeem_vip_code(code: str, user_id: str) -> bool:
    c_clean = code.strip().upper()
    if not c_clean:
        return False
    sb_base = f"{SUPABASE_URL}/rest/v1/vip_codes"
    try:
        r = requests.get(f"{sb_base}?code=eq.{c_clean}&select=*", headers=_sb_headers(), timeout=8)
        if r.status_code == 200:
            item = next(iter(r.json()), None)
            if item and not item.get("is_used", False):
                up = requests.patch(f"{sb_base}?code=eq.{c_clean}", headers=_sb_headers(), json={"is_used": True, "used_by": user_id}, timeout=8)
                return up.status_code in (200, 204)
            elif item and item.get("is_used", False):
                st.warning("Ce code a déjà été utilisé.")
            else:
                st.warning(f"Code '{c_clean}' introuvable.")
    except Exception as e:
        st.warning(f"Détail : {e}")
    return False
    
