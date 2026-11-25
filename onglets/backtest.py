import streamlit as st
import pandas as pd
import io
from datetime import datetime
from moteur import CHAMPIONNATS, load_db, save_db, get_cap, fetch_matches, calc_v2, calc_v3_dixon_coles, calc_v4_meta, poisson_score, check_results
from database import hash_pin
from onglets.backtest import render_backtest
from onglets.infos import render_guide, render_pro

st.set_page_config(page_title="SmartStake Foot", page_icon="⚽", layout="centered")
st.markdown("""<style>.hero{background:linear-gradient(135deg,#064e3b,#15803d);padding:16px;border-radius:14px;color:white;margin-bottom:10px;border:1px solid #22c55e}.hero h1{margin:0;font-size:1.6rem;color:#fff}.hero p{margin:4px 0 0;font-size:.9rem;color:#dcfce7}.stButton>button[kind="primary"]{background-color:#16a34a;border-color:#16a34a;color:white;font-weight:700;border-radius:10px;height:3em}</style>""", unsafe_allow_html=True)

if "db" not in st.session_state: st.session_state.db = load_db()
db = st.session_state.db
for k, v in [("user_id", "Invite"), ("analyses_count", 0), ("is_pro", False), ("last_scan", None)]:
    if k not in st.session_state: st.session_state[k] = v

if st.session_state.user_id not in db:
    db[st.session_state.user_id] = {"capital_depart": 20.0, "paris": [], "is_pro": False, "essai": 0, "pin_hash": ""}

upgrade_token = st.query_params.get("upgrade", "")
expected_upgrade = st.secrets.get("UPGRADE_TOKEN", "SMART2026_OK")
if upgrade_token and upgrade_token == expected_upgrade:
    if st.session_state.user_id != "Invite":
        db[st.session_state.user_id]["is_pro"] = True
        save_db(db)
        st.session_state.is_pro = True
        st.query_params.clear()
        st.toast("🎉 Paiement validé ! Votre compte est passé en PRO ✨")
    else:
        st.warning("💳 Paiement détecté ! Connectez-vous ci-dessous à votre Espace Parieur pour activer votre accès PRO.")

hero_box = st.empty()
def draw_hero():
    badge = "PRO ✨" if st.session_state.is_pro else f"Essai : {max(0, 3 - st.session_state.analyses_count)}/3"
    hero_box.markdown(f'<div class="hero"><h1>⚽ SmartStake — Paris Sportifs Foot</h1><p>Scanner 360° • V2 / V3 / Méta-IA V4 • Cloud Sécurisé • <b>{badge}</b></p></div>', unsafe_allow_html=True)

draw_hero()
st.caption("⚖️ Aide statistique (aucune garantie de gain). **18+ | Jouer comporte des risques** : **09 74 75 13 13**.")

with st.expander(f"👤 Espace Parieur Sécurisé ({st.session_state.user_id})", expanded=(st.session_state.user_id == "Invite")):
    c_u1, c_u2 = st.columns(2)
    pseudo_in = c_u1.text_input("Pseudo ou e-mail :", value="" if st.session_state.user_id == "Invite" else st.session_state.user_id, placeholder="Ex: Tony")
    pin_in = c_u2.text_input("Code PIN (4 chiffres) :", type="password", max_chars=8, placeholder="••••")
    if st.button("🔐 Se connecter / Créer mon espace", use_container_width=True):
        p_clean = pseudo_in.strip()
        if not p_clean or len(pin_in.strip()) < 4:
            st.warning("Entrez un pseudo et un code PIN d'au moins 4 caractères.")
        else:
            h_in = hash_pin(pin_in)
            if p_clean in db:
                stored_pin = db[p_clean].get("pin_hash", "")
                if not stored_pin:
                    db[p_clean]["pin_hash"] = h_in
                    save_db(db)
                    st.session_state.user_id = p_clean
                    st.session_state.is_pro = db[p_clean].get("is_pro", False)
                    st.session_state.analyses_count = db[p_clean].get("essai", 0)
                    st.success("🔒 Code PIN enregistré sur votre compte !")
                    st.rerun()
                elif stored_pin == h_in:
                    st.session_state.user_id = p_clean
                    if upgrade_token == expected_upgrade:
                        db[p_clean]["is_pro"] = True
                        save_db(db)
                        st.query_params.clear()
                    st.session_state.is_pro = db[p_clean].get("is_pro", False)
                    st.session_state.analyses_count = db[p_clean].get("essai", 0)
                    st.rerun()
                else:
                    st.error("❌ Code PIN incorrect pour ce pseudo.")
            else:
                is_vip_new = (upgrade_token == expected_upgrade)
                db[p_clean] = {"capital_depart": 20.0, "paris": [], "is_pro": is_vip_new, "essai": 0, "pin_hash": h_in}
                save_db(db)
                if is_vip_new: st.query_params.clear()
                st.session_state.user_id = p_clean
                st.session_state.is_pro = is_vip_new
                st.session_state.analyses_count = 0
                st.success("✅ Nouvel espace sécurisé créé !")
                st.rerun()

user_data = db[st.session_state.user_id]
capital_actuel = get_cap(user_data)

@st.cache_data(ttl=3600, show_spinner="Chargement des matchs officiels...")
def get_cached_matches(codes): return fetch_matches(codes)

def run_algo(algo_name, df, eq1, eq2):
    if "V4" in algo_name: return calc_v4_meta(df, eq1, eq2)
    if "V3" in algo_name: return calc_v3_dixon_coles(df, eq1, eq2)
    return calc_v2(df, eq1, eq2)

tab_calc, tab_suivi, tab_bt, tab_tuto, tab_pro = st.tabs(["⚽ Analyse", "💰 Bankroll", "📊 Backtest", "📘 Guide", "🏆 Pro"])

with tab_calc:
    ligue = st.selectbox("🏟️ Compétition (Temps Réel)", list(CHAMPIONNATS.keys()))
    fd_code = CHAMPIONNATS[ligue]
    df, err = get_cached_matches(CHAMPIONNATS[ligue])
    if df.empty: st.warning(f"⚠️ Flux indisponible ({err}).")
    else:
        st.caption(f"✅ Flux officiel actif : **{len(df)} matchs terminés**.")
        eqs = sorted(list(set(df['HomeTeam'].tolist() + df['AwayTeam'].tolist())))
        col1, col2 = st.columns(2)
        eq1 = col1.selectbox("🏠 Domicile", eqs, index=0)
        eq2 = col2.selectbox("✈️ Extérieur", eqs, index=1 if len(eqs) > 1 else 0)
        r1, r2, r3 = st.columns(3)
        cap_input = r1.number_input("💰 Bankroll (€)", min_value=1.0, value=capital_actuel, step=1.0)
        risque_pct = r2.select_slider("🎚️ Risque (%)", options=[2.5, 5.0, 7.5, 10.0], value=5.0)
        marge_val = r3.slider("🛡️ Sécurité (%)", 0, 20, 8, step=2)
        q1, q2, q3 = st.columns(3)
        c1 = q1.number_input("Cote 1", min_value=1.05, value=2.20, step=0.05)
        cn = q2.number_input("Cote N", min_value=1.50, value=3.30, step=0.05)
        c2 = q3.number_input("Cote 2", min_value=1.05, value=3.10, step=0.05)
        dnb = st.toggle("🛡️ Remboursé si nul (DNB sur 1 et 2)", value=True)
        algo_ver = st.radio("🧠 Moteur d'Analyse", ["⚡ V2 (Forme)", "🧬 V3 (Dixon-Coles)", "🤖 V4 (Méta-IA V2+V3)"], index=2, horizontal=True)

        if st.button("🔍 SCANNER LES 3 ISSUES (1 / N / 2)", type="primary", use_container_width=True):
            if not st.session_state.is_pro and st.session_state.analyses_count >= 3:
                st.error("🔒 Limite atteinte ! Passe en Pro dans l'onglet 🏆 Pro.")
            elif eq1 == eq2:
                st.warning("Choisis deux équipes différentes.")
            else:
                st.session_state.analyses_count += 1
                user_data["essai"] = st.session_state.analyses_count
                db[st.session_state.user_id] = user_data
                save_db(db)
                draw_hero()

                t3v, t3n, t3d, l1, l2 = run_algo(algo_ver, df, eq1, eq2)
                tot = max(1.0, t3v + t3n + t3d)

                issues_spec = [
                    ("1", f"🏠 {eq1} ({'DNB' if dnb else '1'})", (1 + t3d / t3v) if dnb else tot / t3v, (c1 * (cn - 1) / cn) if dnb else c1, 1.90 if dnb else 2.00, 3.50 if dnb else 5.00),
                    ("N", "🤝 Match Nul", tot / t3n, cn, 2.50, 4.50),
                    ("2", f"✈️ {eq2} ({'DNB' if dnb else '2'})", (1 + t3v / t3d) if dnb else tot / t3d, (c2 * (cn - 1) / cn) if dnb else c2, 1.90 if dnb else 2.00, 3.50 if dnb else 5.00)
                ]

                rapport = []
                for code_i, lbl, ct, cr, cmin, cmax in issues_spec:
                    ct_sec = ct * (1.0 + marge_val / 100.0)
                    ratio = cr / max(0.01, ct_sec)
                    if (cr > ct_sec) and (cmin <= cr <= cmax):
                        statut_col = "🟢 VALUE BET"
                        obj = (cap_input * (risque_pct / 100.0)) * (cr / 2.0)
                        mise = obj / max(0.01, cr - 1.0)
                    elif cr > ct:
                        statut_col = "🟡 VALUE FAIBLE"
                        obj, mise = 0.0, 0.0
                    else:
                        statut_col = "🔴 NO BET"
                        obj, mise = 0.0, 0.0

                    rapport.append({
                        "code": code_i, "label": lbl, "statut": statut_col,
                        "ct": round(ct, 2), "ct_sec": round(ct_sec, 2), "cr": round(cr, 2),
                        "mise": round(mise, 2), "obj": round(obj, 2), "ratio": ratio
                    })

                st.session_state.last_scan = {
                    "match": f"{eq1}-{eq2}", "fd_code": fd_code,
                    "l1": l1, "l2": l2, "rapport": rapport
                }

        if st.session_state.last_scan and st.session_state.last_scan["match"] == f"{eq1}-{eq2}":
            scan = st.session_state.last_scan
            rapport = scan["rapport"]
            st.info(f"🔮 **Score Exact tendance :** {eq1} **{round(scan['l1'])} - {round(scan['l2'])}** {eq2}")

            cols = st.columns(3)
            for idx, item in enumerate(rapport):
                with cols[idx]:
                    st.markdown(f"**{item['label']}**")
                    if "🟢" in item["statut"]:
                        st.success(f"**{item['statut']}**\n\nCote : **{item['cr']:.2f}** (Seuil {item['ct_sec']:.2f})\n\nMise : **{item['mise']:.2f} €** (+{item['obj']:.2f} €)")
                    elif "🟡" in item["statut"]:
                        st.warning(f"**{item['statut']}**\n\nCote : **{item['cr']:.2f}** (Juste {item['ct']:.2f})\n\nSeuil requis : {item['ct_sec']:.2f}")
