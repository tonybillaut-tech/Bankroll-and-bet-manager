import streamlit as st
import pandas as pd
import requests, io, time
from moteur import CHAMPIONNATS, fetch_matches, calc_v2, calc_v3_dixon_coles

def fetch_odds_df(codes, saison="2526"):
    fd_code, csv_code = codes
    if csv_code not in ["CL", "BSA"]:
        for s in [saison, "2425"]:
            url = "https://" + "www.football-data.co.uk" + f"/mmz4281/{s}/{csv_code}.csv"
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                if r.status_code == 200:
                    df = pd.read_csv(io.StringIO(r.text)).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR', 'B365H', 'B365D', 'B365A'])
                    if len(df) >= 25:
                        return df.reset_index(drop=True), True
            except Exception:
                pass
    df, _ = fetch_matches(codes)
    return df.reset_index(drop=True), False

def simuler_df(df, cap_init, marge_pct, dnb, use_v3=True):
    cap, mise_tot, paris, gagnes = cap_init, 0.0, 0, 0
    hist = []
    has_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
    mult = 1.0 + (marge_pct / 100.0)
    start_idx = 25 if use_v3 else 15

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        hist_df = df.iloc[:i]
        # Recalibrage tous les 5 matchs pour garder une vitesse fluide en backtest
        if use_v3:
            sub_i = (i // 5) * 5
            t3v, t3n, t3d, _, _ = calc_v3_dixon_coles(df.iloc[:max(25, sub_i)], row["HomeTeam"], row["AwayTeam"])
        else:
            t3v, t3n, t3d, _, _ = calc_v2(hist_df, row["HomeTeam"], row["AwayTeam"])

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

def render_backtest():
    st.subheader("📊 Backtest & Duel V2 vs V3")
    ligue = st.selectbox("🏟️ Championnat détaillé", list(CHAMPIONNATS.keys()))
    c1, c2 = st.columns(2)
    cap_init = c1.number_input("💰 Capital départ (€)", 10.0, 10000.0, 100.0, step=10.0)
    marge_pct = c2.slider("🛡️ Marge sécurité Value (%)", 0, 25, 8, step=2)
    dnb = st.toggle("🔄 Simuler avec DNB (Remboursé si nul)", value=True)
    csv_up = st.file_uploader("📂 Importer un CSV Bet365 (optionnel)", type=["csv"])

    if st.button("⚔️ Lancer le Duel V2 vs V3 (Dixon-Coles)", type="primary", use_container_width=True):
        with st.spinner("Entraînement et simulation historique en cours..."):
            if csv_up:
                df = pd.read_csv(csv_up).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR']).reset_index(drop=True)
                real_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
            else:
                df, real_odds = fetch_odds_df(CHAMPIONNATS[ligue])

            if len(df) < 30:
                st.warning("Pas assez de matchs terminés sur cette compétition (30 minimum requis).")
            else:
                if real_odds:
                    st.caption("✅ Simulation basée sur les **vraies cotes historiques Bet365**.")
                else:
                    st.warning("⚠️ Cotes réelles indisponibles : simulation sur cotes moyennes.")

                p2, r2, cap2, roi2, hist2 = simuler_df(df, cap_init, marge_pct, dnb, use_v3=False)
                p3, r3, cap3, roi3, hist3 = simuler_df(df, cap_init, marge_pct, dnb, use_v3=True)

                col_v2, col_v3 = st.columns(2)
                with col_v2:
                    st.markdown("#### ⚡ Algo V2")
                    st.metric("Bankroll Finale", f"{cap2:.2f} €", delta=f"{roi2:+.1f}% ROI")
                    st.caption(f"🎯 {p2} paris • {r2}% réussite")

                with col_v3:
                    st.markdown("#### 🧬 Algo V3 (Dixon-Coles)")
                    st.metric("Bankroll Finale", f"{cap3:.2f} €", delta=f"{roi3:+.1f}% ROI")
                    st.caption(f"🎯 {p3} paris • {r3}% réussite")

                # Alignement des deux courbes sur la même longueur pour le graphique
                min_len = min(len(hist2), len(hist3))
                chart_df = pd.DataFrame({
                    "⚡ Algo V2": hist2[-min_len:],
                    "🧬 Algo V3 (Dixon-Coles)": hist3[-min_len:]
                })
                st.line_chart(chart_df)

    if st.button("🏆 Classer les 10 championnats (Audit V3)", use_container_width=True):
        rows, bar, items = [], st.progress(0), list(CHAMPIONNATS.items())
        for idx, (nom, codes) in enumerate(items):
            df_l, real_odds = fetch_odds_df(codes)
            if len(df_l) >= 30:
                p, reuss, cap_f, roi_f, _ = simuler_df(df_l, cap_init, marge_pct, dnb, use_v3=True)
                rows.append({
                    "Ligue": nom,
                    "Source": "Bet365" if real_odds else "Estimé",
                    "Paris": p,
                    "Réussite (%)": reuss,
                    "Finale (€)": cap_f,
                    "ROI (%)": roi_f
                })
            bar.progress((idx + 1) / len(items))
            if not real_odds and idx < len(items) - 1:
                time.sleep(6.1)
        if rows:
            df_rank = pd.DataFrame(rows).sort_values("ROI (%)", ascending=False)
            st.dataframe(df_rank, use_container_width=True, hide_index=True)
        
