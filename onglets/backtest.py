import streamlit as st
import pandas as pd
import requests, io
from database import load_db, SUPABASE_URL, _sb_headers
from moteur import CHAMPIONNATS, fetch_matches, calc_v2, calc_v3_dixon_coles, calc_v4_meta, calc_v5_darwin, get_v4_params
from algo_v5 import run_evolution

LIGUES_EU = (
    "🇫🇷 Ligue 1", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship",
    "🇪🇸 La Liga", "🇮🇹 Serie A", "🇩🇪 Bundesliga",
    "🇵🇹 Primeira Liga", "🇳🇱 Eredivisie"
)

def fetch_odds_df(codes, saison="2526"):
    fd_code, csv_code = codes
    if csv_code not in ("CL", "BSA"):
        for s in (saison, "2425"):
            url = "".join(["ht", "tps:", "//", "www.football-data.co.uk/mmz4281/", s, "/", csv_code, ".csv"])
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
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
        cands = [
            ("H", (1 + t3d / t3v) if dnb else tot / t3v, (c1_o * (cn_o - 1) / cn_o) if dnb else c1_o),
            ("A", (1 + t3v / t3d) if dnb else tot / t3d, (c2_o * (cn_o - 1) / cn_o) if dnb else c2_o)
        ]
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

def render_backtest():
    st.subheader("📊 Backtest, Duel IA & Évolution Darwin")
    db = load_db()

    if st.button("🏆 Classement V4 vs V5 Darwin (Instantané)", use_container_width=True):
        rows = []
        for n, c in CHAMPIONNATS.items():
            cfg = get_v4_params(db, c)
            r4 = float(cfg.get("roi_bt", 0.0))
            r5 = cfg.get("darwin_roi")
            best_r = max(r4, float(r5)) if r5 is not None else r4
            leader = "🦖 V5" if (r5 is not None and float(r5) > r4) else "🤖 V4"
            rows.append({
                "Ligue": n,
                "🤖 V4 (%)": round(r4, 1),
                "🦖 V5 (%)": round(float(r5), 1) if r5 is not None else None,
                "Leader": leader,
                "_sort": best_r
            })
        df_rank = pd.DataFrame(rows).sort_values("_sort", ascending=False).drop(columns=["_sort"])
        st.dataframe(df_rank, use_container_width=True, hide_index=True)

    st.divider()
    custom_df = st.session_state.get("custom_df")
    has_custom = isinstance(custom_df, pd.DataFrame) and len(custom_df) >= 65
    options_ligues = (["📂 Ligue Perso (CSV)"] if has_custom else []) + ["🌍 Toutes les ligues (Portefeuille EU)"] + list(CHAMPIONNATS.keys())
    ligue = st.selectbox("🏟️ Championnat détaillé", options_ligues)
    is_all = ligue.startswith("🌍")
    is_custom = ligue.startswith("📂")

    if is_all:
        st.info("🌍 **Mode Portefeuille Global :** cumule les résultats des **8 championnats européens** avec les vraies cotes Bet365 et l'ADN Darwin propre à chaque ligue.")
    elif is_custom:
        st.info(f"📂 **CSV Personnalisé actif :** `{st.session_state.get('custom_name', 'CSV')}` (**{len(custom_df)} matchs**)")
    else:
        fd_code = CHAMPIONNATS.get(ligue)
        key = next(iter(fd_code))
        v4_cfg = get_v4_params(db, fd_code)
        d_genes = v4_cfg.get("darwin_genes")
        if v4_cfg.get("trained"):
            d_roi = v4_cfg.get("darwin_roi")
            d_txt = f" • 🦖 V5 : **{d_roi:+.1f}%**" if d_roi is not None else (" • 🦖 Darwin actif" if d_genes else "")
            st.info(f"🧠 **{ligue} :** 🤖 V4 `C={v4_cfg.get('C')}` (**{v4_cfg.get('roi_bt', 0):+.1f}%**){d_txt}")

    c1, c2 = st.columns(2)
    cap_init = c1.number_input("💰 Capital départ (€)", 10.0, 10000.0, 100.0, step=10.0)
    marge_pct = c2.slider("🛡️ Marge Value (%)", 0, 25, 10, step=2)
    dnb = st.toggle("🔄 Simuler avec DNB (Remboursé si nul)", value=True)

    # Emplacement de la barre de progression bien visible juste au-dessus des boutons
    zone_prog = st.empty()

    if is_all or is_custom:
        run_duel = st.button("⚔️ Lancer le Duel V2 vs V3 vs V4 vs V5", type="primary", use_container_width=True)
        run_train = False
    else:
        b1, b2 = st.columns(2)
        run_duel = b1.button("⚔️ Duel V2 vs V3 vs V4 vs V5", type="primary", use_container_width=True)
        run_train = b2.button("🧠 Entraîner V4 & V5 (Ligue)", use_container_width=True)

    if run_train and not is_all and not is_custom:
        bar = zone_prog.progress(5, text=f"Chargement des matchs pour {ligue}...")
        df, _ = fetch_odds_df(fd_code)
        if len(df) >= 65:
            grille = [(0.2, 0.75), (0.5, 0.80), (1.0, 0.85), (2.0, 0.90)]
            best_score, best_res = -9999.0, None
            for idx_g, (c_try, a_try) in enumerate(grille):
                pct = 15 + int((idx_g / len(grille)) * 55)
                bar.progress(pct, text=f"🤖 Calibrage V4 ({idx_g + 1}/{len(grille)}) : C={c_try}...")
                p_t, _, _, roi_t, _ = simuler_df(df, cap_init, marge_pct, dnb, "V4", c_try, a_try, step_v4=45)
                score = roi_t if p_t >= 8 else (roi_t - 50.0)
                if score > best_score:
                    best_score = score
                    best_res = (c_try, a_try, p_t, roi_t)
            bar.progress(75, text="🦖 Évolution génétique V5 Darwin (35 générations)...")
            best_genome, _ = run_evolution(df.tail(220).reset_index(drop=True), n_pop=40, n_gen=18)
            p_v5, _, _, roi_v5, _ = simuler_df(df, cap_init, marge_pct, dnb, "V5", darwin_genes=best_genome)
            if best_res:
                bc, ba, bp, broi = best_res
                if "_v4_meta" not in db or not isinstance(db["_v4_meta"], dict):
                    db["_v4_meta"] = {}
                db["_v4_meta"][key] = {
                    "C": float(bc), "alpha": round(float(ba), 2), "trained": True,
                    "roi_bt": round(float(broi), 1), "paris_bt": int(bp),
                    "darwin_genes": [round(float(g), 4) for g in best_genome],
                    "darwin_roi": round(float(roi_v5), 1), "darwin_paris": int(p_v5)
                }
                requests.patch(f"{SUPABASE_URL}/rest/v1/smartstake_users?user_id=eq._v4_meta", headers=_sb_headers(), json={"v4_meta": db["_v4_meta"]}, timeout=8)
            bar.progress(100, text="✅ Entraînement terminé & sauvegardé !")
            st.rerun()

    if run_duel and is_all:
        bar = zone_prog.progress(0, text="Simulation multi-ligues en cours...")
        tot_p = {"V2": 0, "V3": 0, "V4": 0, "V5": 0}
        tot_g = {"V2": 0.0, "V3": 0.0, "V4": 0.0, "V5": 0.0}
        cap_par_ligue = cap_init / len(LIGUES_EU)
        hists = {"V2": [], "V3": [], "V4": [], "V5": []}

        for idx, nom_l in enumerate(LIGUES_EU):
            bar.progress(int((idx / len(LIGUES_EU)) * 95), text=f"⏳ Analyse {nom_l} ({idx + 1}/{len(LIGUES_EU)})...")
            codes_l = CHAMPIONNATS.get(nom_l)
            cfg_l = get_v4_params(db, codes_l)
            df_l, _ = fetch_odds_df(codes_l)
            if len(df_l) >= 65:
                for m_name, c_v, a_v, g_v in [
                    ("V2", 0.5, 0.8, None),
                    ("V3", 0.5, 0.8, None),
                    ("V4", cfg_l.get("C", 0.5), cfg_l.get("alpha", 0.8), None),
                    ("V5", 0.5, 0.8, cfg_l.get("darwin_genes"))
                ]:
                    p_m, _, cap_f, _, h_m = simuler_df(df_l, cap_par_ligue, marge_pct, dnb, m_name, c_v, a_v, g_v, step_v4=35)
                    tot_p[m_name] += p_m
                    tot_g[m_name] += (cap_f - cap_par_ligue)
                    hists[m_name].append(h_m)

        bar.progress(100, text="✅ Portefeuille EU simulé !")
        col2, col3 = st.columns(2)
        with col2:
            for code_m, titre_m in [("V2", "⚡ V2"), ("V4", "🤖 V4 Méta-IA")]:
                cf = round(cap_init + tot_g[code_m], 2)
                roi_g = round((tot_g[code_m] / max(1.0, cap_init)) * 100, 1)
