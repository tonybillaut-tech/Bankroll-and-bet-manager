import streamlit as st
import importlib, pkgutil, inspect, hashlib, hmac
from database import load_db, save_db, hash_pin
from moteur import get_cap
from onglets.analyse import render_analyse
from onglets.backtest import render_backtest
from onglets.donnees import render_donnees

st.set_page_config(page_title="SmartStake — Value Bet & Bankroll IA", page_icon="⚽", layout="centered")
is_android = st.query_params.get("platform", "") == "android"

def make_token(username: str, pin_hash: str) -> str:
    secret = st.secrets.get("SUPABASE_KEY", "smartstake_secret_2026").encode("utf-8")
    msg = f"{username.lower()}:{pin_hash}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()

def render_footer():
    st.divider()
    st.caption(
        "🔞 **Application réservée aux personnes majeures (+18 ans).** "
        "SmartStake est un outil d'aide à la décision mathématique et de gestion de bankroll : "
        "aucun gain n'est garanti. Jouer comporte des risques (endettement, isolement, dépendance). "
        "Aide et information : **09 74 75 13 13** (appel non surtaxé) ou [joueurs-info-service.fr](https://joueurs-info-service.fr) • "
        "[Règles de confidentialité](https://github.com)"
    )

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
div[data-testid="stMetric"] { background: #161b22; padding: 10px 14px; border-radius: 10px; border: 1px solid #2b313a; }
</style>
""", unsafe_allow_html=True)

st.title("⚽ SmartStake")
st.caption("v11.1 • Moteurs V2, V3 Dixon-Coles, V4 Méta-IA & 🦖 V5 Darwin")

db = load_db()

if "user" not in st.session_state:
    st.session_state["user"] = ""

if not st.session_state["user"]:
    saved_u = st.query_params.get("u", "")
    saved_tok = st.query_params.get("t", "")
    if saved_u and saved_tok and isinstance(db, dict):
        matched = next((k for k in db.keys() if k != "_v4_meta" and k.lower() == saved_u.lower()), None)
        if matched:
            p_hash = str(db[matched].get("pin_hash", ""))
            if hmac.compare_digest(saved_tok, make_token(matched, p_hash)):
                st.session_state["user"] = matched

if not st.session_state["user"]:
    tab_login, tab_reg = st.tabs(["🔐 Connexion", "📝 Créer un compte"])
    with tab_login:
        u_in = st.text_input("Identifiant", key="login_u").strip()
        p_in = st.text_input("Code PIN / Mot de passe", type="password", key="login_p").strip()
        stay_logged = st.checkbox("🔒 Rester connecté sur cet appareil", value=True)
        if st.button("Se connecter", type="primary", use_container_width=True):
            matched_user = next((k for k in db.keys() if k != "_v4_meta" and k.lower() == u_in.lower()), None)
            if matched_user:
                stored_pin = str(db[matched_user].get("pin_hash", ""))
                if not stored_pin or stored_pin == hash_pin(p_in):
                    st.session_state["user"] = matched_user
                    if stay_logged:
                        st.query_params["u"] = matched_user
                        st.query_params["t"] = make_token(matched_user, stored_pin)
                    st.rerun()
                else:
                    st.error("Code PIN incorrect.")
            else:
                st.error("Identifiant introuvable.")
    with tab_reg:
        new_u = st.text_input("Choisis un identifiant", key="reg_u").strip()
        new_p = st.text_input("Choisis un code PIN (4 à 8 caractères)", type="password", key="reg_p").strip()
        cap_dep = st.number_input("Capital de départ (€)", 5.0, 50000.0, 20.0, step=5.0)
        if st.button("Créer mon compte", type="primary", use_container_width=True):
            exists = any(k.lower() == new_u.lower() for k in db.keys())
            if len(new_u) < 3 or new_u == "_v4_meta":
                st.warning("Choisis un identifiant d'au moins 3 caractères.")
            elif exists:
                st.error("Cet identifiant est déjà utilisé.")
            elif len(new_p) < 4:
                st.warning("Le code PIN doit contenir au moins 4 caractères.")
            else:
                p_h = hash_pin(new_p)
                db[new_u] = {"capital_depart": float(cap_dep), "paris": [], "is_pro": False, "essai": 0, "pin_hash": p_h}
                save_db(db)
                st.session_state["user"] = new_u
                st.query_params["u"] = new_u
                st.query_params["t"] = make_token(new_u, p_h)
                st.rerun()
    render_footer()
    st.stop()

user = st.session_state["user"]
st.session_state["user_id"] = user
u_data = db.get(user, {"capital_depart": 20.0, "paris": [], "is_pro": False, "essai": 0})
cap = get_cap(u_data)
is_pro = bool(u_data.get("is_pro", False))
essais_faits = int(u_data.get("essai") or 0)

c_head1, c_head2, c_head3 = st.columns(3)
c_head1.markdown(f"👤 **{user}** {'👑 `VIP PRO`' if is_pro else f'🆓 `Essai ({essais_faits}/10)`'}")
c_head2.markdown(f"💰 Capital : **{cap:.2f} €**")
if c_head3.button("🚪 Quitter", use_container_width=True):
    st.session_state["user"] = ""
    st.session_state["user_id"] = ""
    if "u" in st.query_params:
        del st.query_params["u"]
    if "t" in st.query_params:
        del st.query_params["t"]
    st.rerun()

extra_tabs = []
for _, mod_name, _ in pkgutil.iter_modules(["onglets"]):
    if mod_name not in ("analyse", "backtest", "donnees"):
        try:
            mod = importlib.import_module(f"onglets.{mod_name}")
            fn = next((v for k, v in inspect.getmembers(mod, inspect.isfunction) if k.startswith("render_")), None)
            if fn:
                label = "📜 Bankroll" if ("bank" in mod_name or "hist" in mod_name) else ("💎 VIP" if ("vip" in mod_name or "abo" in mod_name) else ("📘 Guide" if ("info" in mod_name or "guide" in mod_name) else f"📌 {mod_name.capitalize()}"))
                extra_tabs.append((label, mod_name, fn))
        except Exception:
            pass

nav_items = [("⚽ Analyse", "analyse", None), ("📊 Backtest", "backtest", None), ("📂 CSV", "donnees", None)] + extra_tabs
labels = [lbl for lbl, _, _ in nav_items]

if "active_tab" not in st.session_state or st.session_state["active_tab"] not in labels:
    st.session_state["active_tab"] = labels

for row_start in range(0, len(labels), 3):
    cols = st.columns(3)
    for idx_col, lbl in enumerate(labels[row_start:row_start + 3]):
        is_sel = (st.session_state["active_tab"] == lbl)
        if cols.at(idx_col) if hasattr(cols, "at") else cols[idx_col]:
            pass
    for idx_col in range(min(3, len(labels) - row_start)):
        lbl = labels[row_start + idx_col]
        is_sel = (st.session_state["active_tab"] == lbl)
        if cols[idx_col].button(lbl, key=f"nav_{row_start + idx_col}", type="primary" if is_sel else "secondary", use_container_width=True):
            st.session_state["active_tab"] = lbl
            st.rerun()

st.divider()
cur_idx = labels.index(st.session_state["active_tab"])
_, cur_mod, cur_fn = nav_items[cur_idx]

if cur_mod == "analyse":
    render_analyse(user, db, cap, is_pro)
elif cur_mod == "backtest":
    render_backtest()
elif cur_mod == "donnees":
    render_donnees()
elif cur_fn:
    n_params = len(inspect.signature(cur_fn).parameters)
    if n_params == 0:
        cur_fn()
    elif n_params == 2:
        cur_fn(db, user)
    elif n_params == 3:
        cur_fn(u_data, db, cap)
    else:
        cur_fn(db, user, is_pro, is_android)

st.divider()
c_prev, c_next = st.columns(2)
if cur_idx > 0:
    if c_prev.button(f"◀ {labels[cur_idx - 1]}", key="nav_prev", use_container_width=True):
        st.session_state["active_tab"] = labels[cur_idx - 1]
        st.rerun()
if cur_idx < len(labels) - 1:
    if c_next.button(f"{labels[cur_idx + 1]} ▶", key="nav_next", use_container_width=True):
        st.session_state["active_tab"] = labels[cur_idx + 1]
        st.rerun()

render_footer()
