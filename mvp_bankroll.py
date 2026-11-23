import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime

st.set_page_config(page_title="SmartStake", page_icon="🎯", layout="centered")

if "analyses_count" not in st.session_state:
    st.session_state.analyses_count = 0
if "is_pro" not in st.session_state:
    st.session_state.is_pro = False
if "historique" not in st.session_state:
    st.session_state.historique = pd.DataFrame(columns=["Date", "Match", "Choix", "Cote", "Mise (€)", "Gain Visé (€)"])

c_t, c_b = st.columns([3, 1])
c_t.title("🎯 SmartStake")
c_b.info("PRO ✨" if st.session_state.is_pro else f"Essai : {max(0, 3 - st.session_state.analyses_count)}/3")

tab1, tab2, tab3 = st.tabs(["🧮 Calculateur", "📈 Suivi", "💎 Pro"])

CHAMPIONNATS = {
    "🇫🇷 Ligue 1 (GitHub)": "https://githubusercontent.com",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://football-data.co.uk",
    "🇪🇸 La Liga": "https://football-data.co.uk",
    "🇮🇹 Serie A": "https://football-data.co.uk",
    "🇩🇪 Bundesliga": "https://football-data.co.uk"
}

@st.cache_data(ttl=600)
def get_data(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text)).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR'])
    except Exception:
        return pd.DataFrame()

with tab1:
    ligue = st.selectbox("Championnat", list(CHAMPIONNATS.keys()))
    df = get_data(CHAMPIONNATS[ligue])

    with st.expander("📂 Ou importer un CSV depuis le téléphone"):
        up = st.file_uploader("Fichier CSV", type=["csv"])
        if up is not None:
            df = pd.read_csv(up).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR'])

    if df.empty:
        st.warning("Charge ton fichier F1.csv sur GitHub ou via le menu ci-dessus.")
    else:
        eqs = sorted(df['HomeTeam'].unique().tolist())
        col1, col2 = st.columns(2)
        eq1 = col1.selectbox("🏠 Domicile", eqs, index=0)
        eq2 = col2.selectbox("✈️ Extérieur", eqs, index=1 if len(eqs) > 1 else 0)

        issue = st.radio("Issue ciblée", ["🏠 Équipe 1", "🤝 Match Nul", "✈️ Équipe 2"], index=2, horizontal=True)
        capital = st.number_input("Capital actuel (€)", min_value=5.0, value=20.0, step=5.0)

        q1, q2, q3 = st.columns(3)
        c1 = q1.number_input("Cote 1", min_value=1.05, value=2.20, step=0.05)
        cn = q2.number_input("Cote N", min_value=1.50, value=3.30, step=0.05)
        c2 = q3.number_input("Cote 2", min_value=1.05, value=3.10, step=0.05)

        dnb = st.toggle("🛡️ Remboursé si nul (DNB)", value=True) if issue != "🤝 Match Nul" else False

        if st.button("🚀 Analyser et calculer la mise", type="primary", use_container_width=True):
            if not st.session_state.is_pro and st.session_state.analyses_count >= 3:
                st.error("🔒 Limite de 3 essais atteinte ! Passe en Pro dans l'onglet 💎 Pro.")
            elif eq1 == eq2:
                st.warning("Choisis deux équipes différentes.")
            else:
                st.session_state.analyses_count += 1
                def sg(t):
                    g = df[(df['HomeTeam'] == t) | (df['AwayTeam'] == t)].tail(6)
                    v = len(g[((g['HomeTeam'] == t) & (g['FTR'] == 'H')) | ((g['AwayTeam'] == t) & (g['FTR'] == 'A'))])
                    n = len(g[g['FTR'] == 'D'])
                    return v, n, len(g) - v - n
                def sl(t, h=True):
                    s = df[df['HomeTeam'] == t].tail(3) if h else df[df['AwayTeam'] == t].tail(3)
                    v = len(s[s['FTR'] == ('H' if h else 'A')])
                    n = len(s[s['FTR'] == 'D'])
                    return v, n, len(s) - v - n

                g1v, g1n, g1d = sg(eq1)
                g2v, g2n, g2d = sg(eq2)
                hv, hn, hd = sl(eq1, True)
                av, an, ad = sl(eq2, False)

                t3v = (g1v + g2d) - (hv + ad)
                t3n = (g1n + g2n) - (hn + an)
                t3d = (g1d + g2v) - (hd + av)
                tot = max(1, t3v + t3n + t3d)

                if issue == "🏠 Équipe 1":
                    ct = (1 + t3d / t3v) if (dnb and t3v > 0) else (tot / t3v if t3v > 0 else 99.0)
                    cr = (c1 * (cn - 1) / cn) if dnb else c1
                    cmin, cmax = (1.90, 3.50) if dnb else (2.00, 5.00)
                    lbl = f"{eq1} ({'DNB' if dnb else '1'})"
                elif issue == "🤝 Match Nul":
                    ct = (tot / t3n) if t3n > 0 else 99.0
                    cr, cmin, cmax, lbl = cn, 2.50, 4.50, "Match Nul"
                else:
                    ct = (1 + t3v / t3d) if (dnb and t3d > 0) else (tot / t3d if t3d > 0 else 99.0)
                    cr = (c2 * (cn - 1) / cn) if dnb else c2
                    cmin, cmax = (1.90, 3.50) if dnb else (2.00, 5.00)
                    lbl = f"{eq2} ({'DNB' if dnb else '2'})"

                ok = (cr > ct) and (cmin <= cr <= cmax)
                obj = (capital / 20.0) * (cr / 2.0) if ok else 0.0
                mise = obj / (cr - 1.0) if (ok and cr > 1) else 0.0

                m1, m2, m3 = st.columns(3)
                m1.metric("Cote Juste", f"{ct:.2f}")
                m2.metric("Cote Retenue", f"{cr:.2f}")
                m3.metric("Mise", f"{mise:.2f} €")

                if ok:
                    st.success(f"✅ **PARIER {mise:.2f} €** sur **{lbl}** (Gain net : **+{obj:.2f} €**)")
                    row = pd.DataFrame([{"Date": datetime.now().strftime("%d/%m %H:%M"), "Match": f"{eq1}-{eq2}", "Choix": lbl, "Cote": round(cr, 2), "Mise (€)": round(mise, 2), "Gain Visé (€)": round(obj, 2)}])
                    st.session_state.historique = pd.concat([st.session_state.historique, row], ignore_index=True)
                else:
                    st.warning(f"⏸️ **PASSER** (Cote {cr:.2f} vs Juste {ct:.2f} | Zone {cmin:.2f}-{cmax:.2f})")

with tab2:
    if st.session_state.historique.empty:
        st.info("Aucun pari validé pour le moment.")
    else:
        st.dataframe(st.session_state.historique, hide_index=True, use_container_width=True)
        buf = io.BytesIO()
        st.session_state.historique.to_excel(buf, index=False)
        st.download_button("📥 Télécharger Excel", buf.getvalue(), "smartstake.xlsx", use_container_width=True)

with tab3:
    st.subheader("💎 SmartStake Pro — 29,90 €/an")
    st.write("Analyses illimitées, calcul automatique des mises et protection DNB.")
    mail = st.text_input("Ton e-mail pour l'essai gratuit :")
    if st.button("🚀 Débloquer l'accès Pro", use_container_width=True):
        if "@" in mail:
            st.session_state.is_pro = True
            st.success("🎉 Accès Pro activé !")
                
