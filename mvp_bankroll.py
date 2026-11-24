import streamlit as st
import pandas as pd
import requests, io, json, os
from datetime import datetime

st.set_page_config(page_title="SmartStake Football", page_icon="⚽", layout="centered")

st.markdown("""
<style>
.hero {background: linear-gradient(135deg, #064e3b 0%, #15803d 100%); padding: 18px; border-radius: 14px; color: white; margin-bottom: 12px; border: 1px solid #22c55e;}
.hero h1 {margin: 0; font-size: 1.7rem; color: #ffffff;}
.hero p {margin: 4px 0 0 0; font-size: 0.92rem; color: #dcfce7;}
.stButton>button[kind="primary"] {background-color: #16a34a; border-color: #16a34a; color: white; font-weight: 700; border-radius: 10px; height: 3em;}
</style>
""", unsafe_allow_html=True)

DB_FILE = "smartstake_users.json"
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {}
    return {}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception: pass

if "db" not in st.session_state: st.session_state.db = load_db()
db = st.session_state.db
for k, v in [("user_id", "Invite"), ("analyses_count", 0), ("is_pro", False)]:
    if k not in st.session_state: st.session_state[k] = v

badge = "PRO ✨" if st.session_state.is_pro else f"Essai gratuit : {max(0, 3 - st.session_state.analyses_count)}/3"
st.markdown(f'<div class="hero"><h1>⚽ SmartStake — Paris Sportifs Foot</h1><p>14 Championnats Auto • Algorithme V2 • Bankroll • <b>{badge}</b></p></div>', unsafe_allow_html=True)
st.caption("⚖️ Outil statistique d'aide à la décision (aucune garantie de gain). **18+ | Jouer comporte des risques** : **09 74 75 13 13**.")

with st.expander("👤 Mon Espace Parieur (Sauvegarde Bankroll)", expanded=False):
    pseudo = st.text_input("Pseudo ou e-mail :", value=st.session_state.user_id)
    if pseudo and pseudo != st.session_state.user_id:
        st.session_state.user_id = pseudo
        if pseudo not in db: db[pseudo] = {"capital_depart": 20.0, "paris": [], "is_pro": False}; save_db(db)
        st.session_state.is_pro = db[pseudo].get("is_pro", False); st.rerun()

if st.session_state.user_id not in db: db[st.session_state.user_id] = {"capital_depart": 20.0, "paris": [], "is_pro": False}
user_data = db[st.session_state.user_id]

def get_cap(u):
    cap = float(u.get("capital_depart", 20.0))
    for p in u.get("paris", []):
        if p.get("Statut") == "✅ Gagné": cap += float(p.get("Gain Visé (€)", 0))
        elif p.get("Statut") == "❌ Perdu": cap -= float(p.get("Mise (€)", 0))
    return round(cap, 2)

capital_actuel = get_cap(user_data)
tab_calc, tab_suivi, tab_tuto, tab_pro = st.tabs(["⚽ Analyse Match", "💰 Ma Bankroll", "📘 Tutoriel", "🏆 Offre Pro"])

CHAMPIONNATS = {
    "🇫🇷 Ligue 1": "F1", "🇫🇷 Ligue 2": "F2", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "E0", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship": "E1",
    "🇪🇸 La Liga": "SP1", "🇪🇸 La Liga 2": "SP2", "🇮🇹 Serie A": "I1", "🇮🇹 Serie B": "I2",
    "🇩🇪 Bundesliga": "D1", "🇩🇪 2. Bundesliga": "D2", "🇵🇹 Liga Portugal": "P1", "🇳🇱 Eredivisie": "N1",
    "🇧🇪 Pro League": "B1", "🇬🇷 Super League": "G1"
}

def read_clean_csv(source):
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            df = pd.read_csv(source, encoding=enc)
            if {'HomeTeam', 'AwayTeam', 'FTR'}.issubset(df.columns): return df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTR'])
        except Exception: continue
    return pd.DataFrame()

def get_data(code):
    for path in [f"data/{code}.csv", f"{code}.csv"]:
        if os.path.exists(path):
            df = read_clean_csv(path)
            if not df.empty: return df
    try:
        r = requests.get(f"https://football-data.co.uk{code}.csv", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200: return read_clean_csv(io.StringIO(r.text))
    except Exception: pass
    return pd.DataFrame()

def calc_v2_and_score(df, eq1, eq2):
    def stats_team(t):
        g = df[(df['HomeTeam'] == t) | (df['AwayTeam'] == t)].tail(6)
        v = len(g[((g['HomeTeam'] == t) & (g['FTR'] == 'H')) | ((g['AwayTeam'] == t) & (g['FTR'] == 'A'))])
        n = len(g[g['FTR'] == 'D']); d = len(g) - v - n; dom = 0.0; bp, bc = [], []
        for _, r in g.iterrows():
            is_h = (r['HomeTeam'] == t)
            if {'FTHG', 'FTAG'}.issubset(g.columns) and pd.notna(r['FTHG']) and pd.notna(r['FTAG']):
                hg, ag = float(r['FTHG']), float(r['FTAG'])
                dom += (hg - ag) * (0.15 if is_h else -0.15)
                bp.append(hg if is_h else ag); bc.append(ag if is_h else hg)
            if {'HST', 'AST'}.issubset(g.columns) and pd.notna(r['HST']) and pd.notna(r['AST']):
                dom += (float(r['HST']) - float(r['AST'])) * (0.04 if is_h else -0.04)
        return v, n, d, dom, (sum(bp)/len(bp) if bp else 1.2), (sum(bc)/len(bc) if bc else 1.2)

    def sl(t, h=True):
        s = df[df['HomeTeam'] == t].tail(3) if h else df[df['AwayTeam'] == t].tail(3)
        v = len(s[s['FTR'] == ('H' if h else 'A')]); n = len(s[s['FTR'] == 'D'])
        return v, n, len(s) - v - n

    g1v, g1n, g1d, dom1, bp1, bc1 = stats_team(eq1); g2v, g2n, g2d, dom2, bp2, bc2 = stats_team(eq2)
    hv, hn, hd = sl(eq1, True); av, an, ad = sl(eq2, False)
    t3_1 = max(0.1, (g1v + g2d) - (hv + ad) + (dom1 - dom2))
    t3_n = max(0.1, (g1n + g2n) - (hn + an))
    t3_2 = max(0.1, (g1d + g2v) - (hd + av) + (dom2 - dom1))
    return t3_1, t3_n, t3_2, f"{round((bp1 + bc2) / 2.0)} - {round((bp2 + bc1) / 2.0)}"

with tab_calc:
    ligue = st.selectbox("🏟️ Championnat (Données mises à jour automatiquement)", list(CHAMPIONNATS.keys()))
    df = get_data(CHAMPIONNATS[ligue])
    if df.empty: st.warning("⏳ Synchronisation des matchs en cours... Actualise dans quelques secondes.")
    else:
        st.caption(f"✅ Base à jour : **{len(df)} matchs** analysés automatiquement.")
        eqs = sorted(df['HomeTeam'].unique().tolist())
        col1, col2 = st.columns(2)
        eq1 = col1.selectbox("🏠 Équipe Domicile", eqs, index=0)
        eq2 = col2.selectbox("✈️ Équipe Extérieur", eqs, index=1 if len(eqs) > 1 else 0)
        issue = st.radio("🎯 Ton pronostic à tester", ["🏠 Équipe 1", "🤝 Match Nul", "✈️ Équipe 2"], index=2, horizontal=True)
        r1, r2 = st.columns(2)
        cap_input = r1.number_input("💰 Ta Bankroll (€)", min_value=1.0, value=capital_actuel, step=1.0)
        risque_pct = r2.select_slider("🎚️ Risque par pari (%)", options=[2.5, 5.0, 7.5, 10.0], value=5.0)
        q1, q2, q3 = st.columns(3)
        c1 = q1.number_input("Cote 1", min_value=1.05, value=2.20, step=0.05)
        cn = q2.number_input("Cote N", min_value=1.50, value=3.30, step=0.05)
        c2 = q3.number_input("Cote 2", min_value=1.05, value=3.10, step=0.05)
        dnb = st.toggle("🛡️ Option Remboursé si nul (DNB)", value=True) if issue != "🤝 Match Nul" else False

        if st.button("⚽ ANALYSER LE MATCH & CALCULER LA MISE", type="primary", use_container_width=True):
            if not st.session_state.is_pro and st.session_state.analyses_count >= 3: st.error("🔒 Limite de 3 essais atteinte ! Débloque l'onglet 🏆 Offre Pro.")
            elif eq1 == eq2: st.warning("Choisis deux équipes différentes.")
            else:
                st.session_state.analyses_count += 1
                t3v, t3n, t3d, score_est = calc_v2_and_score(df, eq1, eq2); tot = max(1.0, t3v + t3n + t3d)
                if issue == "🏠 Équipe 1":
                    ct = (1 + t3d / t3v) if dnb else (tot / t3v); cr = (c1 * (cn - 1) / cn) if dnb else c1
                    cmin, cmax, lbl = (1.90, 3.50, f"{eq1} (DNB)") if dnb else (2.00, 5.00, f"{eq1} (1)")
                elif issue == "🤝 Match Nul": ct, cr, cmin, cmax, lbl = (tot / t3n), cn, 2.50, 4.50, "Match Nul"
                else:
                    ct = (1 + t3v / t3d) if dnb else (tot / t3d); cr = (c2 * (cn - 1) / cn) if dnb else c2
                    cmin, cmax, lbl = (1.90, 3.50, f"{eq2} (DNB)") if dnb else (2.00, 5.00, f"{eq2} (2)")

                ok = (cr > ct) and (cmin <= cr <= cmax)
                obj = (cap_input * (risque_pct / 100.0)) * (cr / 2.0) if ok else 0.0
                mise = obj / (cr - 1.0) if (ok and cr > 1) else 0.0
                m1, m2, m3 = st.columns(3)
                m1.metric("Cote Juste V2", f"{ct:.2f}"); m2.metric("Cote Jouée", f"{cr:.2f}"); m3.metric("Mise Conseillée", f"{mise:.2f} €")
                st.info(f"🔮 **Pronostic Score Exact (tendance stat) :** {eq1} **{score_est}** {eq2}")
                if ok:
                    conf = "🔥 Confiance Élevée" if (cr / ct) >= 1.12 else "⚖️ Confiance Modérée"
                    st.success(f"✅ **VALUE BET ({conf}) — PARIER {mise:.2f} €** sur **{lbl}** (Gain net : **+{obj:.2f} €**)")
                    user_data["paris"].append({"Date": datetime.now().strftime("%d/%m %H:%M"), "Match": f"{eq1}-{eq2}", "Choix": lbl, "Cote": round(cr, 2), "Mise (€)": round(mise, 2), "Gain Visé (€)": round(obj, 2), "Statut": "⏳ En cours"})
                    db[st.session_state.user_id] = user_data; save_db(db)
                else: st.warning(f"⏸️ **NO BET (PASSER)** — Cote {cr:.2f} vs Cote Juste {ct:.2f}")

with tab_suivi:
    st.subheader(f"💰 Bankroll de {st.session_state.user_id}")
    b1, b2 = st.columns(2)
    nouv_dep = b1.number_input("Capital de départ (€)", min_value=1.0, value=float(user_data.get("capital_depart", 20.0)), step=5.0)
    if nouv_dep != user_data.get("capital_depart", 20.0): user_data["capital_depart"] = nouv_dep; db[st.session_state.user_id] = user_data; save_db(db); st.rerun()
    b2.metric("Bankroll Actuelle", f"{capital_actuel:.2f} €", delta=f"{capital_actuel - nouv_dep:+.2f} €")
    if not user_data["paris"]: st.info("Aucun pari validé pour l'instant.")
    else:
        for i, p in enumerate(user_data["paris"]):
            col_info, col_stat = st.columns(2)
