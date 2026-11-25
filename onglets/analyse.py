import streamlit as st
from datetime import datetime
from moteur import CHAMPIONNATS, save_db, fetch_matches, calc_v2, calc_v3_dixon_coles, calc_v4_meta, poisson_score

@st.cache_data(ttl=3600, show_spinner="Chargement des matchs officiels...")
def get_cached_matches(codes):
    return fetch_matches(codes)

def run_algo(algo_name, df, eq1, eq2):
    if "V4" in algo_name:
        return calc_v4_meta(df, eq1, eq2)
    if "V3" in algo_name:
        return calc_v3_dixon_coles(df, eq1, eq2)
    return calc_v2(df, eq1, eq2)

def render_analyse(db, user_data, capital_actuel, draw_hero):
    ligue = st.selectbox("🏟️ Compétition (Temps Réel)", list(CHAMPIONNATS.keys()))
    fd_code = CHAMPIONNATS[ligue]
    df, err = get_cached_matches(CHAMPIONNATS[ligue])
    if df.empty:
        st.warning(f"⚠️ Flux indisponible ({err}).")
        return

    st.caption(f"✅ Flux officiel actif : **{len(df)} matchs terminés**.")
    eqs = sorted(list(set(df['HomeTeam'].tolist() + df['AwayTeam'].tolist())))
    col1, col2 = st.columns(2)
    eq1 = col1.selectbox("🏠 Domicile", eqs, index=0)
    eq2 = col2.selectbox("✈️ Extérieur", eqs, index=1 if len(eqs) > 1 else 0)

    r1, r2, r3 = st.columns(3)
    cap_input = r1.number_input("💰 Bankroll (€)", min_value=1.0, value=capital_actuel, step=1.0)
    risque_pct = r2.select_slider("🎚️ Risque (%)", options=[2.5, 5.0, 7.5, 10.0], value=5.0)
    marge_val = r3.slider("🛡️ Sécurité (%)", 0, 20, 8, step=2)

    q1, q2, q3 = st.columns(3)
    c1 = q1.number_input("Cote 1", min_value=1.05, value=2.20, step=0.05)
    cn = q2.number_input("Cote N", min_value=1.50, value=3.30, step=0.05)
    c2 = q3.number_input("Cote 2", min_value=1.05, value=3.10, step=0.05)
    dnb = st.toggle("🛡️ Remboursé si nul (DNB sur 1 et 2)", value=True)
    algo_ver = st.radio("🧠 Moteur d'Analyse", ["⚡ V2 (Forme)", "🧬 V3 (Dixon-Coles)", "🤖 V4 (Méta-IA V2+V3)"], index=2, horizontal=True)

    if st.button("🔍 SCANNER LES 3 ISSUES (1 / N / 2)", type="primary", use_container_width=True):
        if st.session_state.get("user_id", "Invite") == "Invite":
            st.warning("🔐 **Crée ton espace gratuit ci-dessus (Pseudo + Code PIN)** pour débloquer tes **3 analyses offertes** !")
        elif not st.session_state.is_pro and st.session_state.analyses_count >= 3:
            st.error("🔒 Limite atteinte ! Passe en Pro dans l'onglet 🏆 Pro.")
        elif eq1 == eq2:
            st.warning("Choisis deux équipes différentes.")
        else:
            st.session_state.analyses_count += 1
            user_data["essai"] = st.session_state.analyses_count
            db[st.session_state.user_id] = user_data
            save_db(db)
            draw_hero()

            t3v, t3n, t3d, l1, l2 = run_algo(algo_ver, df, eq1, eq2)
            tot = max(1.0, t3v + t3n + t3d)
            issues_spec = [
                ("1", f"🏠 {eq1} ({'DNB' if dnb else '1'})", (1 + t3d / t3v) if dnb else tot / t3v, (c1 * (cn - 1) / cn) if dnb else c1, c1, 1.90 if dnb else 2.00, 3.50 if dnb else 5.00),
                ("N", "🤝 Match Nul", tot / t3n, cn, cn, 2.50, 4.50),
                ("2", f"✈️ {eq2} ({'DNB' if dnb else '2'})", (1 + t3v / t3d) if dnb else tot / t3d, (c2 * (cn - 1) / cn) if dnb else c2, c2, 1.90 if dnb else 2.00, 3.50 if dnb else 5.00)
            ]
            rapport = []
            for code_i, lbl, ct, cr, c_sec, cmin, cmax in issues_spec:
                ct_sec = ct * (1.0 + marge_val / 100.0)
                ratio = cr / max(0.01, ct_sec)
                if not (cmin <= cr <= cmax):
                    statut_col, obj, mise = "🔴 HORS FOURCHETTE", 0.0, 0.0
                elif cr > ct_sec:
                    statut_col = "🟢 VALUE BET"
                    obj = (cap_input * (risque_pct / 100.0)) * (cr / 2.0)
                    mise = obj / max(0.01, cr - 1.0)
                elif cr > ct:
                    statut_col, obj, mise = "🟡 VALUE FAIBLE", 0.0, 0.0
                else:
                    statut_col, obj, mise = "🔴 NO BET", 0.0, 0.0
                rapport.append({"code": code_i, "label": lbl, "statut": statut_col, "ct": round(ct, 2), "ct_sec": round(ct_sec, 2), "cr": round(cr, 2), "c_sec": round(c_sec, 2), "mise": round(mise, 2), "obj": round(obj, 2), "ratio": ratio, "is_dnb": (dnb and code_i != "N")})

            st.session_state.last_scan = {"match": f"{eq1}-{eq2}", "fd_code": fd_code, "l1": l1, "l2": l2, "rapport": rapport}

    if st.session_state.last_scan and st.session_state.last_scan["match"] == f"{eq1}-{eq2}":
        scan = st.session_state.last_scan
        rapport = scan["rapport"]
        st.info(f"🔮 **Score Exact tendance :** {eq1} **{round(scan['l1'])} - {round(scan['l2'])}** {eq2}")
        cols = st.columns(3)
        for idx, item in enumerate(rapport):
            with cols[idx]:
                st.markdown(f"**{item['label']}**")
                cote_txt = f"**{item['cr']:.2f}** (DNB sur {item['c_sec']:.2f})" if item.get("is_dnb") else f"**{item['cr']:.2f}**"
                if "🟢" in item["statut"]:
                    st.success(f"**{item['statut']}**\n\nCote : {cote_txt} | Seuil {item['ct_sec']:.2f}\n\nMise : **{item['mise']:.2f} €** (+{item['obj']:.2f} €)")
                elif "🟡" in item["statut"]:
                    st.warning(f"**{item['statut']}**\n\nCote : {cote_txt} (Juste {item['ct']:.2f})\n\nSeuil requis : {item['ct_sec']:.2f}")
                else:
                    st.error(f"**{item['statut']}**\n\nCote : {cote_txt}\n\nCote juste : {item['ct']:.2f}")

        greens = [r for r in rapport if "🟢" in r["statut"]]
        if greens:
            best = max(greens, key=lambda x: x["ratio"])
            st.success(f"🏆 **Meilleure opportunité détectée :** **{best['label']}** — Mise : **{best['mise']:.2f} €** (Gain : **+{best['obj']:.2f} €**)")
            st.caption("📋 *Check-list rapide : vérifie les blessés/compos 1h avant le match.*")
            if st.button(f"➕ Enregistrer {best['label']} dans ma Bankroll", type="primary", use_container_width=True):
                user_data["paris"].append({"Date": datetime.now().strftime("%d/%m %H:%M"), "Code": scan["fd_code"], "Match": scan["match"], "Choix": best["label"].replace("🏠 ", "").replace("✈️ ", "").replace("🤝 ", ""), "Cote": best["cr"], "Mise (€)": best["mise"], "Gain Visé (€)": best["obj"], "Statut": "⏳ En cours"})
                db[st.session_state.user_id] = user_data
                save_db(db)
                st.success("✅ Pari enregistré dans ta Bankroll et synchronisé !")
        else:
            st.warning("⏸️ **Aucune opportunité verte sur ce match** — La discipline consiste à passer son tour.")

    with st.expander("🎯 Calculateur de Mise — Score Exact (Loi de Poisson)", expanded=False):
        _, _, _, l1, l2 = run_algo(algo_ver, df, eq1, eq2)
        s1, s2, s3 = st.columns(3)
        g1 = s1.number_input("Buts Dom.", 0, 8, int(round(l1)))
        g2 = s2.number_input("Buts Ext.", 0, 8, int(round(l2)))
        c_sc = s3.number_input("Cote Score", 3.0, 200.0, 10.0, step=0.25)
        ct_sc, prob_sc = poisson_score(l1, l2, g1, g2)
        mise_sc = round(min(cap_input * 0.025, (cap_input * 0.025) * (10.0 / max(5.0, c_sc))), 2)
        k1, k2, k3 = st.columns(3)
        k1.metric("Cote Juste Poisson", f"{ct_sc:.2f}"); k2.metric("Probabilité", f"{prob_sc}%"); k3.metric("Mise Max (≤2.5%)", f"{mise_sc:.2f} €")
        if c_sc > ct_sc:
            st.success(f"✅ **Value Score Exact ({g1}-{g2})** — Mise : **{mise_sc:.2f} €**")
        else:
            st.caption(f"⏸️ Cote ({c_sc:.2f}) < Juste ({ct_sc:.2f}) — Micro-mise fun : {mise_sc:.2f} € max.")
        if st.button("➕ Enregistrer ce Score Exact", use_container_width=True):
            if st.session_state.get("user_id", "Invite") == "Invite":
                st.warning("🔐 Connecte-toi ci-dessus pour enregistrer ce score dans ta bankroll.")
            else:
                user_data["paris"].append({"Date": datetime.now().strftime("%d/%m %H:%M"), "Code": fd_code, "Match": f"{eq1}-{eq2}", "Choix": f"Score {g1}-{g2}", "Cote": round(c_sc, 2), "Mise (€)": mise_sc, "Gain Visé (€)": round(mise_sc * (c_sc - 1), 2), "Statut": "⏳ En cours"})
                db[st.session_state.user_id] = user_data
                save_db(db)
                st.success("✅ Ajouté !")
                
