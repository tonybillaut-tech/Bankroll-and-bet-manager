import streamlit as st
from moteur import save_db

def render_guide():
    st.subheader("📘 Guide SmartStake")
    st.write("**1. Profil :** Ouvre *👤 Mon Espace Parieur* et tape ton pseudo ou e-mail (sauvegarde cloud permanente).")
    st.write("**2. Analyse 1N2 & Score Exact :** Teste le 1N2 ou déplie *🎯 Calculateur de Mise — Score Exact* (loi de Poisson).")
    st.write("**3. Bankroll Auto :** Appuie sur *🔄 Vérifier les matchs terminés* dans *💰 Bankroll*.")
    st.write("**4. Backtest :** Simule la rentabilité face aux cotes Bet365 dans *📊 Backtest*.")

def render_pro(db, user_data):
    st.subheader("🏆 SmartStake Pro — 29,90 €/an")
    st.write("✅ **Analyses illimitées** sur les 10 compétitions + Backtest + Score exact Poisson + Cloud Sync.")
    mail = st.text_input("Ton e-mail :")
    if st.button("🚀 Activer Pro", type="primary", use_container_width=True) and "@" in mail:
        st.session_state.is_pro = True
        user_data["is_pro"] = True
        db[st.session_state.user_id] = user_data
        save_db(db)
        st.success("🎉 Pro activé !")
      
