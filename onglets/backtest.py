import streamlit as st
import pandas as pd
import requests, io, time
from database import load_db, save_db
from moteur import CHAMPIONNATS, fetch_matches, calc_v2, calc_v3_dixon_coles, calc_v4_meta, get_v4_params, save_v4_params

def fetch_odds_df(codes, saison="2526"):
    fd_code, csv_code = codes
    if csv_code not in ["CL", "BSA"]:
        for s in [saison, "2425"]:
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

def simuler_df(df, cap_init, marge_pct, dnb, algo="V3", C_val=0.5, alpha=0.80):
    cap, mise_tot, paris, gagnes = cap_init, 0.0, 0, 0
    hist = []
    has_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
    mult = 1.0 + (marge_pct / 100.0)
    start_idx = 60 if algo == "V4" else (25 if algo == "V3" else 15)

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        if algo == "V4":
            sub_i = (i // 15) * 15
            t3v, t3n, t3d, _, _ = calc_v4_meta(df.iloc[:max(60, sub_i)], row["HomeTeam"], row["AwayTeam"], C_val=C_val, alpha=alpha)
        elif algo == "V3":
            sub_i = (i // 5) * 5
            t3v, t3n, t3d, _, _ = calc_v3_dixon_coles(df.iloc[:max(25, sub_i)], row["HomeTeam"], row["AwayTeam"])
        else:
            t3v, t3n, t3d, _, _ = calc_v2(df.iloc[:i], row["HomeTeam"], row["AwayTeam"])

        tot = max(1.0, t3v + t3n + t3d)
        c1_o = float(row["B365H"]) if has_odds else 2.25
        cn_o = float(row["B365D"]) if has_odds else 3.30
        c2_o = float(row["B365A"]) if has_odds else 3.10
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

    roi = round(((cap - cap_init) / max(1.0, mise_tot)) * 100, 1)
    reussite = round(gagnes * 100 / max(1, paris), 1)
    return paris, reussite, round(cap, 2), roi, hist

def optimiser_grille(df, cap_init, marge_pct, dnb, grille, prog_bar=None):
    best_score, best_res = -9999.0, None
    for idx, (c_try, a_try) in enumerate(grille):
        p_t, r_t, cap_t, roi_t, _ = simuler_df(df, cap_init, marge_pct, dnb, algo="V4", C_val=c_try, alpha=a_try)
        score = roi_t if p_t >= 8 else (roi_t - 50.0)
        if score > best_score:
            best_score = score
            best_res = (c_try, a_try, p_t, r_t, cap_t, roi_t)
        if prog_bar is not None:
            prog_bar.progress((idx + 1) / len(grille))
    return best_res

def render_backtest():
    st.subheader("📊 Backtest, Duel IA & Entraînement V4")
    db = load_db()
    ligue = st.selectbox("🏟️ Championnat détaillé", list(CHAMPIONNATS.keys()))
    fd_code = CHAMPIONNATS[ligue]
    v4_cfg = get_v4_params(db, fd_code)

    if v4_cfg.get("trained"):
        st.info(f"🧠 **V4 déjà entraînée sur {ligue} :** `C={v4_cfg['C']}` | Poids Méta-IA `{int(v4_cfg['alpha']*100)}%` | ROI Backtest : **{v4_cfg['roi_bt']:+.1f}%** ({v4_cfg['paris_bt']} paris)")

    c1, c2 = st.columns(2)
    cap_init = c1.number_input("💰 Capital départ (€)", 10.0, 10000.0, 100.0, step=10.0)
    marge_pct = c2.slider("🛡️ Marge sécurité Value (%)", 0, 25, 8, step=2)
    dnb = st.toggle("🔄 Simuler avec DNB (Remboursé si nul)", value=True)
    csv_up = st.file_uploader("📂 Importer un CSV Bet365 (optionnel)", type=["csv"])

    b1, b2 = st.columns(2)
    run_duel = b1.button("⚔️ Duel V2 vs V3 vs V4", type="primary", use_container_width=True)
    run_train = b2.button("🧠 Entraîner V4 (Cette ligue)", use_container_width=True)

    if run_train:
        with st.spinner(f"Optimisation et entraînement de V4 sur {ligue}..."):
            if csv_up:
                df = pd.read_csv(csv_up).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR']).reset_index(drop=True)
            else:
                df, _ = fetch_odds_df(CHAMPIONNATS[ligue])

            if len(df) < 65:
                st.warning("Pas assez de matchs terminés pour entraîner V4 (65 minimum requis).")
            else:
                grille_complete = [
                    (0.2, 0.50), (0.2, 0.75), (0.2, 0.90),
                    (0.5, 0.50), (0.5, 0.75), (0.5, 0.90),
                    (1.0, 0.50), (1.0, 0.75), (1.0, 0.90),
                    (2.0, 0.60), (2.0, 0.80), (2.0, 0.95)
                ]
                best_res = optimiser_grille(df, cap_init, marge_pct, dnb, grille_complete, st.progress(0))
                if best_res:
                    bc, ba, bp, br, bcap, broi = best_res
                    save_v4_params(db, fd_code, bc, ba, broi, bp)
                    st.success(f"🎉 **V4 entraînée et sauvegardée pour {ligue} !**\n\nParamètres : `C={bc}` • Méta-IA `{int(ba*100)}%` / Dixon-Coles `{int((1-ba)*100)}%` → **{bp} paris**, Réussite **{br}%**, ROI **{broi:+.1f}%** ({bcap:.2f} €)")

    if run_duel:
        with st.spinner("Simulation du Duel V2 vs V3 vs V4 en cours..."):
            if csv_up:
                df = pd.read_csv(csv_up).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR']).reset_index(drop=True)
                real_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
            else:
                df, real_odds = fetch_odds_df(CHAMPIONNATS[ligue])

            if len(df) < 65:
                st.warning("Pas assez de matchs terminés pour entraîner la V4 (65 minimum requis).")
            else:
                if real_odds:
                    st.caption("✅ Simulation basée sur les **vraies cotes historiques Bet365**.")
                else:
                    st.warning("⚠️ Cotes réelles indisponibles : simulation sur cotes moyennes.")

                p2, r2, cap2, roi2, hist2 = simuler_df(df, cap_init, marge_pct, dnb, algo="V2")
                p3, r3, cap3, roi3, hist3 = simuler_df(df, cap_init, marge_pct, dnb, algo="V3")
                p4, r4, cap4, roi4, hist4 = simuler_df(df, cap_init, marge_pct, dnb, algo="V4", C_val=v4_cfg["C"], alpha=v4_cfg["alpha"])

                col2, col3, col4 = st.columns(3)
                with col2:
                    st.markdown("#### ⚡ V2")
                    st.metric("Finale", f"{cap2:.2f} €", delta=f"{roi2:+.1f}%")
                    st.caption(f"{p2} paris • {r2}%")
                with col3:
                    st.markdown("#### 🧬 V3")
                    st.metric("Finale", f"{cap3:.2f} €", delta=f"{roi3:+.1f}%")
                    st.caption(f"{p3} paris • {r3}%")
                with col4:
                    st.markdown("#### 🤖 V4 IA")
                    st.metric("Finale", f"{cap4:.2f} €", delta=f"{roi4:+.1f}%")
                    st.caption(f"{p4} paris • {r4}%")

                min_len = min(len(hist2), len(hist3), len(hist4))
                chart_df = pd.DataFrame({
                    "⚡ V2": hist2[-min_len:],
                    "🧬 V3 Dixon-Coles": hist3[-min_len:],
                    "🤖 V4 Méta-IA": hist4[-min_len:]
                })
                st.line_chart(chart_df)

    st.divider()
    g1, g2 = st.columns(2)
    run_all_train = g1.button("🚀 Entraîner V4 sur les 10 ligues", use_container_width=True)
    run_all_rank = g2.button("🏆 Classer les 10 championnats", use_container_width=True)

    if run_all_train:
        grille_rapide = [(0.2, 0.70), (0.5, 0.50), (0.5, 0.80), (1.0, 0.70), (1.0, 0.90), (2.0, 0.85)]
        rows, bar, items = [], st.progress(0), list(CHAMPIONNATS.items())
        status_txt = st.empty()
        if "_v4_meta" not in db or not isinstance(db["_v4_meta"], dict):
            db["_v4_meta"] = {"capital_depart": 0.0, "paris": [], "is_pro": False, "essai": 0, "pin_hash": ""}

        for idx, (nom, codes) in enumerate(items):
            status_txt.caption(f"⏳ Entraînement en cours : **{nom}** ({idx + 1}/{len(items)})...")
            df_l, real_odds = fetch_odds_df(codes)
            if len(df_l) >= 65:
                best_res = optimiser_grille(df_l, cap_init, marge_pct, dnb, grille_rapide)
                if best_res:
                    bc, ba, bp, br, bcap, broi = best_res
                    db["_v4_meta"][codes] = {
                        "C": float(bc),
                        "alpha": round(float(ba), 2),
                        "trained": True,
                        "roi_bt": round(float(broi), 1),
                        "paris_bt": int(bp)
                    }
                    rows.append({
                        "Ligue": nom,
                        "C": bc,
                        "Méta-IA": f"{int(ba*100)}%",
                        "Paris": bp,
                        "Réussite (%)": br,
                        "ROI (%)": broi
                    })
            bar.progress((idx + 1) / len(items))
            if not real_odds and idx < len(items) - 1:
                time.sleep(6.1)

        save_db(db)
        status_txt.empty()
        
