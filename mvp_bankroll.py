import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime

st.set_page_config(
    page_title="SmartStake — Gestion de Bankroll & Value",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stButton>button {
        border-radius: 12px;
        font-weight: 600;
        height: 3em;
    }
</style>
""", unsafe_allow_html=True)

if "analyses_count" not in st.session_state:
    st.session_state.analyses_count = 0
if "is_pro" not in st.session_state:
    st.session_state.is_pro = False
if "historique" not in st.session_state:
    st.session_state.historique = pd.DataFrame(columns=[
        "Date", "Championnat", "Match", "Choix", "Cote", "Mise (€)", "Gain Net Visé (€)", "Statut"
    ])

col_logo, col_badge = st.columns([3, 1])
with col_logo:
    st.title("🎯 SmartStake")
with col_badge:
    if st.session_state.is_pro:
        st.success("PRO ✨")
    else:
        st.info(f"Essai : {max(0, 3 - st.session_state.analyses_count)}/3")

st.caption("Calculateur automatique de mise dynamique & détection de valeur (Zéro Excel).")

tab_calc, tab_suivi, tab_pro = st.tabs(["🧮 Calculateur", "📈 Ma Bankroll", "💎 Offre Pro"])

CHAMPIONNATS = {
    "🇫🇷 Ligue 1": "https://football-data.co.uk",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://football-data.co.uk",
    "🇪🇸 La Liga": "https://football-data.co.uk",
    "🇮🇹 Serie A": "https://football-data.co.uk",
    "🇩🇪 Bundesliga": "https://football-data.co.uk"
}

@st.cache_data(ttl=3600)
def get_league_data(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        return df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTR'])
    except Exception:
        return pd.DataFrame()

with tab_calc:
    ligue = st.selectbox("Choisir un championnat", list(CHAMPIONNATS.keys()))
    df = get_league_data(CHAMPIONNATS[ligue])

    if df.empty:
        st.warning("Données indisponibles pour le moment pour ce championnat.")
    else:
        equipes = sorted(df['HomeTeam'].unique().tolist())
        c1, c2 = st.columns(2)
        with c1:
            eq1 = st.selectbox("🏠 Domicile", equipes, index=0)
        with c2:
            eq2 = st.selectbox("✈️ Extérieur", equipes, index=1 if len(equipes) > 1 else 0)

        st.markdown("### 1. Tes paramètres")
        p1, p2 = st.columns(2)
        with p1:
            capital = st.number_input("Capital actuel (€)", min_value=5.0, value=20.0, step=5.0)
        with p2:
            cote_eq2 = st.number_input("Cote Équipe 2 (Extérieur)", min_value=1.05, value=2.45, step=0.05)

        mode_dnb = st.toggle("🛡️ Activer la protection « Remboursé si nul » (DNB)", value=True)
        if mode_dnb:
            cote_nul = st.number_input("Cote du Match Nul (pour calcul DNB auto)", min_value=1.50, value=3.30, step=0.05)

        if st.button("🚀 Analyser le match et calculer ma mise", type="primary", use_container_width=True):
            if not st.session_state.is_pro and st.session_state.analyses_count >= 3:
                st.error("🔒 Tu as atteint la limite de 3 analyses gratuites ! Rends-toi dans l'onglet **💎 Offre Pro** pour débloquer l'accès illimité.")
            elif eq1 == eq2:
                st.warning("Sélectionne deux équipes différentes.")
            else:
                st.session_state.analyses_count += 1

                def stats_glissantes(team):
                    g = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)].tail(6)
                    v = len(g[((g['HomeTeam'] == team) & (g['FTR'] == 'H')) | ((g['AwayTeam'] == team) & (g['FTR'] == 'A'))])
                    n = len(g[g['FTR'] == 'D'])
                    d = len(g) - v - n
                    return v, n, d

                def stats_lieu(team, home=True):
                    sub = df[df['HomeTeam'] == team].tail(3) if home else df[df['AwayTeam'] == team].tail(3)
                    target = 'H' if home else 'A'
                    v = len(sub[sub['FTR'] == target])
                    n = len(sub[sub['FTR'] == 'D'])
                    d = len(sub) - v - n
                    return v, n, d

                g1_v, g1_n, g1_d = stats_glissantes(eq1)
                g2_v, g2_n, g2_d = stats_glissantes(eq2)
                h_v, h_n, h_d = stats_lieu(eq1, True)
                a_v, a_n, a_d = stats_lieu(eq2, False)

                t3_v = (g1_v + g2_d) - (h_v + a_d)
                t3_n = (g1_n + g2_n) - (h_n + a_n)
                t3_d = (g1_d + g2_v) - (h_d + a_v)

                if mode_dnb:
                    cote_theo = (1 + (t3_v / t3_d)) if t3_d > 0 else 99.0
                    cote_reelle = (cote_eq2 * (cote_nul - 1)) / cote_nul
                    cote_min, cote_max = 1.90, 3.50
                    label_pari = f"{eq2} (Remboursé si nul)"
                else:
                    somme_t3 = max(1, t3_v + t3_n + t3_d)
                    prob_2 = t3_d / somme_t3
                    cote_theo = (1 / prob_2) if prob_2 > 0 else 99.0
                    cote_reelle = cote_eq2
                    cote_min, cote_max = 2.00, 5.00
                    label_pari = f"{eq2} (Victoire sèche)"

                valide = (cote_reelle > cote_theo) and (cote_min <= cote_reelle <= cote_max)
                objectif = (capital / 20.0) * (cote_reelle / 2.0) if valide else 0.0
                mise = objectif / (cote_reelle - 1.0) if (valide and cote_reelle > 1) else 0.0

                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("Cote Juste Est.", f"{cote_theo:.2f}")
                m2.metric("Cote Retenue", f"{cote_reelle:.2f}")
                m3.metric("Mise Conseillée", f"{mise:.2f} €")

                if valide:
                    st.success(f"✅ **SIGNAL VALIDÉ :** Miser **{mise:.2f} €** sur **{label_pari}** (Gain net visé : **+{objectif:.2f} €**).")
                    new_row = pd.DataFrame([{
                        "Date": datetime.now().strftime("%d/%m %H:%M"),
                        "Championnat": ligue.split(" ", 1)[1],
                        "Match": f"{eq1} - {eq2}",
                        "Choix": label_pari,
                        "Cote": round(cote_reelle, 2),
                        "Mise (€)": round(mise, 2),
                        "Gain Net Visé (€)": round(objectif, 2),
                        "Statut": "En cours"
                    }])
                    st.session_state.historique = pd.concat([st.session_state.historique, new_row], ignore_index=True)
                else:
                    st.warning(f"⏸️ **NO BET (Passer) :** La cote ({cote_reelle:.2f}) ne présente pas assez de valeur face à l'estimation ({cote_theo:.2f}) ou sort de la zone de sécurité.")

with tab_suivi:
    st.subheader("📈 Historique de tes signaux validés")
    if st.session_state.historique.empty:
        st.info("Aucun pari validé pour le moment. Lance une analyse dans l'onglet Calculateur !")
    else:
        st.dataframe(st.session_state.historique, hide_index=True, use_container_width=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            st.session_state.historique.to_excel(writer, index=False)
        buf.seek(0)
        st.download_button(
            "📥 Exporter mon historique (.xlsx)",
            data=buf,
            file_name="smartstake_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

with tab_pro:
    st.subheader("💎 Passe à SmartStake Pro")
    st.markdown("""
    **Arrête de perdre du temps sur Excel et sécurise ta gestion de bankroll :**
    * ✅ **Analyses illimitées** sur les 5 grands championnats européens
    * ✅ **Calcul automatique des mises** (lissage du risque intégré)
    * ✅ **Alertes Value Bets** dès l'ouverture des cotes
    * ✅ **Synchronisation Cloud** de ta bankroll sur mobile
    """)
    
    st.info("🔥 **Offre de lancement : 29,90 € / an** (soit 2,49 € / mois — rentabilisé dès ton premier pari gagnant).")
    
    email_test = st.text_input("Entre ton e-mail pour recevoir ton accès illimité :")
    if st.button("🚀 Activer mon accès Pro (Test Gratuit 7 jours)", type="primary", use_container_width=True):
        if "@" in email_test:
            st.session_state.is_pro = True
            st.balloons()
            st.success("🎉 Merci ! Ton accès Pro est débloqué pour cette session de test.")
        else:
            st.warning("Veuillez entrer une adresse e-mail valide.")
                
