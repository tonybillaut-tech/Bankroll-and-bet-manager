import streamlit as st
import pandas as pd
import io, urllib.parse
from moteur import load_db, save_db, get_cap, check_results
from database import hash_pin
from onglets.analyse import render_analyse
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

tab_calc, tab_suivi, tab_bt, tab_tuto, tab_pro = st.tabs(["⚽ Analyse", "💰 Bankroll", "📊 Backtest", "📘 Guide", "🏆 Pro"])

with tab_calc: render_analyse(db, user_data, capital_actuel, draw_hero)

with tab_suivi:
    st.subheader(f"💰 Bankroll de {st.session_state.user_id}")
    b1, b2 = st.columns(2)
    nouv_dep = b1.number_input("Départ (€)", min_value=1.0, value=float(user_data.get("capital_depart", 20.0)), step=5.0)
    if nouv_dep != user_data.get("capital_depart", 20.0): user_data["capital_depart"] = nouv_dep; db[st.session_state.user_id] = user_data; save_db(db); st.rerun()
    b2.metric("Actuel", f"{capital_actuel:.2f} €", delta=f"{capital_actuel - nouv_dep:+.2f} €")
    if st.button("🔄 Vérifier les matchs terminés", use_container_width=True):
        nb = check_results(user_data["paris"])
        if nb > 0: db[st.session_state.user_id] = user_data; save_db(db); st.success(f"✅ {nb} mis à jour !"); st.rerun()
        else: st.info("Aucun match terminé trouvé.")
    if not user_data["paris"]: st.info("Aucun pari validé.")
    else:
        for i, p in enumerate(user_data["paris"]):
            c_i, c_s = st.columns(2)
            c_i.write(f"⚽ **{p['Match']}** — {p['Choix']} (@{p['Cote']}) | {p['Mise (€)']}€")
            opts = ["⏳ En cours", "✅ Gagné", "🔄 Remboursé", "❌ Perdu"]
            ns = c_s.selectbox("Statut", opts, index=opts.index(p.get("Statut", "⏳ En cours")), key=f"st_{i}", label_visibility="collapsed")
            if ns != p.get("Statut"): user_data["paris"][i]["Statut"] = ns; db[st.session_state.user_id] = user_data; save_db(db); st.rerun()
        buf = io.BytesIO(); pd.DataFrame(user_data["paris"]).to_excel(buf, index=False)
        st.download_button("📥 Exporter Excel", buf.getvalue(), f"smartstake_{st.session_state.user_id}.xlsx", use_container_width=True)

with tab_bt: render_backtest()
with tab_tuto: render_guide()
with tab_pro: render_pro(db, user_data)

app_url = "https://" + "smartstake-app.streamlit.app/"
msg_wa = urllib.parse.quote(f"⚽ Découvre SmartStake Football, un scanner IA de Value Bets & gestion de bankroll (3 analyses gratuites) : {app_url}")
msg_tg = urllib.parse.quote("⚽ SmartStake Football — Scanner IA & Bankroll (3 essais offerts)")

with st.expander("📲 Partager SmartStake avec un ami", expanded=False):
    st.caption("Copie le lien en 1 clic ou envoie-le directement :")
    st.code(app_url, language=None)
    p1, p2 = st.columns(2)
    p1.link_button("🟢 WhatsApp", f"https://" + f"wa.me/?text={msg_wa}", use_container_width=True)
    p2.link_button("✈️ Telegram", f"https://" + f"t.me/share/url?url={urllib.parse.quote(app_url)}&text={msg_tg}", use_container_width=True)

st.caption("SmartStake Football v10.0 — SaaS Edition")
    
