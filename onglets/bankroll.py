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
    paris = user_data.get("paris") if isinstance(user_data.get("paris"), list) else []

    gains_potentiels = 0.0
    mises_en_cours = 0.0
    for p in paris:
        st_p = str(p.get("Statut", ""))
        if "⏳" in st_p or "cours" in st_p:
            mise = float(p.get("Mise (€)", p.get("Mise", 0.0)) or 0.0)
            cote = float(p.get("Cote", 1.0) or 1.0)
            mises_en_cours += mise
            gains_potentiels += mise * cote

    bk_si_gain = round(capital_actuel + gains_potentiels, 2)
    bk_si_perte = round(capital_actuel, 2)
    diff_depart = round(capital_actuel - cap_depart, 2)

    st.metric(
        "💰 Montant de la Bankroll",
        f"{capital_actuel:.2f} €",
        delta=f"{diff_depart:+.2f} € vs départ ({cap_depart:.2f} €)"
    )

    c1, c2 = st.columns(2)
    c1.metric(
        "📈 Si gain(s)",
        f"{bk_si_gain:.2f} €",
        delta=f"+{gains_potentiels:.2f} €" if mises_en_cours > 0 else "Aucun pari en cours"
    )
    c2.metric(
        "📉 Si perte(s)",
        f"{bk_si_perte:.2f} €",
        delta=f"-{mises_en_cours:.2f} € engagés" if mises_en_cours > 0 else "0.00 € en jeu",
        delta_color="inverse" if mises_en_cours > 0 else "off"
    )

    with st.expander("⚙️ Modifier le capital de départ", expanded=False):
        nouveau_cap = st.number_input("Nouveau montant (€)", 1.0, 100000.0, cap_depart, step=5.0, key="in_cap_dep")
        if st.button("💾 Enregistrer le capital", type="primary", use_container_width=True):
            user_data["capital_depart"] = round(float(nouveau_cap), 2)
            if uid:
                db[uid] = user_data
                save_db(db)
            st.rerun()

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
