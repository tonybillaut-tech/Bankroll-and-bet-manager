import streamlit as st
import pandas as pd
import requests, io, time
from database import load_db
from moteur import CHAMPIONNATS, fetch_matches, calc_v2, calc_v3_dixon_coles, calc_v4_meta, calc_v5_darwin, get_v4_params, save_v4_params

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

def simuler_df(df, cap_init, marge_pct, dnb, algo="V3", C_val=0.5, alpha=0.80, darwin_genes=None):
    cap, mise_tot, paris, gagnes, hist = cap_init, 0.0, 0, 0, []
    has_odds = {'B365H', 'B365D', 'B365A'}.issubset(df.columns)
    mult = 1.0 + (marge_pct / 100.0)
    start_idx = 60 if algo in ("V4", "V5") else (25 if algo == "V3" else 15)

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        if algo == "V5":
            t3v, t3n, t3d, _, _ = calc_v5_darwin(df.iloc[:max(60, (i // 45) * 45)], row["HomeTeam"], row["AwayTeam"], cloud_genome=darwin_genes)
        elif algo == "V4":
            t3v, t3n, t3d, _, _ = calc_v4_meta(df.iloc[:max(60, (i // 20) * 20)], row["HomeTeam"], row["AwayTeam"], C_val=C_val, alpha=alpha)
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
    ligue = st.selectbox("🏟️ Championnat détaillé", list(CHAMPIONNATS.keys()))
    fd_code = CHAMPIONNATS.get(ligue)
    v4_cfg = get_v4_params(db, fd_code)
    d_genes = v4_cfg.get("darwin_genes")

    if v4_cfg.get("trained"):
        d_txt = " • 🦖 Darwin Cloud actif" if d_genes else ""
        st.info(f"🧠 **IA entraînée sur {ligue} :** V4 `C={v4_cfg.get('C')}` ({int(v4_cfg.get('alpha', 0.8)*100)}% IA, ROI **{v4_cfg.get('roi_bt', 0):+.1f}%**){d_txt}")

    c1, c2 = st.columns(2)
    cap_init = c1.number_input("💰 Capital départ (€)", 10.0, 10000.0, 100.0, step=10.0)
    marge_pct = c2.slider("🛡️ Marge Value (%)", 0, 25, 10, step=2)
    dnb = st.toggle("🔄 Simuler avec DNB (Remboursé si nul)", value=True)
    csv_up = st.file_uploader("📂 Importer un CSV Bet365 (optionnel)", type=["csv"])

    if st.button("⚔️ Lancer le Duel V2 vs V3 vs V4 vs V5 Darwin", type="primary", use_container_width=True):
        bar = st.progress(0, text="Chargement des données...")
        df = pd.read_csv(csv_up).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR']).reset_index(drop=True) if csv_up else fetch_odds_df(fd_code)
        if len(df) >= 65:
            bar.progress(20, text="⚡ Simulation V2...")
            p2, r2, cap2, roi2, h2 = simuler_df(df, cap_init, marge_pct, dnb, "V2")
            bar.progress(45, text="🧬 Simulation V3 Dixon-Coles...")
            p3, r3, cap3, roi3, h3 = simuler_df(df, cap_init, marge_pct, dnb, "V3")
            bar.progress(70, text="🤖 Simulation V4 Méta-IA...")
            p4, r4, cap4, roi4, h4 = simuler_df(df, cap_init, marge_pct, dnb, "V4", v4_cfg.get("C", 0.5), v4_cfg.get("alpha", 0.8))
            bar.progress(90, text="🦖 Évolution V5 Darwin...")
            p5, r5, cap5, roi5, h5 = simuler_df(df, cap_init, marge_pct, dnb, "V5", darwin_genes=d_genes)
            bar.progress(100, text="✅ Duel terminé !")

            col2, col3 = st.columns(2)
            with col2:
                st.metric("⚡ V2", f"{cap2:.2f} €", delta=f"{roi2:+.1f}% ({p2}p)")
                st.metric("🤖 V4 Méta-IA", f"{cap4:.2f} €", delta=f"{roi4:+.1f}% ({p4}p)")
            with col3:
                st.metric("🧬 V3 Dixon-Coles", f"{cap3:.2f} €", delta=f"{roi3:+.1f}% ({p3}p)")
                st.metric("🦖 V5 Darwin", f"{cap5:.2f} €", delta=f"{roi5:+.1f}% ({p5}p)")

            m = min(len(h2), len(h3), len(h4), len(h5))
            st.line_chart(pd.DataFrame({"⚡ V2": h2[-m:], "🧬 V3": h3[-m:], "🤖 V4": h4[-m:], "🦖 V5 Darwin": h5[-m:]}))

    st.divider()
    if st.button("🏆 Classement V4 & V5 Cloud (Instantané)", use_container_width=True):
        rows = [{"Ligue": n, "V4": "🧠 OK" if get_v4_params(db, c).get("trained") else "Std", "V5": "🦖 OK" if get_v4_params(db, c).get("darwin_genes") else "Auto", "ROI V4 (%)": get_v4_params(db, c).get("roi_bt", 0.0)} for n, c in CHAMPIONNATS.items()]
        st.dataframe(pd.DataFrame(rows).sort_values("ROI V4 (%)", ascending=False), use_container_width=True, hide_index=True)
            
