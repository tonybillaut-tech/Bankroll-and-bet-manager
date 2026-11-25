import streamlit as st
import pandas as pd
from moteur import save_db, check_results

def render_bankroll(user_data, db, capital_actuel):
    st.subheader("💰 Gestion de Bankroll")
    col_b1, col_b2 = st.columns(2)
    col_b1.metric("Capital de départ", f"{user_data.get('capital_depart', 20.0):.2f} €")
    col_b2.metric("Capital actuel", f"{capital_actuel:.2f} €")

    paris = user_data.get("paris", [])
    if paris:
        df_paris = pd.DataFrame(paris)
        st.dataframe(df_paris, use_container_width=True)
        if st.button("🔄 Vérifier les résultats des matchs", use_container_width=True):
            user_data["paris"] = check_results(paris)
            db[st.session_state.user_id] = user_data
            save_db(db)
            st.rerun()
    else:
        st.info("Aucun pari enregistré pour le moment. Lance une analyse dans l'onglet ⚽ Analyse.")
      
