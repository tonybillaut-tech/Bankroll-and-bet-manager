import streamlit as st
import pandas as pd
from moteur import CHAMPIONNATS, run_financial_backtest

def render_backtest():
    st.subheader("📊 Backtest Financier (Cotes Bet365)")
    c1, c2 = st.columns(2)
    saison = c1.selectbox("📅 Saison", ["2425", "2526"], format_func=lambda x: "2024/2025 (Complète)" if x == "2425" else "2025/2026 (En cours)")
    dnb = c2.toggle("🛡️ Simuler avec DNB", value=True)
    if st.button("🚀 Lancer le Backtest (100 € / ligue)", type="primary", use_container_width=True):
        res = []
        bar = st.progress(0)
        eu = [(k, v[1]) for k, v in CHAMPIONNATS.items() if v[1] not in ("BSA", "CL")]
        for i, (nom, code) in enumerate(eu):
            r = run_financial_backtest(code, saison=saison, cap_init=100.0, risque=5.0, use_dnb=dnb)
            if r: res.append({"Compétition": nom, **r})
            bar.progress((i + 1) / len(eu))
        if res:
            df_bt = pd.DataFrame(res)
            st.dataframe(df_bt, use_container_width=True, hide_index=True)
            gain = df_bt["Finale (€)"].sum() - (100.0 * len(df_bt))
            st.success(f"💰 **{df_bt['Paris'].sum()} paris :** Profit **{gain:+.2f} €** | ROI **{df_bt['ROI (%)'].mean():+.1f}%** | Réussite **{df_bt['Réussite (%)'].mean():.1f}%**")
        else:
            st.warning("⚠️ Archives historiques bloquées par le pare-feu serveur.")
          
