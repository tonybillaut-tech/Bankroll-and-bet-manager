import streamlit as st
from database import save_db

def render_guide():
    st.subheader("📘 Guide Complet SmartStake")
    st.write("**1. Espace Parieur Sécurisé :** Ouvre *👤 Espace Parieur Sécurisé* en haut de la page, choisis ton pseudo et un **code PIN** pour protéger et sauvegarder ta bankroll à vie.")
    st.write("**2. Scanner 360° & Moteurs IA :** Choisis ton moteur (**⚡ V2 Forme**, **🧬 V3 Dixon-Coles** ou **🤖 V4 Méta-IA**). L'application scanne les 3 issues (`1 / N / 2`) avec un code couleur clair : **🟢 VALUE BET** (pari recommandé), **🟡 VALUE FAIBLE** (surveillance) et **🔴 NO BET** (à éviter).")
    st.write("**3. Check-list avant match :** Vérifie toujours 1h avant le coup d'envoi l'absence de blessés majeurs ou de rotation d'effectif.")
    st.write("**4. Backtest & Classement :** Utilise *📊 Backtest* pour comparer V2, V3 et V4 sur les vraies cotes historiques Bet365 et repérer les championnats les plus rentables.")
    st.divider()
    st.caption("⚖️ **Mentions Légales & Jeu Responsable :** SmartStake est un outil indépendant d'analyse statistique et de gestion de bankroll. Aucun pari en argent réel n'est pris dans l'application. Réservé aux personnes majeures (**18+**). Jouer comporte des risques : **09 74 75 13 13**.")

def render_pro(db, user_data):
    st.subheader("🏆 SmartStake Pro — 29,90 €/an")
    st.write("✨ **Passe au niveau supérieur avec une méthode disciplinée (soit moins de 2,50 €/mois) :**")
    st.write("• **Analyses illimitées** sur les 10 plus grandes compétitions en direct\n• **Scanner 360° + Méta-IA V4** + calcul automatique **DNB**\n• **Calculateur Score Exact** (Loi de Poisson) plafonné à ≤ 2,5 %\n• **Audit comparatif** des 10 championnats + **Sauvegarde Cloud Sécurisée**")

    if st.session_state.get("is_pro") or user_data.get("is_pro"):
        st.success("✅ Ton statut **SmartStake Pro ✨** est déjà actif sur ce profil !")
        return

    pay_link = st.secrets.get("PAY_LINK", "")
    if pay_link:
        st.link_button("💳 Régler 29,90 €/an & Débloquer PRO instantanément", pay_link, type="primary", use_container_width=True)
        st.caption("⚡ *Après validation du paiement, tu es redirigé automatiquement et ton compte passe en PRO dans la seconde.*")
    else:
        st.link_button("💳 Régler 29,90 €/an via PayPal (`@TonyBillaut`)", "https://paypal.com", type="primary", use_container_width=True)
        st.info("💡 **Astuce mobile :** Indique bien ton **pseudo SmartStake** en note du paiement PayPal pour recevoir ton **code VIP**.")

    code_saisi = st.text_input("🔑 Déjà réglé ? Entre ton code d'activation VIP :")
    vip_secret = str(st.secrets.get("VIP_CODE", "SMART2026")).strip().upper()

    if st.button("✅ Débloquer mon accès Pro", use_container_width=True):
        if st.session_state.get("user_id", "Invite") == "Invite":
            st.warning("⚠️ Ouvre d'abord **👤 Espace Parieur Sécurisé** en haut de la page pour enregistrer ton propre pseudo et ton code PIN avant d'activer ton code.")
        elif code_saisi.strip().upper() == vip_secret:
            st.session_state.is_pro = True
            user_data["is_pro"] = True
            db[st.session_state.user_id] = user_data
            save_db(db)
            st.success("🎉 Accès SmartStake Pro activé sur ton profil !")
            st.rerun()
        else:
            st.error("❌ Code invalide. Vérifie le code reçu après ton paiement PayPal.")
            
