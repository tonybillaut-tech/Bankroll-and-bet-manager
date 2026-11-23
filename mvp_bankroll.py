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

@st.cache_data(ttl=600)
def get_data(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text)).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR'])
    except Exception:
        return pd.DataFrame()

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
    st.subheader("🔎 Scanner « Spécial Extérieur DNB »")
    st.caption("Détecte automatiquement les meilleures opportunités sur les dernières affiches du fichier.")
    if df.empty:
        st.warning("Charge un fichier CSV ci-dessus pour lancer le scanner.")
    else:
        risque_scan = st.select_slider("Risque du scanner (%)", options=[2.5, 5.0, 7.5, 10.0], value=5.0, key="r_scan")
        if st.button("⚡ Scanner les opportunités", type="primary", use_container_width=True):
            if not st.session_state.is_pro and st.session_state.analyses_count >= 3:
                st.error("🔒 Limite d'essai atteinte ! Débloque l'onglet 💎 Pro.")
            else:
                st.session_state.analyses_count += 1
                derniers = df.tail(9)
                signaux = []
                col_c2 = 'AvgA' if 'AvgA' in df.columns else ('B365A' if 'B365A' in df.columns else None)
                col_cn = 'AvgD' if 'AvgD' in df.columns else ('B365D' if 'B365D' in df.columns else None)
                
                for _, row in derniers.iterrows():
                    e1, e2 = row['HomeTeam'], row['AwayTeam']
                    t3v, t3n, t3d = calc_t3(df, e1, e2)
                    if t3d > 0 and col_c2 and col_cn and pd.notna(row[col_c2]) and pd.notna(row[col_cn]):
                        ct = 1 + (t3v / t3d)
                        cr = (float(row[col_c2]) * (float(row[col_cn]) - 1)) / float(row[col_cn])
                        if cr > ct and 1.90 <= cr <= 3.50:
                            obj = (capital_actuel * (risque_scan / 100.0)) * (cr / 2.0)
                            mise = obj / (cr - 1.0)
                            signaux.append({
                                "Match": f"{e1} vs {e2}",
                                "Pari": f"{e2} (DNB)",
                                "Cote Juste": round(ct, 2),
                                "Cote DNB Est.": round(cr, 2),
                                "Mise (€)": round(mise, 2),
                                "Gain Visé (€)": round(obj, 2)
                            })
                if signaux:
                    st.success(f"🎯 **{len(signaux)} opportunité(s) détectée(s)** sur votre capital de **{capital_actuel:.2f} €** :")
                    st.dataframe(pd.DataFrame(signaux), hide_index=True, use_container_width=True)
                else:
                    st.info("Aucun signal DNB (1,90 – 3,50) détecté sur les dernières affiches de ce fichier.")

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
            
