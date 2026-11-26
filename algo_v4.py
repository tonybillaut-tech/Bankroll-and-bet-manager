import numpy as np
import streamlit as st
from sklearn.linear_model import LogisticRegression
from algo_v2 import calc_v2
from algo_v3 import calc_v3_dixon_coles

@st.cache_data(ttl=3600, show_spinner=False)
def train_meta_model(df_hash, df_sub, C_val=0.5):
    X, y = [], []
    label_map = {"H": 0, "D": 1, "A": 2}
    start = max(25, len(df_sub) - 180)
    for i in range(start, len(df_sub)):
        row = df_sub.iloc[i]
        ftr = row["FTR"]
        if ftr not in label_map:
            continue
        v2_1, v2_n, v2_2, _, _ = calc_v2(df_sub.iloc[:i], row["HomeTeam"], row["AwayTeam"])
        tot2 = max(1.0, v2_1 + v2_n + v2_2)
        p2 = np.array([v2_1 / tot2, v2_n / tot2, v2_2 / tot2])

        sub_i = (i // 10) * 10
        v3_1, v3_n, v3_2, l1_3, l2_3 = calc_v3_dixon_coles(df_sub.iloc[:max(25, sub_i)], row["HomeTeam"], row["AwayTeam"])
        p3 = np.array([v3_1 / 100.0, v3_n / 100.0, v3_2 / 100.0])

        X.append(np.concatenate([p2, p3, p3 - p2, [l1_3 - l2_3]]))
        y.append(label_map[ftr])

    if len(set(y)) < 3 or len(X) < 30:
        return None
    clf = LogisticRegression(C=float(C_val), max_iter=300)
    clf.fit(np.array(X), np.array(y))
    return clf

def calc_v4_meta(df, eq1, eq2, C_val=0.5, alpha=0.80):
    sub = df.dropna(subset=['HomeTeam', 'AwayTeam', 'FTR', 'FTHG', 'FTAG']).tail(250).reset_index(drop=True)
    v2_1, v2_n, v2_2, l1_2, l2_2 = calc_v2(sub, eq1, eq2)
    v3_1, v3_n, v3_2, l1_3, l2_3 = calc_v3_dixon_coles(sub, eq1, eq2)
    if len(sub) < 55:
        return v3_1, v3_n, v3_2, l1_3, l2_3

    df_hash = f"meta_{C_val}_{len(sub)}_{sub.iloc[-1]['HomeTeam']}_{sub.iloc[-1]['AwayTeam']}_{sub.iloc[-1]['FTHG']}"
    clf = train_meta_model(df_hash, sub, C_val=C_val)
    if clf is None:
        return v3_1, v3_n, v3_2, l1_3, l2_3

    tot2 = max(1.0, v2_1 + v2_n + v2_2)
    p2 = np.array([v2_1 / tot2, v2_n / tot2, v2_2 / tot2])
    p3 = np.array([v3_1 / 100.0, v3_n / 100.0, v3_2 / 100.0])
    feat = np.concatenate([p2, p3, p3 - p2, [l1_3 - l2_3]]).reshape(1, -1)

    probs = clf.predict_proba(feat).flatten()
    blend = np.maximum(1.0, (float(alpha) * probs + (1.0 - float(alpha)) * p3) * 100.0)
    p_v, p_n, p_d = blend.tolist()
    return p_v, p_n, p_d, (0.75 * l1_3 + 0.25 * l1_2), (0.75 * l2_3 + 0.25 * l2_2)
      
