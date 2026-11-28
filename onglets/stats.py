import streamlit as st
import pandas as pd
from database import load_db

def _get_uid(db):
    if isinstance(db, dict):
        v_users = {k.lower(): k for k in db if k != "_v4_meta"}
        for v in [st.session_state.get(k) for k in ("user_id", "user", "username", "pseudo", "login")] + list(st.session_state.values()):
            if isinstance(v, str) and v.strip().lower() in v_users:
                return v_users[v.strip().lower()]
    return st.session_state.get("user_id", "")

def render_stats(user_data, db, capital_actuel):
    st.subheader("📈 Statistiques & Performance")
    fresh_db = load_db() or db
    uid = _get_uid(fresh_db)
    u = fresh_db.get(uid, user_data) if uid else user_data
    cap_dep = float(u.get("capital_depart") or 20.0)
    paris = u.get("paris") if isinstance(u.get("paris"), list) else []

    if not paris:
        st.info("Aucun pari enregistré pour le moment. Tes statistiques apparaîtront dès ton premier pari dans ⚽ Analyse.")
        return

    gagnes, perdus, remb, encours = 0, 0, 0, 0
    mise_totale, profit_net = 0.0, 0.0
    cotes_gagnantes = []
    serie_cur, serie_max, meilleur_gain = 0, 0, 0.0
    courbe = [cap_dep]
    cap_run = cap_dep
    par_ligue = {}

    for p in paris:
        st_p = str(p.get("Statut", ""))
        mise = float(p.get("Mise (€)", p.get("Mise", 0.0)) or 0.0)
        cote = float(p.get("Cote", 1.0) or 1.0)
        lig = str(p.get("Code") or "Autre")

        if "✅" in st_p or "Gagné" in st_p:
            gagnes += 1
            gain_p = mise * (cote - 1.0)
            mise_totale += mise
            profit_net += gain_p
            cap_run += gain_p
            courbe.append(round(cap_run, 2))
            cotes_gagnantes.append(cote)
            serie_cur += 1
            serie_max = max(serie_max, serie_cur)
            meilleur_gain = max(meilleur_gain, gain_p)
            par_ligue.setdefault(lig, {"Paris": 0, "Gagnés": 0, "Bilan (€)": 0.0})
            par_ligue[lig]["Paris"] += 1
            par_ligue[lig]["Gagnés"] += 1
            par_ligue[lig]["Bilan (€)"] += gain_p
        elif "❌" in st_p or "Perdu" in st_p:
            perdus += 1
            mise_totale += mise
            profit_net -= mise
            cap_run -= mise
            courbe.append(round(cap_run, 2))
            serie_cur = 0
            par_ligue.setdefault(lig, {"Paris": 0, "Gagnés": 0, "Bilan (€)": 0.0})
            par_ligue[lig]["Paris"] += 1
            par_ligue[lig]["Bilan (€)"] -= mise
        elif "🔄" in st_p or "Remboursé" in st_p:
            remb += 1
        else:
            encours += 1

    termines = gagnes + perdus
    winrate = (gagnes / termines * 100.0) if termines > 0 else 0.0
    roi = (profit_net / mise_totale * 100.0) if mise_totale > 0 else 0.0
    cote_moy = (sum(cotes_gagnantes) / len(cotes_gagnantes)) if cotes_gagnantes else 0.0

    r1_c1, r1_c2 = st.columns(2)
    r1_c1.metric("🎯 Taux de réussite", f"{winrate:.1f}%", f"{gagnes}G / {perdus}P ({remb} remb.)")
    r1_c2.metric("📊 ROI Global", f"{roi:+.1f}%", f"{profit_net:+.2f} € net")

    r2_c1, r2_c2 = st.columns(2)
    r2_c1.metric("💎 Cote moy. gagnante", f"{cote_moy:.2f}" if cote_moy > 0 else "—", f"Max : +{meilleur_gain:.2f} €")
    r2_c2.metric("🔥 Meilleure série", f"{serie_max} victoire(s)", f"{encours} en cours")

    if len(courbe) > 1:
        st.markdown("#### 📈 Évolution de la Bankroll (€)")
        df_courbe = pd.DataFrame({"Bankroll (€)": courbe})
        st.line_chart(df_courbe, use_container_width=True)

    if par_ligue:
        st.markdown("#### 🏟️ Bilan par Compétition")
        rows = []
        for k, v in sorted(par_ligue.items(), key=lambda x: x[1]["Bilan (€)"], reverse=True):
            taux = (v["Gagnés"] / v["Paris"] * 100.0) if v["Paris"] > 0 else 0.0
            rows.append({"Ligue": k, "Paris": v["Paris"], "Réussite": f"{taux:.0f}%", "Bilan (€)": round(v["Bilan (€)"], 2)})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
