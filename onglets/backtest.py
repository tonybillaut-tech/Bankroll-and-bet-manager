import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from database import load_db, SUPABASE_URL, _sb_headers
from moteur import CHAMPIONNATS, get_v4_params
from bt_core import LIGUES_EU, fetch_odds_df, simuler_df, entrainer_ligue

def scroll_to(anchor):
    components.html(f"<script>const el = window.parent.document.getElementById('{anchor}'); if (el) {{ el.scrollIntoView({{behavior: 'smooth', block: 'start'}}); }}</script>", height=0)

def render_backtest():
    st.subheader("📊 Backtest & Arène IA")
    db = load_db()
    mode = st.radio("Mode", ["⚔️ Duel IA", "🧠 Entraîner", "🏆 Top 10"], horizontal=True, label_visibility="collapsed")

    if mode == "🏆 Top 10":
        rows = [{"Ligue": n, "🤖 V4 (%)": round(float(get_v4_params(db, c).get("roi_bt", 0)), 1), "🦖 V5 (%)": get_v4_params(db, c).get("darwin_roi"), "Leader": "🦖 V5" if (get_v4_params(db, c).get("darwin_roi") or -999) > float(get_v4_params(db, c).get("roi_bt", 0)) else "🤖 V4"} for n, c in CHAMPIONNATS.items()]
        st.dataframe(pd.DataFrame(rows).sort_values("🦖 V5 (%)", ascending=False), use_container_width=True, hide_index=True)
        return

    custom_df = st.session_state.get("custom_df")
    has_custom = isinstance(custom_df, pd.DataFrame) and len(custom_df) >= 65
    ligue = st.selectbox("🏟️ Cible", (["📂 Ligue Perso (CSV)"] if has_custom else []) + ["🌍 Toutes les ligues (Portefeuille EU)"] + list(CHAMPIONNATS.keys()))
    is_all, is_custom = ligue.startswith("🌍"), ligue.startswith("📂")
    zone_prog = st.empty()

    with st.expander("⚙️ Paramètres (100€ • Marge 10% • DNB)", expanded=False):
        c1, c2 = st.columns(2)
        cap_init = c1.number_input("💰 Capital (€)", 10.0, 10000.0, 100.0, step=10.0)
        marge_pct = c2.slider("🛡️ Marge (%)", 0, 25, 10, step=2)
        dnb = st.toggle("🔄 DNB", value=True)

    fd_code = None if (is_all or is_custom) else CHAMPIONNATS.get(ligue)
    v4_cfg = get_v4_params(db, "CUSTOM_CSV" if is_custom else fd_code) if not is_all else {}

    if mode == "🧠 Entraîner":
        if st.button(f"🧠 Lancer l'entraînement ({ligue})", type="primary", use_container_width=True):
            bar = zone_prog.progress(10, text=f"Entraînement ({ligue})...")
            if is_all:
                for idx, nom_l in enumerate(LIGUES_EU):
                    bar.progress(int((idx / len(LIGUES_EU)) * 95), text=f"🧠 {nom_l}...")
                    codes_l = CHAMPIONNATS.get(nom_l)
                    df_l = fetch_odds_df(codes_l)
                    if len(df_l) >= 65:
                        entrainer_ligue(db, next(iter(codes_l)), df_l, cap_init, marge_pct, dnb)
                requests.patch(f"{SUPABASE_URL}/rest/v1/smartstake_users?user_id=eq._v4_meta", headers=_sb_headers(), json={"v4_meta": db["_v4_meta"]}, timeout=10)
                st.session_state["last_train"] = {"ligue": ligue, "multi": True}
            else:
                df = custom_df.copy() if is_custom else fetch_odds_df(fd_code)
                if len(df) >= 65:
                    bilan = entrainer_ligue(db, "CUSTOM_CSV" if is_custom else next(iter(fd_code)), df, cap_init, marge_pct, dnb, bar=bar)
                    if not is_custom:
                        requests.patch(f"{SUPABASE_URL}/rest/v1/smartstake_users?user_id=eq._v4_meta", headers=_sb_headers(), json={"v4_meta": db["_v4_meta"]}, timeout=8)
                    if bilan:
                        bilan["ligue"] = ligue
                        st.session_state["last_train"] = bilan
            bar.progress(100, text="✅ Terminé !")
            st.rerun()

        lt = st.session_state.get("last_train")
        if isinstance(lt, dict) and lt.get("ligue") == ligue:
            st.markdown('<div id="res-bt"></div>', unsafe_allow_html=True)
            st.info(f"🛡️ **Élitisme actif :** candidat (`{lt['try_v5']:+.1f}%`) < champion (`{lt['roi_v5']:+.1f}%`), ancien ADN conservé.") if lt.get("kept_old") else st.success(f"✅ **{ligue}** : record enregistré !")
            if not lt.get("multi"):
                t1, t2 = st.columns(2)
                t1.metric("🤖 V4", f"{lt['roi_v4']:+.1f}%", delta=f"{lt['p_v4']} paris")
                t2.metric("🦖 V5 Champion", f"{lt['roi_v5']:+.1f}%", delta=f"{lt['p_v5']} paris")
                if lt.get("hist_v5"):
                    st.line_chart(pd.DataFrame({"🦖 Candidat (€)": lt["hist_v5"]}))
            scroll_to("res-bt")
        return

    if st.button(f"⚔️ Lancer le Duel ({ligue})", type="primary", use_container_width=True):
        bar = zone_prog.progress(10, text="Simulation en cours...")
        if is_all:
            tot_p, tot_g, cap_l, hists = {"V2": 0, "V3": 0, "V4": 0, "V5": 0}, {"V2": 0.0, "V3": 0.0, "V4": 0.0, "V5": 0.0}, cap_init / len(LIGUES_EU), {"V2": [], "V3": [], "V4": [], "V5": []}
            for idx, nom_l in enumerate(LIGUES_EU):
                bar.progress(int((idx / len(LIGUES_EU)) * 90), text=f"⏳ {nom_l}...")
                codes_l = CHAMPIONNATS.get(nom_l)
                cfg_l = get_v4_params(db, codes_l)
                df_l = fetch_odds_df(codes_l)
                if len(df_l) >= 65:
                    for m_n, cv, av, gv in [("V2", 0.5, 0.8, None), ("V3", 0.5, 0.8, None), ("V4", cfg_l.get("C", 0.5), cfg_l.get("alpha", 0.8), None), ("V5", 0.5, 0.8, cfg_l.get("darwin_genes"))]:
                        pm, _, cf, _, hm = simuler_df(df_l, cap_l, marge_pct, dnb, m_n, cv, av, gv, step_v4=35)
                        tot_p[m_n] += pm
                        tot_g[m_n] += (cf - cap_l)
                        hists[m_n].append(hm)
            res = {k: (t, round(cap_init + tot_g[k], 2), round((tot_g[k]/cap_init)*100, 1), tot_p[k]) for k, t in [("V2", "⚡ V2"), ("V3", "🧬 V3"), ("V4", "🤖 V4"), ("V5", "🦖 V5")]}
            min_l = min((len(x) for ml in hists.values() for x in ml if len(x) > 0), default=0)
            courbes = {t: [round(sum(c), 2) for c in zip(*[x[-min_l:] for x in hists[k] if len(x) >= min_l])] for k, t in [("V2", "⚡ V2"), ("V3", "🧬 V3"), ("V4", "🤖 V4"), ("V5", "🦖 V5")] if min_l > 0}
        else:
            df = custom_df.copy() if is_custom else fetch_odds_df(fd_code)
            p2, _, c2, r2, h2 = simuler_df(df, cap_init, marge_pct, dnb, "V2")
            p3, _, c3, r3, h3 = simuler_df(df, cap_init, marge_pct, dnb, "V3")
            p4, _, c4, r4, h4 = simuler_df(df, cap_init, marge_pct, dnb, "V4", v4_cfg.get("C", 0.5), v4_cfg.get("alpha", 0.8))
            p5, _, c5, r5, h5 = simuler_df(df, cap_init, marge_pct, dnb, "V5", darwin_genes=v4_cfg.get("darwin_genes"))
            m = min(len(h2), len(h3), len(h4), len(h5))
            res = {"V2": ("⚡ V2", c2, r2, p2), "V3": ("🧬 V3", c3, r3, p3), "V4": ("🤖 V4", c4, r4, p4), "V5": ("🦖 V5", c5, r5, p5)}
            courbes = {"⚡ V2": h2[-m:], "🧬 V3": h3[-m:], "🤖 V4": h4[-m:], "🦖 V5": h5[-m:]}
        bar.progress(100, text="✅ Terminé !")
        st.markdown('<div id="res-bt"></div>', unsafe_allow_html=True)
        c2, c3 = st.columns(2)
        for col, keys in [(c2, ("V2", "V4")), (c3, ("V3", "V5"))]:
            for k in keys:
                t, cf, rf, np_ = res[k]
                col.metric(t, f"{cf:.2f} €", delta=f"{rf:+.1f}% ({np_}p)")
        if courbes:
            st.line_chart(pd.DataFrame(courbes))
        scroll_to("res-bt")
                
