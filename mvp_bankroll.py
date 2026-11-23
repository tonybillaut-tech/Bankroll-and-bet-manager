import streamlit as st
import pandas as pd
import requests, io, json, os
from datetime import datetime

st.set_page_config(page_title="SmartStake", page_icon="🎯", layout="centered")
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

db = load_db()
for k, v in [("user_id", "Invite"), ("analyses_count", 0), ("is_pro", False)]:
    if k not in st.session_state: st.session_state[k] = v

c_t, c_b = st.columns(2)
c_t.title("🎯 SmartStake")
c_b.info("PRO ✨" if st.session_state.is_pro else f"Essai : {max(0, 3 - st.session_state.analyses_count)}/3")
st.info("⚖️ **Mentions légales :** Outil statistique d'aide à la décision (aucune garantie de gain). **18+ | Jouer comporte des risques** : **09 74 75 13 13** (appel non surtaxé).")

with st.expander("👤 Mon Espace Utilisateur (Sauvegarde Bankroll)", expanded=False):
    pseudo = st.text_input("Pseudo ou e-mail :", value=st.session_state.user_id)
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

def get_cap(u):
    cap = float(u.get("capital_depart", 20.0))
    for p in u.get("paris", []):
        if p.get("Statut") == "✅ Gagné": cap += float(p.get("Gain Visé (€)", 0))
        elif p.get("Statut") == "❌ Perdu": cap -= float(p.get("Mise (€)", 0))
    return round(cap, 2)

capital_actuel = get_cap(user_data)
tab_calc, tab_suivi, tab_tuto, tab_pro = st.tabs(["🧮 Calculateur", "📈 Bankroll", "📘 Tutoriel", "💎 Pro"])

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
    except Exception: return pd.DataFrame()

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
    g1v, g1n, g1d = sg(eq1); g2v, g2n, g2d = sg(eq2)
    hv, hn, hd = sl(eq1, True); av, an, ad = sl(eq2, False)
    return (g1v + g2d) - (hv + ad), (g1n + g2n) - (hn + an), (g1d + g2v) - (hd + av)

with tab_calc:
    ligue = st.selectbox("Championnat actif", list(CHAMPIONNATS.keys()))
    df = get_data(CHAMPIONNATS[ligue])
    with st.expander("📂 Importer un CSV ou liens directs (Saison 2026/2027)"):
        st.markdown("[🇫🇷 Ligue 1](https://football-data.co.uk) | [🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League](https://football-data.co.uk) | [🇪🇸 Liga](https://football-data.co.uk) | [🇮🇹 Serie A](https://football-data.co.uk) | [🇩🇪 Bundesliga](https://football-data.co.uk)")
        up = st.file_uploader("Charger un fichier CSV :", type=["csv"])
        if up is not None:
            df = pd.read_csv(up).dropna(subset=['HomeTeam', 'AwayTeam', 'FTR'])
            st.success(f"Fichier chargé ({len(df)} matchs) !")

    if df.empty:
        st.warning("⚠️ Aucun fichier chargé. Télécharge un CSV via les liens ci-dessus et importe-le !")
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
            elif eq1 == eq2: st.warning("Choisis deux équipes différentes.")
            else:
                st.session_state.analyses_count += 1
                t3v, t3n, t3d = calc_t3(df, eq1, eq2)
                tot = max(1, t3v + t3n + t3d)
                if issue == "🏠 Équipe 1":
                    ct = (1 + t3d / t3v) if (dnb and t3v > 0) else (tot / t3v if t3v > 0 else 99.0)
                    cr = (c1 * (cn - 1) / cn) if dnb else c1
                    cmin, cmax, lbl = (1.90, 3.50, f"{eq1} (DNB)") if dnb else (2.00, 5.00, f"{eq1} (1)")
                elif issue == "🤝 Match Nul":
                    ct, cr, cmin, cmax, lbl = (tot / t3n if t3n > 0 else 99.0), cn, 2.50, 4.50, "Match Nul"
                else:
                    ct = (1 + t3v / t3d) if (dnb and t3d > 0) else (tot / t3d if t3d > 0 else 99.0)
                    cr = (c2 * (cn - 1) / cn) if dnb else c2
                    cmin, cmax, lbl = (1.90, 3.50, f"{eq2} (DNB)") if dnb else (2.00, 5.00, f"{eq2} (2)")

                ok = (cr > ct) and (cmin <= cr <= cmax)
                obj = (cap_input * (risque_pct / 100.0)) * (cr / 2.0) if ok else 0.0
                mise = obj / (cr - 1.0) if (ok and cr > 1) else 0.0
                m1, m2, m3 = st.columns(3)
                m1.metric("Cote Juste", f"{ct:.2f}"); m2.metric("Cote Retenue", f"{cr:.2f}"); m3.metric("Mise", f"{mise:.2f} €")
                if ok:
                    st.success(f"✅ **PARIER {mise:.2f} €** sur **{lbl}** (Gain net : **+{obj:.2f} €**)")
                    user_data["paris"].append({"Date": datetime.now().strftime("%d/%m %H:%M"), "Match": f"{eq1}-{eq2}", "Choix": lbl, "Cote": round(cr, 2), "Mise (€)": round(mise, 2), "Gain Visé (€)": round(obj, 2), "Statut": "⏳ En cours"})
                    db[st.session_state.user_id] = user_data; save_db(db)
                else: st.warning(f"⏸️ **PASSER** (Cote {cr:.2f} vs Juste {ct:.2f} | Zone {cmin:.2f}-{cmax:.2f})")

with tab_suivi:
    st.subheader(f"📈 Bankroll de {st.session_state.user_id}")
    b1, b2 = st.columns(2)
    nouv_dep = b1.number_input("Capital de départ (€)", min_value=1.0, value=float(user_data.get("capital_depart", 20.0)), step=5.0)
    if nouv_dep != user_data.get("capital_depart", 20.0):
        user_data["capital_depart"] = nouv_dep; db[st.session_state.user_id] = user_data; save_db(db); st.rerun()
    b2.metric("Capital Actuel Calculé", f"{capital_actuel:.2f} €", delta=f"{capital_actuel - nouv_dep:+.2f} €")
    if not user_data["paris"]: st.info("Aucun pari enregistré. Valide un signal dans le Calculateur !")
    else:
        for i, p in enumerate(user_data["paris"]):
            col_info, col_stat = st.columns(2)
            col_info.write(f"**{p['Match']}** — {p['Choix']} (@{p['Cote']}) | Mise : {p['Mise (€)']}€")
            opts = ["⏳ En cours", "✅ Gagné", "🔄 Remboursé", "❌ Perdu"]
            nouv_stat = col_stat.selectbox("Statut", opts, index=opts.index(p.get("Statut", "⏳ En cours")), key=f"stat_{i}", label_visibility="collapsed")
            if nouv_stat != p.get("Statut"):
                user_data["paris"][i]["Statut"] = nouv_stat; db[st.session_state.user_id] = user_data; save_db(db); st.rerun()
        buf = io.BytesIO()
        pd.DataFrame(user_data["paris"]).to_excel(buf, index=False)
        st.download_button("📥 Exporter ma bankroll (.xlsx)", buf.getvalue(), f"smartstake_{st.session_state.user_id}.xlsx", use_container_width=True)

with tab_tuto:
    st.subheader("📘 Mode d'emploi SmartStake")
    if os.path.exists("tuto.md"):
        with open("tuto.md", "r", encoding="utf-8") as f: st.markdown(f.read())
    else: st.info("Crée le fichier tuto.md sur GitHub pour afficher le guide complet.")

with tab_pro:
    st.subheader("💎 SmartStake Pro — 29,90 €/an")
    st.write("Analyses illimitées, réglage du risque sur-mesure, sauvegarde multi-utilisateurs et protection DNB.")
    mail = st.text_input("Ton e-mail pour activer l'accès Pro :")
    if st.button("🚀 Débloquer l'accès Pro", use_container_width=True) and "@" in mail:
        
