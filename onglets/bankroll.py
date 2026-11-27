import streamlit as st
import pandas as pd
from moteur import save_db, check_results

def render_bankroll(user_data, db, capital_actuel):
    st.subheader("💰 Gestion de Bankroll")
    cap_depart = float(user_data.get("capital_depart") or 20.0)
    col_b1, col_b2 = st.columns(2)
    col_b1.metric("Capital de départ", f"{cap_depart:.2f} €")
    col_b2.metric("Capital actuel", f"{capital_actuel:.2f} €")

    with st.expander("⚙️ Modifier le capital de départ", expanded=False):
        nouveau_cap = st.number_input(
            "Nouveau montant (€)",
            min_value=1.0,
            max_value=100000.0,
            value=cap_depart,
            step=5.0,
            key="input_cap_depart"
        )
        if st.button("💾 Enregistrer le capital", type="primary", use_container_width=True):
            user_data["capital_depart"] = round(float(nouveau_cap), 2)
            db[st.session_state.user_id] = user_data
            save_db(db)
            st.success(f"Capital de départ mis à jour : {nouveau_cap:.2f} €")
            st.rerun()

    paris = user_data.get("paris") if isinstance(user_data.get("paris"), list) else []
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
        
