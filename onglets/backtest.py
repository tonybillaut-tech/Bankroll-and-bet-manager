import streamlit as st
import pandas as pd
from moteur import CHAMPIONNATS, fetch_matches, calc_v2

def render_backtest():
    st.subheader("📊 Backtest & Audit de l'Algorithme V2")
    ligue = st.selectbox("🏟️ Choisir le championnat à auditer", list(CHAMPIONNATS.keys()))
    c1, c2 = st.columns(2)
    cap_init = c1.number_input("💰 Capital départ (€)", 10.0, 10000.0, 100.0, step=10.0)
    dnb = c2.toggle("🛡️ Simuler avec DNB", value=True)
    csv_up = st.file_uploader("📂 Optionnel : Importer un CSV Bet365 (ex. F1.csv)", type=["csv"])

    if st.button("🚀 Lancer la simulation sur toute la saison", type="primary", use_container_width=True):
        if csv_up:
            df = pd.read_csv(csv_up).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR']).reset_index(drop=True)
        else:
            df, _ = fetch_matches(CHAMPIONNATS[ligue])
            df = df.reset_index(drop=True)
        if len(df) < 35:
            st.warning("Pas assez de matchs terminés sur cette compétition.")
            return
        cap, mise_tot, paris, gagnes, hist_cap = cap_init, 0.0, 0, 0, [cap_init]
        has_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
        for i in range(30, len(df)):
            row = df.iloc[i]
            t3v, t3n, t3d, _, _ = calc_v2(df.iloc[:i], row["HomeTeam"], row["AwayTeam"])
            tot = max(1.0, t3v + t3n + t3d)
            c1_o = float(row["B365H"]) if has_odds else 2.25
            cn_o = float(row["B365D"]) if has_odds else 3.30
            c2_o = float(row["B365A"]) if has_odds else 3.10
            cands = [("H", (1 + t3d/t3v) if dnb else tot/t3v, (c1_o*(cn_o-1)/cn_o) if dnb else c1_o),
                     ("A", (1 + t3v/t3d) if dnb else tot/t3d, (c2_o*(cn_o-1)/cn_o) if dnb else c2_o)]
            cmin, cmax = (1.90, 3.50) if dnb else (2.00, 5.00)
            for side, ct, cr in cands:
                if cr > ct and cmin <= cr <= cmax and cap > 1.0:
                    mise = min(cap, ((cap * 0.05) * (cr / 2.0)) / (cr - 1.0))
                    paris += 1; mise_tot += mise
                    if row["FTR"] == side: cap += mise * (cr - 1.0); gagnes += 1
                    elif dnb and row["FTR"] == "D": gagnes += 1
                    else: cap -= mise
                    hist_cap.append(round(cap, 2))
                    break
        roi = round(((cap - cap_init) / max(1.0, mise_tot)) * 100, 1)
        m1, m2, m3 = st.columns(3)
        m1.metric("Paris joués", f"{paris} / {len(df)-30}")
        m2.metric("Taux réussite", f"{round(gagnes*100/max(1, paris), 1)} %")
        m3.metric("Bankroll Finale", f"{cap:.2f} €", delta=f"{roi:+.1f}% ROI")
        st.line_chart(hist_cap)
        
