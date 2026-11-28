import streamlit as st
import pandas as pd
from moteur import save_db, check_results

def _get_uid(db):
    if isinstance(db, dict):
        v_users = {k.lower(): k for k in db if k != "_v4_meta"}
        for v in [st.session_state.get(k) for k in ("user_id", "user", "username", "pseudo", "login")] + list(st.session_state.values()):
            if isinstance(v, str) and v.strip().lower() in v_users:
                return v_users[v.strip().lower()]
    return st.session_state.get("user_id", "")

def render_bankroll(user_data, db, capital_actuel):
    st.subheader("💰 Gestion de Bankroll")
    uid = _get_uid(db)
    cap_depart = float(user_data.get("capital_depart") or 20.0)
    col_b1, col_b2 = st.columns(2)
    col_b1.metric("Capital de départ", f"{cap_depart:.2f} €")
    col_b2.metric("Capital actuel", f"{capital_actuel:.2f} €")

    with st.expander("⚙️ Modifier le capital de départ", expanded=False):
        nouveau_cap = st.number_input("Nouveau montant (€)", 1.0, 100000.0, cap_depart, step=5.0, key="in_cap_dep")
        if st.button("💾 Enregistrer le capital", type="primary", use_container_width=True):
            user_data["capital_depart"] = round(float(nouveau_cap), 2)
            if uid:
                db[uid] = user_data
                save_db(db)
            st.rerun()

    paris = user_data.get("paris") if isinstance(user_data.get("paris"), list) else []
    if paris:
        st.dataframe(pd.DataFrame(paris), use_container_width=True)
        if st.button("🔄 Vérifier les résultats des matchs", use_container_width=True):
            user_data["paris"] = check_results(paris)
            if uid:
                db[uid] = user_data
                save_db(db)
            st.rerun()
    else:
        st.info("Aucun pari enregistré pour le moment. Lance une analyse dans l'onglet ⚽ Analyse.")
