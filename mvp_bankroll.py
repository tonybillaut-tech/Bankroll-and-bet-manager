# Flux calendrier des matchs à venir (OpenFootball)
CALENDRIERS = {
    "🇫🇷 Ligue 1 (GitHub)": "https://githubusercontent.com",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://githubusercontent.com",
    "🇪🇸 La Liga": "https://githubusercontent.com",
    "🇮🇹 Serie A": "https://githubusercontent.com",
    "🇩🇪 Bundesliga": "https://githubusercontent.com"
}

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
                # Correspondance souple des noms d'équipes entre OpenFootball et Football-Data
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
                    st.success(f"🎯 **{len(cibles)} cible(s) repérée(s) pour la prochaine journée !** Vérifie si leur cote DNB chez ton bookmaker dépasse la colonne **Cote Min. à jouer** :")
                    st.dataframe(pd.DataFrame(cibles), hide_index=True, use_container_width=True)
                else:
                    st.info("Aucune cible visiteuse forte détectée sur la prochaine journée.")
                    
