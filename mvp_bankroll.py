import streamlit as st
import importlib, pkgutil, inspect
from database import load_db, save_db, hash_pin
from moteur import get_cap
from onglets.analyse import render_analyse
from onglets.backtest import render_backtest
from onglets.donnees import render_donnees

st.set_page_config(page_title="SmartStake — Value Bet & Bankroll IA", page_icon="⚽", layout="centered")
is_android = st.query_params.get("platform", "") == "android"

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
div[data-testid="stMetric"] { background: #161b22; padding: 10px 14px; border-radius: 10px; border: 1px solid #2b313a; }
</style>
""", unsafe_allow_html=True)

st.title("⚽ SmartStake")
st.caption("v11.0 • Moteurs V2, V3 Dixon-Coles, V4 Méta-IA & 🦖 V5 Darwin")

db = load_db()

if "user" not in st.session_state:
    st.session_state["user"] = ""

if not st.session_state["user"]:
    tab_login, tab_reg = st.tabs(["🔐 Connexion", "📝 Créer un compte"])
    with tab_login:
        u_in = st.text_input("Identifiant", key="login_u").strip()
        p_in = st.text_input("Code PIN / Mot de passe", type="password", key="login_p").strip()
        if st.button("Se connecter", type="primary", use_container_width=True):
            matched_user = next((k for k in db.keys() if k != "_v4_meta" and k.lower() == u_in.lower()), None)
            if matched_user:
                stored_pin = str(db[matched_user].get("pin_hash", ""))
                if not stored_pin or stored_pin == hash_pin(p_in):
                    st.session_state["user"] = matched_user
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
                db[new_u] = {
                    "capital_depart": float(cap_dep),
                    "paris": [],
                    "is_pro": False,
                    "essai": 0,
                    "pin_hash": hash_pin(new_p)
                }
                save_db(db)
                st.session_state["user"] = new_u
                st.rerun()
    st.stop()

user = st.session_state["user"]
u_data = db.get(user, {"capital_depart": 20.0, "paris": [], "is_pro": False, "essai": 0})
cap = get_cap(u_data)
is_pro = bool(u_data.get("is_pro", False))

c_head1, c_head2, c_head3 = st.columns(3)
c_head1.markdown(f"👤 **{user}** {'👑 `VIP PRO`' if is_pro else '🆓 `Essai`'}")
c_head2.markdown(f"💰 Capital : **{cap:.2f} €**")
if c_head3.button("🚪 Quitter", use_container_width=True):
    st.session_state["user"] = ""
    st.rerun()

extra_tabs = []
for _, mod_name, _ in pkgutil.iter_modules(["onglets"]):
    if mod_name not in ("analyse", "backtest", "donnees"):
        try:
            mod = importlib.import_module(f"onglets.{mod_name}")
            fn = next((v for k, v in inspect.getmembers(mod, inspect.isfunction) if k.startswith("render_")), None)
            if fn:
                label = "📜 Paris" if "hist" in mod_name or "pari" in mod_name else ("💎 VIP" if "vip" in mod_name or "abo" in mod_name else ("📘 Guide" if "info" in mod_name or "guide" in mod_name else f"📌 {mod_name.capitalize()}"))
                extra_tabs.append((label, mod_name, fn))
        except Exception:
            pass

tab_labels = ["⚽ Analyse", "📊 Backtest", "📂 CSV / Perso"] + [lbl for lbl, _, _ in extra_tabs]
tabs = st.tabs(tab_labels)
it_tabs = iter(tabs)

with next(it_tabs):
    render_analyse(user, db, cap, is_pro)

with next(it_tabs):
    render_backtest()

with next(it_tabs):
    render_donnees()

for _, mod_name, fn in extra_tabs:
    with next(it_tabs):
        n_params = len(inspect.signature(fn).parameters)
        if n_params == 0:
            fn()
        elif n_params == 2:
            fn(user, db)
        elif n_params == 3:
            fn(user, db, is_pro)
        else:
            fn(user, db, is_pro, is_android)
