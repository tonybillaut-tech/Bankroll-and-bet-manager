# ⚽ SmartStake Football — Aide à la Décision & Gestion de Bankroll

[![Streamlit App](https://streamlit.io)](https://streamlit.app)

**SmartStake** est une application web d'analyse statistique et de gestion rigoureuse de bankroll dédiée aux paris sportifs sur le football. Elle permet d'identifier les **Value Bets** sur les 10 plus grandes compétitions mondiales et de calculer la mise mathématique optimale selon le profil de risque.

---

## 🚀 Fonctionnalités Principales

* **📊 Détection de Value Bets (1N2 & DNB) :** Calcul de la cote juste théorique basée sur la forme récente, la dynamique domicile/extérieur et la domination statistique, couplé à une marge de sécurité paramétrable.
* **🎯 Modèle de Score Exact (Loi de Poisson) :** Estimation des probabilités de scores exacts et plafonnement automatique des micro-mises (≤ 2,5 % de la bankroll).
* **💰 Gestion & Suivi de Bankroll Cloud :** Espace parieur personnel avec sauvegarde persistante, mise à jour automatique des résultats des matchs terminés et export Excel (`.xlsx`).
* **📈 Backtest Historique & Audit des Ligues :** Simulation de stratégies sur les données et cotes historiques (Bet365) avec classement des championnats par ROI.

---

## 🏆 Compétitions Couvertes (Temps Réel)

🇫🇷 Ligue 1 • 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League • 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship • 🇪🇸 La Liga • 🇮🇹 Serie A • 🇩🇪 Bundesliga • 🇵🇹 Primeira Liga • 🇳🇱 Eredivisie • 🇧🇷 Brasileirão • 🇪🇺 Ligue des Champions

---

## 🛠️ Architecture du Projet

```text
├── mvp_bankroll.py       # Interface principale Streamlit (Analyse, Suivi, Espace Parieur)
├── moteur.py             # Algorithme V2, Loi de Poisson, API Football-Data & persistance GitHub
├── onglets/
│   ├── backtest.py       # Module de simulation historique et classement des ligues
│   └── infos.py          # Guide d'utilisation, mentions légales et gestion SmartStake Pro
├── requirements.txt      # Dépendances Python
└── PRIVACY.md            # Politique de confidentialité
```

---

## ⚖️ Avertissement & Jeu Responsable

*SmartStake est un outil indépendant d'aide à la décision statistique et de gestion financière. Aucune prise de pari en argent réel n'est effectuée sur la plateforme, et les analyses passées ne garantissent pas les résultats futurs.*

🔞 **Interdit aux mineurs (18+).** Jouer comporte des risques : endettement, isolement, dépendance. Pour être aidé, appelez le **09 74 75 13 13** (appel non surtaxé).
