import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import math
from datetime import datetime
from database import load_db, save_db
from moteur import CHAMPIONNATS, fetch_matches, get_cap, calc_v2, calc_v3_dixon_coles, calc_v4_meta, calc_v5_darwin, get_v4_params

def _pick(titre, opts, key, idx=0):
    if key not in st.session_state or st.session_state[key] not in opts:
        st.session_state[key] = opts[min(idx, len(opts) - 1)]
    st.caption(titre)
    with st.popover(f"{st.session_state[key]} ▾", use_container_width=True):
        c = st.radio(titre, opts, index=opts.index(st.session_state[key]), key=f"r_{key}", label_visibility="collapsed")
        if c != st.session_state[key]:
            st.session_state[key] = c
            st.rerun()
    return st.session_state[key]

def render_analyse(*args):
    db = load_db()
    user, is_pro_f, cap_arg = "", False, None
    if isinstance(db, dict):
        v_users = {k.lower(): k for k in db if k != "_v4_meta"}
        for v in [st.session_state.get(k) for k in ("user_id", "user", "username", "pseudo", "login")] + list(st.session_state.values()):
            if isinstance(v, str) and v.strip().lower() in v_users:
                user = v_users[v.strip().lower()]
                break
    for a in args:
        if a is True: is_pro_f = True
        elif isinstance(a, dict) and a.get("is_pro"): is_pro_f = True
        elif isinstance(a, (int, float)) and not isinstance(a, bool): cap_arg = float(a)

    u = db.get(user, {}) if user else {}
    cap = cap_arg if cap_arg is not None else get_cap(u)
    is_pro, essai = bool(is_pro_f or u.get("is_pro", False)), int(u.get("essai", 0))

    st.subheader("⚽ Analyse Prédictive & Value Bets")
    cdf = st.session_state.get("custom_df")
    has_c = isinstance(cdf, pd.DataFrame) and len(cdf) >= 10
    ligue = _pick("🏟️ Compétition", (["📂 Ligue Perso (CSV)"] if has_c else []) + list(CHAMPIONNATS.keys()), "a_lig")

    if ligue.startswith("📂"):
        df, v4_cfg, d_genes, code_fd = cdf.copy(), {"C": 0.5, "alpha": 0.8}, None, ""
    else:
        fd = CHAMPIONNATS.get(ligue)
        code_fd = next(iter(fd)) if isinstance(fd, (tuple, list)) else str(fd)
        v4_cfg = get_v4_params(db, fd)
        d_genes = v4_cfg.get("darwin_genes")
        with st.spinner("Chargement des matchs..."):
            df, err = fetch_matches(fd)
        if df.empty:
            st.error(f"⚠️ Flux indisponible ({err}).")
            return
        st.caption(f"✅ **{len(df)} matchs**{' • 🦖 Darwin actif' if d_genes else ''}")

    eqs = sorted(set(df["HomeTeam"]).union(df["AwayTeam"]))
    c1, c2 = st.columns(2)
    with c1: eq1 = _pick("🏠 Domicile", eqs, "a_eq1", 0)
    with c2: eq2 = _pick("✈️ Extérieur", eqs, "a_eq2", 1)
    if eq1 == eq2:
        st.warning("Choisis deux équipes différentes.")
        return

    algo = st.radio("Moteur", ["🦖 V5 Darwin", "🤖 V4 Méta-IA", "🧬 V3 Dixon-Coles", "⚡ V2 Classique"], horizontal=True)
    k1, kn, k2 = st.columns(3)
    c1_b = k1.number_input("Cote 1", 1.01, 50.0, 2.10, step=0.05)
    cn_b = kn.number_input("Cote N", 1.01, 50.0, 3.30, step=0.05)
    c2_b = k2.number_input("Cote 2", 1.01, 50.0, 3.40, step=0.05)
    dnb = st.toggle("🔄 Remboursé si Nul (DNB)", False)
    r_pct = st.slider("🛡️ Risque max (%)", 1.0, 10.0, 5.0, step=0.5)

    if st.button("🚀 Lancer l'analyse & détecter les Value Bets", type="primary", use_container_width=True):
        if not is_pro and essai >= 3:
            st.error("🔒 **3 essais gratuits épuisés.** Passe en **VIP Pro** !")
            return
        if not is_pro and user:
            u["essai"] = essai + 1
            db[user] = u
            save_db(db)
        if "V5" in algo: t1, tn, t2, l1, l2 = calc_v5_darwin(df, eq1, eq2, cloud_genome=d_genes)
        elif "V4" in algo: t1, tn, t2, l1, l2 = calc_v4_meta(df, eq1, eq2, C_val=v4_cfg.get("C", 0.5), alpha=v4_cfg.get("alpha", 0.8))
        elif "V3" in algo: t1, tn, t2, l1, l2 = calc_v3_dixon_coles(df, eq1, eq2)
        else: t1, tn, t2, l1, l2 = calc_v2(df, eq1, eq2)
        st.session_state["last_ana"] = {"eq1": eq1, "eq2": eq2, "code": code_fd, "t1": t1, "tn": tn, "t2": t2, "l1": l1, "l2": l2, "c1": c1_b, "cn": cn_b, "c2": c2_b, "dnb": dnb, "r": r_pct, "sc": True}

    res = st.session_state.get("last_ana")
    if isinstance(res, dict) and res.get("eq1") == eq1 and res.get("eq2") == eq2:
        t1, tn, t2, l1, l2 = res["t1"], res["tn"], res["t2"], res["l1"], res["l2"]
        c1_b, cn_b, c2_b, dnb, r_pct = res["c1"], res["cn"], res["c2"], res["dnb"], res["r"]
        st.markdown('<div id="res-a"></div>', unsafe_allow_html=True)
        m1, mn, m2 = st.columns(3)
        m1.metric(f"🏠 {eq1}", f"{t1:.1f}%", f"Juste : {100/max(1.0, t1):.2f}")
        mn.metric("🤝 Nul", f"{tn:.1f}%", f"Juste : {100/max(1.0, tn):.2f}")
        m2.metric(f"✈️ {eq2}", f"{t2:.1f}%", f"Juste : {100/max(1.0, t2):.2f}")

        tot = max(1.0, t1 + tn + t2)
        cands = [(f"1 DNB ({eq1})", 1.0 + t2/max(1.0, t1), c1_b*(cn_b-1)/cn_b), (f"2 DNB ({eq2})", 1.0 + t1/max(1.0, t2), c2_b*(cn_b-1)/cn_b)] if dnb else [(f"Victoire {eq1} (1)", tot/max(1.0, t1), c1_b), (f"Match Nul (N)", tot/max(1.0, tn), cn_b), (f"Victoire {eq2} (2)", tot/max(1.0, t2), c2_b)]
        found = False
        for lbl, c_th, c_re in cands:
            edge = ((c_re / c_th) - 1.0) * 100.0
            if edge >= 8.0 and c_re >= 1.50:
                found = True
                mise = round(min(cap, ((cap * r_pct / 100.0) * (c_re / 2.0)) / max(0.1, c_re - 1.0)), 2)
                st.success(f"💎 **VALUE BET : {lbl}** • Cote **{c_re:.2f}** (juste **{c_th:.2f}**, **+{edge:.1f}%**) • Mise : **{mise:.2f} €**")
                if st.button(f"📥 Enregistrer ce pari ({mise:.2f} €)", key=f"sv_{eq1}_{eq2}_{lbl}"):
                    if not isinstance(u.get("paris"), list): u["paris"] = []
                    u["paris"].append({"Date": datetime.now().strftime("%d/%m/%Y %H:%M"), "Code": res.get("code", ""), "Match": f"{eq1} vs {eq2}", "Pronostic": lbl, "Cote": round(c_re, 2), "Mise (€)": mise, "Statut": "⏳ En cours"})
                    db[user] = u
                    save_db(db)
                    st.toast("✅ Pari ajouté !")
                    st.rerun()
        if not found:
            st.warning("🛡️ **Aucun Value Bet détecté sur ces cotes.**")

        gs = sorted([((math.exp(-l1)*(l1**g1)/math.factorial(g1))*(math.exp(-l2)*(l2**g2)/math.factorial(g2))*100.0, f"{g1}-{g2}") for g1 in range(5) for g2 in range(5)], reverse=True)
        top_p, top_s = next(iter(gs))
        with st.expander(f"🎯 Score Exact : {top_s} ({top_p:.1f}%) • Buts : {l1:.2f} - {l2:.2f}", expanded=True):
            for idx, (prob, sc) in enumerate(gs):
                if idx >= 3:
                    break
                st.write(f"• **{sc}** : **{prob:.1f}%** *(Mise max : {round(min(cap*0.025, cap*r_pct/250.0), 2):.2f} €)*")
        if res.get("sc"):
            res["sc"] = False
            components.html("<script>const e=window.parent.document.getElementById('res-a');if(e)e.scrollIntoView({behavior:'smooth'});</script>", height=0)
