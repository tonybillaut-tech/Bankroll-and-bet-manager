import streamlit as st
import pandas as pd
import requests
import io
import json
import os
from datetime import datetime

st.set_page_config(page_title="SmartStake V2", page_icon="🎯", layout="centered")

DB_FILE = "smartstake_users.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

db = load_db()

if "user_id" not in st.session_state:
    st.session_state.user_id = "Invite"
if "analyses_count" not in st.session_state:
    st.session_state.analyses_count = 0
if "is_pro" not in st.session_state:
    st.session_state.is_pro = False

c_t, c_b = st.columns(2)
c_t.title("🎯 SmartStake")
c_b.info("PRO ✨" if st.session_state.is_pro else f"Essai : {max(0, 3 - st.session_state.analyses_count)}/3")

st.info("⚖️ **Mentions légales :** Outil statistique d'aide à la décision (aucune garantie de gain). **18+ | Jouer comporte des risques** : **09 74 75 13 13** (appel non surtaxé).")

with st.expander("👤 Mon Espace Utilisateur (Sauvegarde Bankroll)", expanded=False):
    pseudo = st.text_input("Entre ton pseudo ou e-mail pour charger/sauvegarder ton profil :", value=st.session_state.user_id)
    if pseudo and pseudo != st.session_state.user_id:
        st.session_state.user_id = pseudo
        if pseudo not in db:
            db[pseudo] = {"capital_depart": 20.0, "paris": [], "is_pro": False}
            save_db(db)
        st.session_state.is_pro = db[pseudo].get("is_pro", False)
        st.rerun()

if st.session_state.user_id not in db:
    db[st.session_state.user_id] = {"capital_depart": 20.0, "paris": [], "is_pro": False}

user_data = db[st.session_state.user_id]

def get_current_capital(u_data):
    cap = float(u_data.get("capital_depart", 20.0))
    for p in u_data.get("paris", []):
        statut = p.get("Statut", "⏳ En cours")
        mise = float(p.get("Mise (€)", 0))
        gain_net = float(p.get("Gain Visé (€)", 0))
        if statut == "✅ Gagné":
            cap += gain_net
        elif statut == "❌ Perdu":
            cap -= mise
    return round(cap, 2)

capital_actuel = get_current_capital(user_data)

tab_scan, tab_calc, tab_suivi, tab_pro = st.tabs(["🔎 Scanner", "🧮 Calculateur", "📈 Ma Bankroll", "💎 Pro"])

CHAMPIONNATS = {
    "🇫🇷 Ligue 1 (GitHub)": "https://githubusercontent.com",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://football-data.co.uk",
    "🇪🇸 La Liga": "https://football-data.co.uk",
    "🇮🇹 Serie A": "https://football-data.co.uk",
    "🇩🇪 Bundesliga": "https://football-data.co.uk"
}

CALENDRIERS = {
    "🇫🇷 Ligue 1 (GitHub)": "https://githubusercontent.com",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://githubusercontent.com",
    "🇪🇸 La Liga": "https://githubusercontent.com",
    "🇮🇹 Serie A": "https://githubusercontent.com",
    "🇩🇪 Bundesliga": "https://githubusercontent.com"
}

@st.cache_data(ttl=600)
def get_data(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text)).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR'])
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_upcoming_matches(url_json):
    try:
        r = requests.get(url_json, timeout=10)
        data = r.json()
        prochains = []
        for m in data.get("matches", []):
            if "score" not in m or m["score"].get("ft") is None:
                prochains.append({"Date": m.get("date", ""), "Domicile": m["team1"], "Exterieur": m["team2"]})
        return prochains[:9]
    except Exception:
        return []

def calc_t3(df, eq1, eq2):
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
    return (g1v + g2d) - (hv + ad), (g1n + g2n) - (hn + an), (g1d + g2v) - (hd + av)

ligue = st.selectbox("Championnat actif", list(CHAMPIONNATS.keys()))
df = get_data(CHAMPIONNATS[ligue])

with st.expander("📂 Importer un CSV ou liens directs (Saison 2026/2027)"):
    st.markdown("""
    * [🇫🇷 Ligue 1 (F1.csv)](https://football-data.co.uk) | [🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (E0.csv)](https://football-data.co.uk) | [🇪🇸 Liga (SP1.csv)](https://football-data.co.uk)
    * [🇮🇹 Serie A (I1.csv)](https://football-data.co.uk) | [🇩🇪 Bundesliga (D1.csv)](https://football-data.co.uk) | [🌐 Tous les championnats](https://football-data.co.uk)
    """)
    up = st.file_uploader("Charger un fichier CSV :", type=["csv"])
    if up is not None:
        df = pd.read_csv(up).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR'])
        st.success(f"Fichier chargé ({len(df)} matchs) !")

with tab_scan:
    st.subheader("🔎 Scanner — Prochains matchs à venir")
    st.caption("Identifie les équipes visiteuses sous-cotées pour la prochaine journée (à croiser avec les cotes bookmaker).")
    if df.empty:
        st.warning("Charge un fichier CSV ci-dessus pour l'historique statistique.")
    else:
        if st.button("⚡ Détecter les cibles du prochain week-end", type="primary", use_container_width=True):
            a_venir = get_upcoming_matches(CALENDRIERS.get(ligue, ""))
            if not a_venir:
                st.info("Calendrier automatique indisponible pour cette ligue. Utilise l'onglet **🧮 Calculateur** pour tester tes affiches !")
            else:
                eq_csv = df['HomeTeam'].unique().tolist()
                def match_name(nom):
                    for e in eq_csv:
                        if e.lower() in nom.lower() or nom.lower()[:5] in e.lower():
                            return e
                    return None

                cibles = []
                for m in a_venir:
                    e1, e2 = match_name(m["Domicile"]), match_name(m["Exterieur"])
                    if e1 and e2:
                        t3v, t3n, t3d = calc_t3(df, e1, e2)
                        if t3d > 0:
                            ct_dnb = round(1 + (t3v / t3d), 2)
                            if ct_dnb <= 2.60:
                                cibles.append({
                                    "Date": m["Date"],
                                    "Affiche": f"{e1} vs {e2}",
                                    "Cible": f"{e2} (DNB)",
                                    "Cote Juste DNB": ct_dnb,
                                    "Cote Min. à jouer": round(max(1.90, ct_dnb + 0.05), 2)
                                })
                if cibles:
                    st.success(f"🎯 **{len(cibles)} cible(s) repérée(s) pour la prochaine journée !**")
                    st.dataframe(pd.DataFrame(cibles), hide_index=True, use_container_width=True)
                else:
                    st.info("Aucune cible visiteuse forte détectée sur la prochaine journée.")

with tab_calc:
    if df.empty:
        st.warning("Charge un fichier CSV ci-dessus.")
    else:
        eqs = sorted(df['HomeTeam'].unique().tolist())
        col1, col2 = st.columns(2)
        eq1 = col1.selectbox("🏠 Domicile", eqs, index=0)
        eq2 = col2.selectbox("✈️ Extérieur", eqs, index=1 if len(eqs) > 1 else 0)

        issue = st.radio("Issue ciblée", ["🏠 Équipe 1", "🤝 Match Nul", "✈️ Équipe 2"], index=2, horizontal=True)
        r1, r2 = st.columns(2)
        cap_input = r1.number_input("Capital actuel (€)", min_value=1.0, value=capital_actuel, step=1.0)
        risque_pct = r2.select_slider("Niveau de risque (%)", options=[2.5, 5.0, 7.5, 10.0], value=5.0)

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
                t3v, t3n, t3d = calc_t3(df, eq1, eq2)
                tot = max(1, t3v + t3n + t3d)

                if issue == "🏠 Équipe 1":
                    ct = (1 + t3d / t3v) if (dnb and t3v > 0) else (tot / t3v if t3v > 0 else 99.0)
                    cr = (c1 * (cn - 1) / cn) if dnb else c1
                    cmin, cmax = (1.90, 3.50) if dnb else (2.00, 5.00)
        
