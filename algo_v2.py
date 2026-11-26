import pandas as pd

def calc_v2(df, eq1, eq2):
    def st_t(t):
        g = df[(df['HomeTeam'] == t) | (df['AwayTeam'] == t)].tail(6)
        v = len(g[((g['HomeTeam'] == t) & (g['FTR'] == 'H')) | ((g['AwayTeam'] == t) & (g['FTR'] == 'A'))])
        n = len(g[g['FTR'] == 'D'])
        d = len(g) - v - n
        dom, bp, bc = 0.0, [], []
        for _, r in g.iterrows():
            is_h = (r['HomeTeam'] == t)
            if {'FTHG', 'FTAG'}.issubset(g.columns) and pd.notna(r['FTHG']) and pd.notna(r['FTAG']):
                hg, ag = float(r['FTHG']), float(r['FTAG'])
                dom += (hg - ag) * (0.15 if is_h else -0.15)
                bp.append(hg if is_h else ag)
                bc.append(ag if is_h else hg)
            if {'HST', 'AST'}.issubset(g.columns) and pd.notna(r['HST']) and pd.notna(r['AST']):
                dom += (float(r['HST']) - float(r['AST'])) * (0.04 if is_h else -0.04)
        return v, n, d, dom, (sum(bp) / len(bp) if bp else 1.2), (sum(bc) / len(bc) if bc else 1.2)

    def sl(t, h=True):
        s = df[df['HomeTeam'] == t].tail(3) if h else df[df['AwayTeam'] == t].tail(3)
        v = len(s[s['FTR'] == ('H' if h else 'A')])
        n = len(s[s['FTR'] == 'D'])
        return v, n, len(s) - v - n

    g1v, g1n, g1d, dom1, bp1, bc1 = st_t(eq1)
    g2v, g2n, g2d, dom2, bp2, bc2 = st_t(eq2)
    hv, hn, hd = sl(eq1, True)
    av, an, ad = sl(eq2, False)
    l1 = max(0.3, (bp1 + bc2) / 2)
    l2 = max(0.3, (bp2 + bc1) / 2)
    return (
        max(0.1, (g1v + g2d) - (hv + ad) + (dom1 - dom2)),
        max(0.1, (g1n + g2n) - (hn + an)),
        max(0.1, (g1d + g2v) - (hd + av) + (dom2 - dom1)),
        l1,
        l2
  )
  
