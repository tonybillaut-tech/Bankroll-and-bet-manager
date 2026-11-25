import streamlit as st
from moteur import save_db

def render_guide():
    st.subheader("📘 Guide Complet SmartStake")
    st.write("**1. Profil Cloud :** Ouvre *👤 Mon Espace Parieur* et entre ton pseudo ou e-mail pour sauvegarder ta bankroll à vie.")
    st.write("**2. Analyse 1N2 & Marge de Sécurité :** Règle ta *Marge sécurité Value (%)* (8 % conseillé) et valide uniquement les signaux verts **VALUE BET**.")
    st.write("**3. Check-list avant match :** Vérifie toujours 1h avant le coup d'envoi l'absence de blessés majeurs ou de rotation d'effectif.")
    st.write("**4. Backtest & Classement :** Utilise *📊 Backtest* pour repérer les championnats les plus rentables (ex. Primeira Liga, La Liga, Serie A) et tester tes réglages.")
    st.divider()
    st.caption("⚖️ **Mentions Légales & Jeu Responsable :** SmartStake est un outil indépendant d'analyse statistique et de gestion de bankroll. Aucun pari en argent réel n'est pris dans l'application. Réservé aux personnes majeures (**18+**). Jouer comporte des risques : **09 74 75 13 13**.")

def render_pro(db, user_data):
    st.subheader("🏆 SmartStake Pro — 29,90 €/an")
    st.write("✨ **Passe au niveau supérieur avec une méthode disciplinée :**")
    st.write("• **Analyses illimitées** sur les 10 plus grandes compétitions en direct\n• **Marge de sécurité Value** + calcul automatique **DNB**\n• **Calculateur Score Exact** (Loi de Poisson) plafonné à ≤ 2,5 %\n• **Audit comparatif** des 10 championnats + **Sauvegarde Cloud**")
    
    st.link_button("💳 Régler 29,90 € via PayPal (`@TonyBillaut`)", "https://paypal.com", type="primary", use_container_width=True)
    st.info("💡 **Astuce mobile :** Indique bien ton **pseudo SmartStake** en note du paiement PayPal pour recevoir ton **code VIP**.")

    if st.session_state.get("is_pro"):
        st.success("✅ Ton statut **SmartStake Pro** est déjà actif sur ce profil !")
        return

    code_saisi = st.text_input("🔑 Déjà réglé ? Entre ton code d'activation VIP :")
    vip_secret = str(st.secrets.get("VIP_CODE", "SMART2026")).strip().upper()
    
    if st.button("✅ Débloquer mon accès Pro", use_container_width=True):
        if st.session_state.get("user_id", "Invite") == "Invite":
            st.warning("⚠️ Ouvre d'abord **👤 Mon Espace Parieur** en haut de la page pour enregistrer ton propre pseudo avant d'activer ton code.")
        elif code_saisi.strip().upper() == vip_secret:
            st.session_state.is_pro = True
            user_data["is_pro"] = True
            db[st.session_state.user_id] = user_data
            save_db(db)
            st.success("🎉 Accès SmartStake Pro activé sur ton profil !")
            st.rerun()
        else:
            st.error("❌ Code invalide. Vérifie le code reçu après ton paiement PayPal.")
            
