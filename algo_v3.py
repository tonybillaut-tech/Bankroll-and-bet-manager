import numpy as np
import math
import streamlit as st
from scipy.optimize import minimize
from algo_v2 import calc_v2

@st.cache_data(ttl=3600, show_spinner=False)
def fit_dixon_coles(df_hash, teams, home_idx, away_idx, hg, ag, weights):
    n_teams = len(teams)
    def rho_correction(x, y, l1, l2, rho):
        if x == 0 and y == 0: return max(0.01, 1.0 - (l1 * l2 * rho))
        elif x == 0 and y == 1: return max(0.01, 1.0 + (l1 * rho))
        elif x == 1 and y == 0: return max(0.01, 1.0 + (l2 * rho))
        elif x == 1 and y == 1: return max(0.01, 1.0 - rho)
        return 1.0

    def loss_func(params):
        att = params[:n_teams] - np.mean(params[:n_teams])
        defn = params[n_teams:2*n_teams]
        home_adv, rho = params[2*n_teams], params[2*n_teams + 1]
        l1 = np.exp(att[home_idx] + defn[away_idx] + home_adv)
        l2 = np.exp(att[away_idx] + defn[home_idx])
        ll = weights * (hg * np.log(l1 + 1e-9) - l1 + ag * np.log(l2 + 1e-9) - l2)
        corr = np.array([rho_correction(int(x), int(y), a, b, rho) for x, y, a, b in zip(hg, ag, l1, l2)])
        ll += weights * np.log(corr)
        return -np.sum(ll) + 0.05 * (np.sum(att**2) + np.sum(defn**2))

    init_p = np.zeros(2 * n_teams + 2)
    init_p[2 * n_teams], init_p[2 * n_teams + 1] = 0.25, -0.05
    bounds = [(-2.5, 2.5)] * (2 * n_teams) + [(-0.5, 1.0), (-0.3, 0.3)]
    res = minimize(loss_func, init_p, method="L-BFGS-B", bounds=bounds, options={"maxiter": 120})
    p = res.x
    return dict(zip(teams, p[:n_teams] - np.mean(p[:n_teams]))), dict(zip(teams, p[n_teams:2*n_teams])), float(p[2*n_teams]), float(p[2*n_teams + 1])

def calc_v3_dixon_coles(df, eq1, eq2):
    sub = df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']).tail(250).reset_index(drop=True)
    if len(sub) < 20 or eq1 not in sub['HomeTeam'].values or eq2 not in sub['AwayTeam'].values:
        return calc_v2(df, eq1, eq2)

    teams = sorted(list(set(sub['HomeTeam']).union(set(sub['AwayTeam']))))
    t_map = {t: i for i, t in enumerate(teams)}
    hg, ag = sub['FTHG'].astype(float).values, sub['FTAG'].astype(float).values
    n = len(sub)
    weights = np.exp(-0.006 * np.arange(n - 1, -1, -1))
    df_hash = f"{n}_{sub.iloc[-1]['HomeTeam']}_{sub.iloc[-1]['AwayTeam']}_{hg[-1]}_{ag[-1]}"
    att, defn, home_adv, rho = fit_dixon_coles(df_hash, teams, sub['HomeTeam'].map(t_map).values, sub['AwayTeam'].map(t_map).values, hg, ag, weights)

    l1, l2 = max(0.25, math.exp(att[eq1] + defn[eq2] + home_adv)), max(0.25, math.exp(att[eq2] + defn[eq1]))
    p_v, p_n, p_d = 0.0, 0.0, 0.0
    for x in range(8):
        px = (math.exp(-l1) * (l1 ** x)) / math.factorial(x)
        for y in range(8):
            py = (math.exp(-l2) * (l2 ** y)) / math.factorial(y)
            tau = max(0.01, 1.0 - l1 * l2 * rho) if (x == 0 and y == 0) else (max(0.01, 1.0 + l1 * rho) if (x == 0 and y == 1) else (max(0.01, 1.0 + l2 * rho) if (x == 1 and y == 0) else (max(0.01, 1.0 - rho) if (x == 1 and y == 1) else 1.0)))
            prob = px * py * tau
            if x > y: p_v += prob
            elif x == y: p_n += prob
            else: p_d += prob

    tot = max(0.001, p_v + p_n + p_d)
    return (p_v / tot) * 100.0, (p_n / tot) * 100.0, (p_d / tot) * 100.0, l1, l2
  
