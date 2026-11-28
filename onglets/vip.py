import streamlit as st
from database import save_db, redeem_vip_code

STRIPE_URL = st.secrets.get("STRIPE_LINK", "https://stripe.com")
CODE_PROMO_VIP = st.secrets.get("VIP_CODE", "SMARTSTAKE2026")

def render_vip(db, user, is_pro, is_android=False):
    st.subheader("💎 Espace VIP Pro — SmartStake")
    u_data = db.get(user, {}) if isinstance(db, dict) else {}

    if is_pro:
        st.success(f"👑 **Statut VIP PRO actif** pour **{user}** — Accès illimité aux 4 moteurs d'IA (`V2`, `V3`, `V4`, `🦖 V5 Darwin`) et au suivi de bankroll.")
    else:
        essais = int(u_data.get("essai") or 0)
        restants = max(0, 10 - essais)
        st.warning(f"🆓 **Mode Découverte** : il te reste **{restants} analyse(s) gratuite(s)** sur 10.")

    st.markdown("""
    ### Ce que débloque l'abonnement VIP Pro :
    * **Analyses prédictives illimitées** sur les 10 plus grands championnats + ligues personnalisées CSV
    * **Accès complet à 🦖 V5 Darwin** (l'IA génétique auto-évolutive entraînée chaque semaine dans le cloud)
    * **Détection automatique des Value Bets** et calcul de mise optimale (critère de Kelly fractionné)
    * **Suivi complet de Bankroll** et vérification automatique des résultats
    """)

    if not is_pro:
        st.divider()
        if is_android:
            st.info("📱 **Abonnement via Google Play Store :** bientôt disponible directement depuis l'application Android.")
        else:
            st.link_button("🚀 Passer VIP Pro maintenant", STRIPE_URL, type="primary", use_container_width=True)

    st.divider()
    with st.expander("🎟️ Activer un Code Promo / Accès Testeur"):
        code_in = st.text_input("Entre ton code d'activation", type="password", key="vip_code_input").strip()
        if st.button("Valider le code", use_container_width=True):
            if code_in and (code_in == CODE_PROMO_VIP or redeem_vip_code(code_in, user)):
                u_data["is_pro"] = True
                db[user] = u_data
                save_db(db)
                st.success("✅ Code validé ! Ton compte est désormais **VIP PRO**.")
                st.rerun()
            else:
                st.error("Code invalide.")
