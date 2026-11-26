import streamlit as st
import math
from datetime import datetime
from database import load_db, save_db
from moteur import CHAMPIONNATS, fetch_matches, get_cap, calc_v2, calc_v3_dixon_coles, calc_v4_meta, calc_v5_darwin, get_v4_params

def render_analyse(*args):
    db, user, cap, is_pro = None, "", None, False
    for a in args:
        if isinstance(a, bool):
            is_pro = a
        elif isinstance(a, dict) and "_v4_meta" in a:
            db = a
        elif isinstance(a, str):
            user = a
        elif isinstance(a, (int, float)):
            cap = float(a)
    if db is None:
        db = load_db()
    u = db.get(user, {}) if isinstance(db, dict) else {}
    if cap is None:
        cap = get_cap(u)
    is_pro = bool(u.get("is_pro", is_pro))
    essai = int(u.get("essai", 0))

    st.subheader("⚽ Analyse Prédictive & Value Bets")
    ligue = st.selectbox("🏟️ Compétition (Temps Réel)", list(CHAMPIONNATS.keys()))
    fd_code = CHAMPIONNATS.get(ligue)
    v4_cfg = get_v4_params(db, fd_code)
    d_genes = v4_cfg.get("darwin_genes")

    with st.spinner("Connexion officielle aux résultats du championnat..."):
        df, err = fetch_matches(fd_code)

    if df.empty:
        st.error(f"⚠️ Flux temporairement indisponible ({err}). Réessaie dans 1 minute.")
        return

    badge_v4 = f" • 🧠 V4 (`C={v4_cfg.get('C')}`, ROI `{v4_cfg.get('roi_bt', 0):+.1f}%`)" if v4_cfg.get("trained") else ""
    badge_v5 = " • 🦖 Darwin Cloud actif" if d_genes else ""
    st.caption(f"✅ Flux officiel actif : **{len(df)} matchs terminés**{badge_v4}{badge_v5}")

    equipes = sorted(list(set(df["HomeTeam"]).union(set(df["AwayTeam"]))))
    c1, c2 = st.columns(2)
    eq1 = c1.selectbox("🏠 Domicile", equipes, index=0)
    eq2 = c2.selectbox("✈️ Extérieur", equipes, index=min(1, len(equipes) - 1))

    if eq1 == eq2:
        st.warning("Sélectionne deux équipes différentes.")
        return

    algo = st.radio(
        "🧠 Moteur d'analyse",
        ["🦖 V5 Darwin (Évolution IA)", "🤖 V4 Méta-IA (Super-Cerveau)", "🧬 V3 Dixon-Coles", "⚡ V2 Classique"],
        horizontal=True
    )

    st.markdown("#### 💶 Cotes Bookmaker à l'instant T")
    k1, kn, k2 = st.columns(3)
    c1_b = k1.number_input("Cote 1 (Dom)", 1.01, 50.0, 2.10, step=0.05)
    cn_b = kn.number_input("Cote N (Nul)", 1.01, 50.0, 3.30, step=0.05)
    c2_b = k2.number_input("Cote 2 (Ext)", 1.01, 50.0, 3.40, step=0.05)

    dnb_mode = st.toggle("🔄 Option Sécurité : Remboursé si Nul (DNB)", value=True)
    risque_pct = st.slider("🛡️ Risque maximum par pari (% du capital)", 1.0, 10.0, 5.0, step=0.5)

    if st.button("🚀 Lancer l'analyse & détecter les Value Bets", type="primary", use_container_width=True):
        if not is_pro and essai >= 3:
            st.error("🔒 **Tes 3 analyses gratuites sont épuisées.** Passe en mode **VIP Pro** dans l'onglet **💎 Abonnement** pour continuer en illimité !")
            return

        if not is_pro:
            u["essai"] = essai + 1
            db[user] = u
            save_db(db)

        if "V5" in algo:
            t1, tn, t2, l1, l2 = calc_v5_darwin(df, eq1, eq2, cloud_genome=d_genes)
        elif "V4" in algo:
            t1, tn, t2, l1, l2 = calc_v4_meta(df, eq1, eq2, C_val=v4_cfg.get("C", 0.5), alpha=v4_cfg.get("alpha", 0.80))
        elif "V3" in algo:
            t1, tn, t2, l1, l2 = calc_v3_dixon_coles(df, eq1, eq2)
        else:
            t1, tn, t2, l1, l2 = calc_v2(df, eq1, eq2)

        m1, mn, m2 = st.columns(3)
        m1.metric(f"🏠 {eq1}", f"{t1:.1f}%", f"Cote juste : {100/max(1.0, t1):.2f}")
        mn.metric("🤝 Match Nul", f"{tn:.1f}%", f"Cote juste : {100/max(1.0, tn):.2f}")
        m2.metric(f"✈️ {eq2}", f"{t2:.1f}%", f"Cote juste : {100/max(1.0, t2):.2f}")

        st.divider()
        tot = max(1.0, t1 + tn + t2)
        if dnb_mode:
            cands = [
                (f"1 DNB ({eq1})", 1.0 + (t2 / max(1.0, t1)), c1_b * (cn_b - 1.0) / cn_b),
                (f"2 DNB ({eq2})", 1.0 + (t1 / max(1.0, t2)), c2_b * (cn_b - 1.0) / cn_b)
            ]
        else:
            cands = [
                (f"Victoire {eq1} (1)", tot / max(1.0, t1), c1_b),
                (f"Match Nul (N)", tot / max(1.0, tn), cn_b),
                (f"Victoire {eq2} (2)", tot / max(1.0, t2), c2_b)
            ]

        found = False
        for label, c_theo, c_reelle in cands:
            edge = ((c_reelle / c_theo) - 1.0) * 100.0
            if edge >= 8.0 and c_reelle >= 1.50:
                found = True
                mise_opt = round(min(cap, ((cap * (risque_pct / 100.0)) * (c_reelle / 2.0)) / max(0.1, c_reelle - 1.0)), 2)
                st.success(f"💎 **VALUE BET DÉTECTÉ : {label}**\n\n• Cote réelle : **{c_reelle:.2f}** (vs cote juste **{c_theo:.2f}**) → Avantage mathématique : **+{edge:.1f}%**\n• Mise conseillée ({risque_pct}% risque) : **{mise_opt:.2f} €**")
                if st.button(f"📥 Enregistrer ce pari ({mise_opt:.2f} € sur {label})", key=f"save_{label}"):
                    u.setdefault("paris", []).append({
                        "Date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Match": f"{eq1} vs {eq2}",
                        "Pronostic": label,
                        "Cote": round(c_reelle, 2),
                        "Mise (€)": mise_opt,
                        "Statut": "⏳ En cours"
                    })
                    db[user] = u
                    save_db(db)
                    st.toast("✅ Pari ajouté à ta bankroll !")

        if not found:
            st.warning("🛡️ **Aucun Value Bet détecté sur ces cotes.** La discipline consiste à passer son tour !")

        grille_sc = []
        for g1 in range(5):
            for g2 in range(5):
                p1 = (math.exp(-l1) * (l1 ** g1)) / math.factorial(g1)
                p2 = (math.exp(-l2) * (l2 ** g2)) / math.factorial(g2)
                grille_sc.append((p1 * p2 * 100.0, f"{g1}-{g2}"))
        grille_sc.sort(reverse=True)
        top_prob, top_sc = next(iter(grille_sc))

        with st.expander(f"🎯 Score Exact estimé : {top_sc} ({top_prob:.1f}%) • Buts attendus : {l1:.2f} - {l2:.2f}", expanded=True):
            for idx, (prob, sc) in enumerate(grille_sc):
                if idx >= 3:
                    break
                mise_sc = round(min(cap * 0.025, (cap * (risque_pct / 100.0)) * 0.4), 2)
                st.write(f"• **{sc}** : **{prob:.1f}%** *(Mise max plafonnée à 2,5 % : {mise_sc:.2f} €)*")
        
