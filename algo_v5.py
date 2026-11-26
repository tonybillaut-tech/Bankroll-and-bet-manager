import numpy as np
import pandas as pd
import math
import streamlit as st

def extract_features_row(df_past, eq1, eq2, elo_dict):
    e1 = elo_dict.get(eq1, 1500.0)
    e2 = elo_dict.get(eq2, 1500.0)
    elo_diff = (e1 - e2) / 400.0

    g1 = df_past[(df_past['HomeTeam'] == eq1) | (df_past['AwayTeam'] == eq1)].tail(6)
    g2 = df_past[(df_past['HomeTeam'] == eq2) | (df_past['AwayTeam'] == eq2)].tail(6)

    def form_stats(g, t):
        if len(g) == 0:
            return 0.0, 1.2, 1.2
        pts, bp, bc = 0.0, [], []
        for _, r in g.iterrows():
            is_h = (r['HomeTeam'] == t)
            hg, ag = float(r.get('FTHG', 1)), float(r.get('FTAG', 1))
            gf, ga = (hg, ag) if is_h else (ag, hg)
            bp.append(gf)
            bc.append(ga)
            pts += 3.0 if gf > ga else (1.0 if gf == ga else 0.0)
        return pts / (3.0 * len(g)), float(np.mean(bp)), float(np.mean(bc))

    f1, bp1, bc1 = form_stats(g1, eq1)
    f2, bp2, bc2 = form_stats(g2, eq2)
    h_sub = df_past[df_past['HomeTeam'] == eq1].tail(4)
    a_sub = df_past[df_past['AwayTeam'] == eq2].tail(4)
    fh, _, _ = form_stats(h_sub, eq1)
    fa, _, _ = form_stats(a_sub, eq2)

    return (elo_diff, f1 - f2, fh - fa, (bp1 + bc2) / 2.0, (bp2 + bc1) / 2.0)

def predict_with_genome(genes, feat):
    w_elo, w_form, w_ha, bias_h, bias_d, temp, l_scale, draw_boost = genes
    elo_diff, form_diff, ha_diff, exp_g1, exp_g2 = feat

    score_h = w_elo * elo_diff + w_form * form_diff + w_ha * ha_diff + bias_h
    score_a = -w_elo * elo_diff - w_form * form_diff - w_ha * ha_diff
    score_d = bias_d - abs(score_h - score_a) * draw_boost

    logits = np.array([score_h, score_d, score_a], dtype=float) * max(0.3, float(temp))
    logits -= np.max(logits)
    probs = np.exp(logits)
    probs /= np.sum(probs)
    p_v, p_n, p_d = probs.tolist()

    l1 = max(0.35, exp_g1 * float(l_scale) * (1.0 + 0.15 * elo_diff))
    l2 = max(0.35, exp_g2 * float(l_scale) * (1.0 - 0.15 * elo_diff))
    return p_v * 100.0, p_n * 100.0, p_d * 100.0, l1, l2

def run_evolution(df_sub, n_pop=40, n_gen=18, seed_genome=None):
    rng = np.random.default_rng()
    pop = rng.normal(
        loc=[1.4, 0.8, 0.5, 0.25, -0.15, 1.2, 1.0, 0.4],
        scale=[0.8, 0.6, 0.4, 0.25, 0.25, 0.4, 0.2, 0.3],
        size=(n_pop, 8)
    )

    if seed_genome is not None and len(seed_genome) == 8:
        base = np.array([float(x) for x in seed_genome], dtype=float)
        half = max(2, n_pop // 2)
        seeded = [base] + [base + rng.normal(0.0, 0.10, size=8) for _ in range(half - 1)]
        pop = np.vstack([np.array(seeded), pop[half:]])

    feats, targets, odds = [], [], []
    has_odds = {'B365H', 'B365D', 'B365A'}.issubset(df_sub.columns)
    elo_running = {}
    start = max(30, len(df_sub) - 160)

    for i in range(len(df_sub)):
        r = df_sub.iloc[i]
        if i >= start and r['FTR'] in ('H', 'D', 'A'):
            feats.append(extract_features_row(df_sub.iloc[max(0, i - 40):i], r['HomeTeam'], r['AwayTeam'], elo_running))
            targets.append(r['FTR'])
            if has_odds:
                odds.append((float(r['B365H']), float(r['B365D']), float(r['B365A'])))
            else:
                odds.append((2.25, 3.30, 3.10))

        h, a = r['HomeTeam'], r['AwayTeam']
        eh, ea = elo_running.get(h, 1500.0), elo_running.get(a, 1500.0)
        exp_h = 1.0 / (1.0 + 10.0 ** ((ea - (eh + 65.0)) / 400.0))
        res_h = 1.0 if r['FTR'] == 'H' else (0.5 if r['FTR'] == 'D' else 0.0)
        elo_running[h] = eh + 24.0 * (res_h - exp_h)
        elo_running[a] = ea + 24.0 * ((1.0 - res_h) - (1.0 - exp_h))

    if len(feats) < 25:
        fallback = tuple(float(x) for x in seed_genome) if (seed_genome and len(seed_genome) == 8) else (1.4, 0.8, 0.5, 0.25, -0.15, 1.2, 1.0, 0.4)
        return fallback, elo_running

    for _ in range(n_gen):
        fitness = []
        for ind in pop:
            profit, bets, log_loss = 0.0, 0, 0.0
            for f, t, (ch, cd, ca) in zip(feats, targets, odds):
                pv, pn, pd_p, _, _ = predict_with_genome(ind, f)
                p_map = {'H': pv / 100.0, 'D': pn / 100.0, 'A': pd_p / 100.0}
                log_loss += math.log(max(0.05, p_map[t]))
                if pv > 35.0 and ch > (100.0 / pv) * 1.10 and 1.85 <= ch <= 3.50:
                    bets += 1
                    profit += (ch - 1.0) if t == 'H' else (-1.0 if t == 'A' else 0.0)
                elif pd_p > 35.0 and ca > (100.0 / pd_p) * 1.10 and 1.85 <= ca <= 3.50:
                    bets += 1
                    profit += (ca - 1.0) if t == 'A' else (-1.0 if t == 'H' else 0.0)
            roi_bonus = (profit / max(5, bets)) * 18.0 if bets >= 6 else -5.0
            fitness.append((log_loss / len(feats)) + roi_bonus)

        elite_idx = np.argsort(fitness)[-8:]
        elites = pop[elite_idx]
        next_pop = [elites[-1]]
        while len(next_pop) < n_pop:
            idx1, idx2 = rng.choice(8, size=2, replace=False).tolist()
            p1, p2 = elites[idx1], elites[idx2]
            mask = rng.random(8) < 0.5
            child = np.where(mask, p1, p2)
            if rng.random() < 0.35:
                child += rng.normal(0.0, 0.15, size=8)
            next_pop.append(child)
        pop = np.array(next_pop)

    return tuple(next(iter(pop)).tolist()), elo_running

@st.cache_data(ttl=3600, show_spinner=False)
def evolve_cached(df_hash, df_sub):
    return run_evolution(df_sub, n_pop=28, n_gen=10)

def calc_v5_darwin(df, eq1, eq2, cloud_genome=None):
    sub = df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTR']).tail(220).reset_index(drop=True)
    if len(sub) < 35:
        return 40.0, 30.0, 30.0, 1.3, 1.1

    elo_dict = {}
    for _, r in sub.iterrows():
        h, a = r['HomeTeam'], r['AwayTeam']
        eh, ea = elo_dict.get(h, 1500.0), elo_dict.get(a, 1500.0)
        exp_h = 1.0 / (1.0 + 10.0 ** ((ea - (eh + 65.0)) / 400.0))
        res_h = 1.0 if r['FTR'] == 'H' else (0.5 if r['FTR'] == 'D' else 0.0)
        elo_dict[h] = eh + 24.0 * (res_h - exp_h)
        elo_dict[a] = ea + 24.0 * ((1.0 - res_h) - (1.0 - exp_h))

    if cloud_genome and len(cloud_genome) == 8:
        alpha_genome = tuple(float(x) for x in cloud_genome)
    else:
        df_hash = f"darwin_{len(sub)}_{sub.iloc[-1]['HomeTeam']}_{sub.iloc[-1]['AwayTeam']}_{sub.iloc[-1]['FTR']}"
        alpha_genome, _ = evolve_cached(df_hash, sub)

    feat = extract_features_row(sub, eq1, eq2, elo_dict)
    return predict_with_genome(alpha_genome, feat)
    
