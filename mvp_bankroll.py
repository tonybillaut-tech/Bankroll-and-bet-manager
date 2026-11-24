import streamlit as st
import pandas as pd
import io
from datetime import datetime
from moteur import CHAMPIONNATS, load_db, save_db, get_cap, fetch_matches, calc_v2, poisson_score, check_results, run_financial_backtest

st.set_page_config(page_title="SmartStake Foot", page_icon="⚽", layout="centered")
st.markdown("""<style>.hero{background:linear-gradient(135deg,#064e3b,#15803d);padding:16px;border-radius:14px;color:white;margin-bottom:10px;border:1px solid #22c55e}.hero h1{margin:0;font-size:1.6rem;color:#fff}.hero p{margin:4px 0 0;font-size:.9rem;color:#dcfce7}.stButton>button[kind="primary"]{background-color:#16a34a;border-color:#16a34a;color:white;font-weight:700;border-radius:10px;height:3em}</style>""", unsafe_allow_html=True)

if "db" not in st.session_state: st.session_state.db = load_db()
db = st.session_state.db
for k, v in [("user_id", "Invite"), ("analyses_count", 0), ("is_pro", False)]:
    if k not in st.session_state: st.session_state[k] = v

badge = "PRO ✨" if st.session_state.is_pro else f"Essai : {max(0, 3 - st.session_state.analyses_count)}/3"
st.markdown(f'<div class="hero"><h1>⚽ SmartStake — Paris Sportifs Foot</h1><p>10 Compétitions Live • Algo V2 • Score Exact • <b>{badge}</b></p></div>', unsafe_allow_html=True)
st.caption("⚖️ Aide statistique (aucune garantie de gain). **18+ | Jouer comporte des risques** : **09 74 75 13 13**.")

with st.expander("👤 Mon Espace Parieur", expanded=False):
    pseudo = st.text_input("Pseudo ou e-mail :", value=st.session_state.user_id)
    if pseudo and pseudo != st.session_state.user_id:
        st.session_state.user_id = pseudo
        if pseudo not in db: db[pseudo] = {"capital_depart": 20.0, "paris": [], "is_pro": False}; save_db(db)
        st.session_state.is_pro = db[pseudo].get("is_pro", False); st.rerun()

if st.session_state.user_id not in db: db[st.session_state.user_id] = {"capital_depart": 20.0, "paris": [], "is_pro": False}
user_data = db[st.session_state.user_id]
capital_actuel = get_cap(user_data)

@st.cache_data(ttl=3600, show_spinner="Chargement des matchs officiels...")
def get_cached_matches(codes):
    return fetch_matches(codes)

tab_calc, tab_suivi, tab_bt, tab_tuto, tab_pro = st.tabs(["⚽ Analyse", "💰 Bankroll", "📊 Backtest", "📘 Guide", "🏆 Pro"])

with tab_calc:
    ligue = st.selectbox("🏟️ Compétition (Temps Réel)", list(CHAMPIONNATS.keys()))
    fd_code = CHAMPIONNATS[ligue][0]
    df, err = get_cached_matches(CHAMPIONNATS[ligue])
    if df.empty: st.warning(f"⚠️ Flux indisponible ({err}).")
    else:
        st.caption(f"✅ Flux officiel actif : **{len(df)} matchs terminés**.")
        eqs = sorted(list(set(df['HomeTeam'].tolist() + df['AwayTeam'].tolist())))
        col1, col2 = st.columns(2)
        eq1 = col1.selectbox("🏠 Domicile", eqs, index=0)
        eq2 = col2.selectbox("✈️ Extérieur", eqs, index=1 if len(eqs) > 1 else 0)
        issue = st.radio("🎯 Pronostic 1N2", ["🏠 Équipe 1", "🤝 Match Nul", "✈️ Équipe 2"], index=2, horizontal=True)
        r1, r2 = st.columns(2)
        cap_input = r1.number_input("💰 Bankroll (€)", min_value=1.0, value=capital_actuel, step=1.0)
        risque_pct = r2.select_slider("🎚️ Risque 1N2 (%)", options=[2.5, 5.0, 7.5, 10.0], value=5.0)
        q1, q2, q3 = st.columns(3)
        c1 = q1.number_input("Cote 1", min_value=1.05, value=2.20, step=0.05)
        cn = q2.number_input("Cote N", min_value=1.50, value=3.30, step=0.05)
        c2 = q3.number_input("Cote 2", min_value=1.05, value=3.10, step=0.05)
        dnb = st.toggle("🛡️ Remboursé si nul (DNB)", value=True) if issue != "🤝 Match Nul" else False

        if st.button("⚽ ANALYSER LE 1N2 & CALCULER LA MISE", type="primary", use_container_width=True):
            if not st.session_state.is_pro and st.session_state.analyses_count >= 3: st.error("🔒 Limite atteinte ! Passe en Pro.")
            elif eq1 == eq2: st.warning("Choisis deux équipes différentes.")
            else:
                st.session_state.analyses_count += 1
                t3v, t3n, t3d, l1, l2 = calc_v2(df, eq1, eq2); tot = max(1.0, t3v + t3n + t3d)
                if issue == "🏠 Équipe 1": ct, cr, cmin, cmax, lbl = ((1 + t3d/t3v) if dnb else tot/t3v), ((c1*(cn-1)/cn) if dnb else c1), (1.90 if dnb else 2.00), (3.50 if dnb else 5.00), f"{eq1} ({'DNB' if dnb else '1'})"
                elif issue == "🤝 Match Nul": ct, cr, cmin, cmax, lbl = tot/t3n, cn, 2.50, 4.50, "Match Nul"
                else: ct, cr, cmin, cmax, lbl = ((1 + t3v/t3d) if dnb else tot/t3d), ((c2*(cn-1)/cn) if dnb else c2), (1.90 if dnb else 2.00), (3.50 if dnb else 5.00), f"{eq2} ({'DNB' if dnb else '2'})"
                ok = (cr > ct) and (cmin <= cr <= cmax)
                obj = (cap_input * (risque_pct / 100.0)) * (cr / 2.0) if ok else 0.0
                mise = obj / (cr - 1.0) if (ok and cr > 1) else 0.0
                m1, m2, m3 = st.columns(3)
                m1.metric("Cote Juste V2", f"{ct:.2f}"); m2.metric("Cote Jouée", f"{cr:.2f}"); m3.metric("Mise 1N2", f"{mise:.2f} €")
                st.info(f"🔮 **Score Exact tendance :** {eq1} **{round(l1)} - {round(l2)}** {eq2}")
                if ok:
                    conf = "🔥 Confiance Élevée" if (cr / ct) >= 1.12 else "⚖️ Confiance Modérée"
                    st.success(f"✅ **VALUE BET ({conf}) — PARIER {mise:.2f} €** sur **{lbl}** (Gain : **+{obj:.2f} €**)")
                    user_data["paris"].append({"Date": datetime.now().strftime("%d/%m %H:%M"), "Code": fd_code, "Match": f"{eq1}-{eq2}", "Choix": lbl, "Cote": round(cr, 2), "Mise (€)": round(mise, 2), "Gain Visé (€)": round(obj, 2), "Statut": "⏳ En cours"})
                    db[st.session_state.user_id] = user_data; save_db(db)
                else: st.warning(f"⏸️ **NO BET (PASSER)** — Cote {cr:.2f} vs Juste {ct:.2f}")

        with st.expander("🎯 Calculateur de Mise — Score Exact (Loi de Poisson)", expanded=False):
            _, _, _, l1, l2 = calc_v2(df, eq1, eq2)
            s1, s2, s3 = st.columns(3)
            g1 = s1.number_input("Buts Dom.", 0, 8, int(round(l1)))
            g2 = s2.number_input("Buts Ext.", 0, 8, int(round(l2)))
            c_sc = s3.number_input("Cote Score", 3.0, 200.0, 10.0, step=0.25)
            ct_sc, prob_sc = poisson_score(l1, l2, g1, g2)
            mise_sc = round(min(cap_input * 0.025, (cap_input * 0.025) * (10.0 / max(5.0, c_sc))), 2)
            k1, k2, k3 = st.columns(3)
            k1.metric("Cote Juste Poisson", f"{ct_sc:.2f}"); k2.metric("Probabilité", f"{prob_sc}%"); k3.metric("Mise Max (≤2.5%)", f"{mise_sc:.2f} €")
            if c_sc > ct_sc: st.success(f"✅ **Value Score Exact ({g1}-{g2})** — Mise conseillée : **{mise_sc:.2f} €**")
            else: st.caption(f"⏸️ Cote bookmaker ({c_sc:.2f}) sous la cote juste Poisson ({ct_sc:.2f}) — Micro-mise fun : {mise_sc:.2f} € max.")
            if st.button("➕ Enregistrer ce Score Exact dans ma Bankroll", use_container_width=True):
                user_data["paris"].append({"Date": datetime.now().strftime("%d/%m %H:%M"), "Code": fd_code, "Match": f"{eq1}-{eq2}", "Choix": f"Score {g1}-{g2}", "Cote": round(c_sc, 2), "Mise (€)": mise_sc, "Gain Visé (€)": round(mise_sc * (c_sc - 1), 2), "Statut": "⏳ En cours"})
                db[st.session_state.user_id] = user_data; save_db(db); st.success("✅ Pari Score Exact ajouté !")

with tab_suivi:
    st.subheader(f"💰 Bankroll de {st.session_state.user_id}")
    b1, b2 = st.columns(2)
    nouv_dep = b1.number_input("Départ (€)", min_value=1.0, value=float(user_data.get("capital_depart", 20.0)), step=5.0)
    if nouv_dep != user_data.get("capital_depart", 20.0): user_data["capital_depart"] = nouv_dep; db[st.session_state.user_id] = user_data; save_db(db); st.rerun()
    b2.metric("Actuel", f"{capital_actuel:.2f} €", delta=f"{capital_actuel - nouv_dep:+.2f} €")
    if st.button("🔄 Vérifier automatiquement les matchs terminés", use_container_width=True):
        nb = check_results(user_data["paris"])
        if nb > 0: db[st.session_state.user_id] = user_data; save_db(db); st.success(f"✅ {nb} pari(s) mis à jour !"); st.rerun()
        else: st.info("Aucun match terminé trouvé.")
    if not user_data["paris"]: st.info("Aucun pari validé.")
    else:
        for i, p in enumerate(user_data["paris"]):
            c_i, c_s = st.columns(2)
            c_i.write(f"⚽ **{p['Match']}** — {p['Choix']} (@{p['Cote']}) | {p['Mise (€)']}€")
            opts = ["⏳ En cours", "✅ Gagné", "🔄 Remboursé", "❌ Perdu"]
            ns = c_s.selectbox("Statut", opts, index=opts.index(p.get("Statut", "⏳ En cours")), key=f"st_{i}", label_visibility="collapsed")
            if ns != p.get("Statut"): user_data["paris"][i]["Statut"] = ns; db[st.session_state.user_id] = user_data; save_db(db); st.rerun()
        buf = io.BytesIO(); pd.DataFrame(user_data["paris"]).to_excel(buf, index=False)
        st.download_button("📥 Exporter Excel", buf.getvalue(), f"smartstake_{st.session_state.user_id}.xlsx", use_container_width=True)

with tab_bt:
    st.subheader("📊 Backtest Financier (Cotes Réelles Bet365)")
    c_b1, c_b2 = st.columns(2)
    saison_sel = c_b1.selectbox("📅 Saison historique", ["2425", "2526"], format_func=lambda x: "Saison 2024/2025 (Complète)" if x=="2425" else "Saison 2025/2026 (En cours)")
    dnb_bt = c_b2.toggle("🛡️ Simuler avec DNB", value=True)
    if st.button("🚀 Lancer le Backtest Financier (100 € / ligue)", type="primary", use_container_width=True):
        res = []
        bar = st.progress(0)
        eu_ligues = [(k, v[1]) for k, v in CHAMPIONNATS.items() if v[1] not in ("BSA", "CL")]
        for idx, (nom, csv_c) in enumerate(eu_ligues):
            r = run_financial_backtest(csv_c, saison=saison_sel, cap_init=100.0, risque=5.0, use_dnb=dnb_bt)
            if r: res.append({"Compétition": nom, **r})
            bar.progress((idx + 1) / len(eu_ligues))
        if res:
            df_bt = pd.DataFrame(res)
            st.dataframe(df_bt, use_container_width=True, hide_index=True)
        
