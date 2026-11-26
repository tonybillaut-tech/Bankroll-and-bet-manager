import streamlit as st
import pandas as pd
import io

def render_donnees():
    st.subheader("📂 Données Personnalisées & Import CSV")
    st.caption("Importe tes propres championnats (Ligue 2, Belgique, Turquie...) ou saisis des matchs à la main pour les utiliser dans **Analyse** et **Backtest**.")

    csv_file = st.file_uploader("📥 Importer un fichier CSV", type=["csv"])
    if csv_file is not None:
        raw = csv_file.getvalue().decode("utf-8", errors="ignore")
        sep = ";" if raw.count(";") > raw.count(",") else ","
        try:
            df_up = pd.read_csv(io.StringIO(raw), sep=sep)
            df_up.columns = [c.strip() for c in df_up.columns]
            req = {"HomeTeam", "AwayTeam", "FTR"}
            if not req.issubset(set(df_up.columns)):
                st.error("⚠️ Colonnes manquantes. Le fichier doit contenir au minimum : `HomeTeam`, `AwayTeam`, `FTR`.")
            else:
                df_clean = df_up.dropna(subset=["HomeTeam", "AwayTeam", "FTR"]).reset_index(drop=True)
                if "FTHG" not in df_clean.columns:
                    df_clean["FTHG"] = df_clean["FTR"].map({"H": 2, "D": 1, "A": 0}).fillna(1)
                if "FTAG" not in df_clean.columns:
                    df_clean["FTAG"] = df_clean["FTR"].map({"H": 0, "D": 1, "A": 2}).fillna(1)
                st.session_state["custom_df"] = df_clean
                st.session_state["custom_name"] = csv_file.name
                st.success(f"✅ **{csv_file.name}** activé ({len(df_clean)} matchs) ! Il est maintenant disponible dans **⚽ Analyse** et **📊 Backtest**.")
        except Exception as e:
            st.error(f"Erreur de lecture du CSV : {e}")

    custom_df = st.session_state.get("custom_df")
    if isinstance(custom_df, pd.DataFrame) and not custom_df.empty:
        nom_actif = st.session_state.get("custom_name", "Ligue Perso")
        st.info(f"📌 **Fichier actif :** `{nom_actif}` (**{len(custom_df)} matchs**)")
        st.dataframe(custom_df.tail(5), use_container_width=True, hide_index=True)

        with st.expander("➕ Ajouter un résultat manuellement"):
            c1, c2 = st.columns(2)
            h_team = c1.text_input("Équipe Domicile")
            a_team = c2.text_input("Équipe Extérieur")
            g1, g2 = st.columns(2)
            hg = g1.number_input("Buts Domicile", 0, 20, 1)
            ag = g2.number_input("Buts Extérieur", 0, 20, 0)
            if st.button("Ajouter ce match au CSV actif"):
                if h_team.strip() and a_team.strip():
                    ftr = "H" if hg > ag else ("A" if ag > hg else "D")
                    new_row = pd.DataFrame([{
                        "HomeTeam": h_team.strip(), "AwayTeam": a_team.strip(),
                        "FTHG": int(hg), "FTAG": int(ag), "FTR": ftr
                    }])
                    updated = pd.concat([custom_df, new_row], ignore_index=True)
                    st.session_state["custom_df"] = updated
                    st.toast("✅ Match ajouté !")
                    st.rerun()

        col_dl, col_del = st.columns(2)
        col_dl.download_button(
            "💾 Télécharger le CSV mis à jour",
            data=custom_df.to_csv(index=False).encode("utf-8"),
            file_name=nom_actif,
            mime="text/csv",
            use_container_width=True
        )
        if col_del.button("🗑️ Retirer le CSV actif", use_container_width=True):
            st.session_state.pop("custom_df", None)
            st.session_state.pop("custom_name", None)
            st.rerun()

    st.divider()
    st.markdown("#### 📄 Besoin d'un modèle vierge ?")
    exemple = "HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A\nBordeaux,Caen,2,1,H,1.95,3.40,3.80\nMetz,Auxerre,1,1,D,2.30,3.20,3.10\n"
    st.download_button(
        "⬇️ Télécharger le modèle CSV exemple",
        data=exemple.encode("utf-8"),
        file_name="modele_smartstake.csv",
        mime="text/csv",
        use_container_width=True
          )
  
