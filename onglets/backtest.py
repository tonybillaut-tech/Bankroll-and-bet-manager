import streamlit as st
import pandas as pd
import requests, io
from database import load_db, SUPABASE_URL, _sb_headers
from moteur import CHAMPIONNATS, fetch_matches, calc_v2, calc_v3_dixon_coles, calc_v4_meta, calc_v5_darwin, get_v4_params
from algo_v5 import run_evolution

LIGUES_EU = ("🇫🇷 Ligue 1", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship", "🇪🇸 La Liga", "🇮🇹 Serie A", "🇩🇪 Bundesliga", "🇵🇹 Primeira Liga", "🇳🇱 Eredivisie")

def fetch_odds_df(codes, saison="2526"):
    fd_code, csv_code = codes
    if csv_code not in ("CL", "BSA"):
        for s in (saison, "2425"):
            try:
                r = requests.get("".join(["ht", "tps:", "//", "www.football-data.co.uk/mmz4281/", s, "/", csv_code, ".csv"]), headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                if r.status_code == 200:
                    df = pd.read_csv(io.StringIO(r.text)).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR', 'B365H', 'B365D', 'B365A'])
                    if len(df) >= 60:
                        return df.reset_index(drop=True), True
            except Exception:
                pass
    df, _ = fetch_matches(codes)
    return df.reset_index(drop=True), False

def simuler_df(df, cap_init, marge_pct, dnb, algo="V3", C_val=0.5, alpha=0.80, darwin_genes=None, step_v4=25):
    cap, mise_tot, paris, gagnes, hist = cap_init, 0.0, 0, 0, []
    has_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
    mult = 1.0 + (marge_pct / 100.0)
    start_idx = 60 if algo in ("V4", "V5") else (25 if algo == "V3" else 15)

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        if algo == "V5":
            t3v, t3n, t3d, _, _ = calc_v5_darwin(df.iloc[:max(60, (i // 50) * 50)], row["HomeTeam"], row["AwayTeam"], cloud_genome=darwin_genes)
        elif algo == "V4":
            t3v, t3n, t3d, _, _ = calc_v4_meta(df.iloc[:max(60, (i // step_v4) * step_v4)], row["HomeTeam"], row["AwayTeam"], C_val=C_val, alpha=alpha)
        elif algo == "V3":
            t3v, t3n, t3d, _, _ = calc_v3_dixon_coles(df.iloc[:max(25, (i // 5) * 5)], row["HomeTeam"], row["AwayTeam"])
        else:
            t3v, t3n, t3d, _, _ = calc_v2(df.iloc[:i], row["HomeTeam"], row["AwayTeam"])

        tot = max(1.0, t3v + t3n + t3d)
        c1_o, cn_o, c2_o = (float(row["B365H"]), float(row["B365D"]), float(row["B365A"])) if has_odds else (2.25, 3.30, 3.10)
        cands = [("H", (1 + t3d / t3v) if dnb else tot / t3v, (c1_o * (cn_o - 1) / cn_o) if dnb else c1_o), ("A", (1 + t3v / t3d) if dnb else tot / t3d, (c2_o * (cn_o - 1) / cn_o) if dnb else c2_o)]
        cmin, cmax = (1.90, 3.50) if dnb else (2.00, 5.00)
        for side, ct, cr in cands:
            if cr > (ct * mult) and cmin <= cr <= cmax and cap > 1.0:
                mise = min(cap, ((cap * 0.05) * (cr / 2.0)) / (cr - 1.0))
                paris += 1
                mise_tot += mise
                if row["FTR"] == side:
                    cap += mise * (cr - 1.0)
                    gagnes += 1
                elif dnb and row["FTR"] == "D":
                    gagnes += 1
                else:
                    cap -= mise
                break
        hist.append(round(cap, 2))
    return paris, round(gagnes * 100 / max(1, paris), 1), round(cap, 2), round(((cap - cap_init) / max(1.0, mise_tot)) * 100, 1), hist

def entrainer_ligue(db, key, df, cap_init, marge_pct, dnb):
    best_score, best_res = -9999.0, None
    for c_try, a_try in ((0.2, 0.75), (0.5, 0.80), (1.0, 0.85), (2.0, 0.90)):
        p_t, _, _, roi_t, _ = simuler_df(df, cap_init, marge_pct, dnb, "V4", c_try, a_try, step_v4=45)
        score = roi_t if p_t >= 8 else (roi_t - 50.0)
        if score > best_score:
            best_score, best_res = score, (c_try, a_try, p_t, roi_t)
    best_genome, _ = run_evolution(df.tail(220).reset_index(drop=True), n_pop=40, n_gen=18)
    p_v5, _, _, roi_v5, _ = simuler_df(df, cap_init, marge_pct, dnb, "V5", darwin_genes=best_genome)
    if best_res:
        bc, ba, bp, broi = best_res
        db.setdefault("_v4_meta", {})[key] = {"C": float(bc), "alpha": round(float(ba), 2), "trained": True, "roi_bt": round(float(broi), 1), "paris_bt": int(bp), "darwin_genes": [round(float(g), 4) for g in best_genome], "darwin_roi": round(float(roi_v5), 1), "darwin_paris": int(p_v5)}

def render_backtest():
    st.subheader("📊 Backtest & Arène IA")
    db = load_db()
    custom_df = st.session_state.get("custom_df")
    has_custom = isinstance(custom_df, pd.DataFrame) and len(custom_df) >= 65
    ligue = st.selectbox("🏟️ Championnat", (["📂 Ligue Perso (CSV)"] if has_custom else []) + ["🌍 Toutes les ligues (Portefeuille EU)"] + list(CHAMPIONNATS.keys()))
    is_all, is_custom = ligue.startswith("🌍"), ligue.startswith("📂")
    zone_prog = st.empty()

    b1, b2, b3 = st.columns(3)
    run_duel = b1.button("⚔️ Duel", type="primary", use_container_width=True)
    run_train = b2.button("🧠 Entraîner", use_container_width=True)
    run_rank = b3.button("🏆 Top 10", use_container_width=True)

    with st.expander("⚙️ Paramètres (100€ • Marge 10% • DNB)", expanded=False):
        c1, c2 = st.columns(2)
        cap_init = c1.number_input("💰 Capital (€)", 10.0, 10000.0, 100.0, step=10.0)
        marge_pct = c2.slider("🛡️ Marge (%)", 0, 25, 10, step=2)
        dnb = st.toggle("🔄 DNB", value=True)

    fd_code = None if (is_all or is_custom) else CHAMPIONNATS.get(ligue)
    v4_cfg = get_v4_params(db, "CUSTOM_CSV" if is_custom else fd_code) if not is_all else {}
    if not is_all and v4_cfg.get("trained"):
        st.caption(f"🧠 **{ligue} :** 🤖 V4 `C={v4_cfg.get('C')}` (**{v4_cfg.get('roi_bt', 0):+.1f}%**) • 🦖 V5 : **{v4_cfg.get('darwin_roi', 0):+.1f}%**")

    if run_rank:
        rows = [{"Ligue": n, "🤖 V4 (%)": round(float(get_v4_params(db, c).get("roi_bt", 0)), 1), "🦖 V5 (%)": get_v4_params(db, c).get("darwin_roi"), "Leader": "🦖 V5" if (get_v4_params(db, c).get("darwin_roi") or -999) > float(get_v4_params(db, c).get("roi_bt", 0)) else "🤖 V4"} for n, c in CHAMPIONNATS.items()]
        st.dataframe(pd.DataFrame(rows).sort_values("🦖 V5 (%)", ascending=False), use_container_width=True, hide_index=True)

    if run_train:
        if is_all:
            bar = zone_prog.progress(0, text="Entraînement des 8 ligues EU...")
            for idx, nom_l in enumerate(LIGUES_EU):
                bar.progress(int((idx / len(LIGUES_EU)) * 95), text=f"🧠 {nom_l} ({idx + 1}/{len(LIGUES_EU)})...")
                codes_l = CHAMPIONNATS.get(nom_l)
                df_l, _ = fetch_odds_df(codes_l)
                if len(df_l) >= 65:
                    entrainer_ligue(db, next(iter(codes_l)), df_l, cap_init, marge_pct, dnb)
            requests.patch(f"{SUPABASE_URL}/rest/v1/smartstake_users?user_id=eq._v4_meta", headers=_sb_headers(), json={"v4_meta": db["_v4_meta"]}, timeout=10)
            bar.progress(100, text="✅ Sauvegardé !")
            st.rerun()
        else:
            bar = zone_prog.progress(20, text=f"Entraînement sur {ligue}...")
            df = custom_df.copy() if is_custom else fetch_odds_df(fd_code)
            if isinstance(df, tuple):
                df, _ = df
            if len(df) >= 65:
                entrainer_ligue(db, "CUSTOM_CSV" if is_custom else next(iter(fd_code)), df, cap_init, marge_pct, dnb)
                if not is_custom:
                    requests.patch(f"{SUPABASE_URL}/rest/v1/smartstake_users?user_id=eq._v4_meta", headers=_sb_headers(), json={"v4_meta": db["_v4_meta"]}, timeout=8)
                bar.progress(100, text="✅ Sauvegardé !")
                st.rerun()

    if run_duel:
        bar = zone_prog.progress(10, text="Simulation en cours...")
        if is_all:
            tot_p, tot_g, cap_l, hists = {"V2": 0, "V3": 0, "V4": 0, "V5": 0}, {"V2": 0.0, "V3": 0.0, "V4": 0.0, "V5": 0.0}, cap_init / len(LIGUES_EU), {"V2": [], "V3": [], "V4": [], "V5": []}
            for idx, nom_l in enumerate(LIGUES_EU):
                bar.progress(int((idx / len(LIGUES_EU)) * 90), text=f"⏳ {nom_l}...")
                codes_l = CHAMPIONNATS.get(nom_l)
                cfg_l = get_v4_params(db, codes_l)
                df_l, _ = fetch_odds_df(codes_l)
                if len(df_l) >= 65:
                    for m_n, cv, av, gv in [("V2", 0.5, 0.8, None), ("V3", 0.5, 0.8, None), ("V4", cfg_l.get("C", 0.5), cfg_l.get("alpha", 0.8), None), ("V5", 0.5, 0.8, cfg_l.get("darwin_genes"))]:
                        pm, _, cf, _, hm = simuler_df(df_l, cap_l, marge_pct, dnb, m_n, cv, av, gv, step_v4=35)
                        tot_p[m_n] += pm
                        tot_g[m_n] += (cf - cap_l)
                        hists[m_n].append(hm)
            bar.progress(100, text="✅ Terminé !")
            c2, c3 = st.columns(2)
            for col, pairs in [(c2, [("V2", "⚡ V2"), ("V4", "🤖 V4")]), (c3, [("V3", "🧬 V3"), ("V5", "🦖 V5")])]:
                for cm, tm in pairs:
                    col.metric(tm, f"{cap_init + tot_g[cm]:.2f} €", delta=f"{(tot_g[cm]/cap_init)*100:+.1f}% ({tot_p[cm]}p)")
        else:
            df = custom_df.copy() if is_custom else fetch_odds_df(fd_code)
            if isinstance(df, tuple):
                df, _ = df
            if len(df) >= 65:
                p2, _, c2, r2, h2 = simuler_df(df, cap_init, marge_pct, dnb, "V2")
                p3, _, c3, r3, h3 = simuler_df(df, cap_init, marge_pct, dnb, "V3")
                p4, _, c4, r4, h4 = simuler_df(df, cap_init, marge_pct, dnb, "V4", v4_cfg.get("C", 0.5), v4_cfg.get("alpha", 0.8))
                p5, _, c5, r5, h5 = simuler_df(df, cap_init, marge_pct, dnb, "V5", darwin_genes=v4_cfg.get("darwin_genes"))
                bar.progress(100, text="✅ Terminé !")
                col2, col3 = st.columns(2)
                col2.metric("⚡ V2", f"{c2:.2f} €", delta=f"{r2:+.1f}% ({p2}p)")
                col2.metric("🤖 V4", f"{c4:.2f} €", delta=f"{r4:+.1f}% ({p4}p)")
    
