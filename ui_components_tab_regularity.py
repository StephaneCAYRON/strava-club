import streamlit as st
import pandas as pd
import altair as alt
from strava_operations import *
from db_operations import *
from ui_components import common_critria


def make_display_names(df):
    """
    Génère des noms d'affichage uniques pour chaque athlète.
    Commence par le prénom seul, et ajoute progressivement des lettres du nom
    de famille jusqu'à ce que tous les noms soient uniques.
    Retourne un dict {id_strava: display_name}.
    """
    athletes = df[['id_strava', 'firstname', 'lastname']].drop_duplicates('id_strava').copy()
    athletes['lastname'] = athletes['lastname'].fillna('')
    athletes['letters'] = 0

    max_len = int(athletes['lastname'].str.len().max()) if len(athletes) > 0 else 0

    for _ in range(max_len + 2):
        def make_name(row):
            if row['letters'] == 0:
                return row['firstname']
            suffix = row['lastname'][:int(row['letters'])]
            return f"{row['firstname']} {suffix}." if suffix else row['firstname']

        athletes['display_name'] = athletes.apply(make_name, axis=1)

        dup_mask = athletes['display_name'].duplicated(keep=False)
        if not dup_mask.any():
            break

        athletes.loc[dup_mask, 'letters'] += 1

    return dict(zip(athletes['id_strava'], athletes['display_name']))


def render_tab_regularity(texts):
    """
    Onglet Challenge Régularité :
    - Calcul mensuel des KM.
    - Attribution des points dynamiques (1er = N points, où N = nb participants actifs ce mois-là).
    - Cumul annuel + Tableau croisé mois par mois.
    """
    
    st.markdown("### 📅 Challenge Régularité")
    st.caption("Le principe : s'il y a **10 participants** actifs dans le mois, le 1er au nombre de km cumulé dans le mois gagne **10 pts**, le 2ème **9 pts**... et le 10ème **1 pt**.")

    # --- 1. SÉLECTION GROUPE et ANNEE ---
    selected_g, selected_year = common_critria("regularity")

    if selected_g == "":
        st.info("Veuillez rejoindre un groupe d'abord.")
        return

    # --- 2. RÉCUPÉRATION DES DONNÉES ---
    res = get_leaderboard_by_group_by_year_cached(selected_g['group_id'], selected_year)
    
    if res.data:

        df = pd.DataFrame(res.data)

        # Conversion dates et calculs de base
        df['start_date'] = pd.to_datetime(df['start_date'])
        df['Month_Num'] = df['start_date'].dt.month
        # Astuce : On récupère le nom du mois (Janvier, Février...) selon la locale ou en anglais par défaut
        df['Month_Name'] = df['start_date'].dt.month_name()

        # Calcul des noms d'affichage uniques (prénom + initiale(s) du nom si doublon)
        display_names_map = make_display_names(df)
        df['display_name'] = df['id_strava'].map(display_names_map)

        # --- 3. ALGORITHME DE CALCUL DES POINTS ---
        all_monthly_scores = []
        
        # On boucle sur chaque mois où il y a eu de l'activité
        months_active = sorted(df['Month_Num'].unique())
        
        for m in months_active:
            # 1. Filtrer les données du mois M
            df_m = df[df['Month_Num'] == m]
            
            # On groupe par athlète pour avoir KM et Points
            rank_m = df_m.groupby(['id_strava', 'display_name', 'avatar_url'])['distance_km'].sum().reset_index()
            rank_m = rank_m.sort_values('distance_km', ascending=False).reset_index(drop=True)
            
            N = len(rank_m)
            rank_m['points_month'] = rank_m.index.map(lambda x: N - x)
            rank_m['month_num'] = m
            rank_m['month_name'] = df_m['Month_Name'].iloc[0] 
            
            # --- CRÉATION DU TEXTE D'AFFICHAGE (Pts + KM) ---
            rank_m['display_text'] = rank_m.apply(
                lambda row: f"{int(row['points_month'])} pts ({row['distance_km']:.0f} km)", axis=1
            )
            
            all_monthly_scores.append(rank_m)

        # --- 4. AGGRÉGATION ANNUELLE ---
        if all_monthly_scores:
            # On concatène tous les mois
            df_scores = pd.concat(all_monthly_scores)
            
            # On somme les points par athlète pour le classement général
            final_leaderboard = df_scores.groupby(['id_strava', 'display_name', 'avatar_url'])['points_month'].sum().reset_index()
            final_leaderboard.rename(columns={'points_month': 'total_points'}, inplace=True)
            # Tri final par points décroissants
            final_leaderboard = final_leaderboard.sort_values('total_points', ascending=False).reset_index(drop=True)

            
            # On utilise un conteneur pour styliser un peu
            for i, row in final_leaderboard.iterrows():
                # Préparation des données
                rank_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
                avatar = get_safe_avatar_url(row['avatar_url'])
                
                # On crée une ligne avec 3 colonnes de largeurs différentes
                # [Image, Nom/Stats, Distance]
                c1, c2, c3 = st.columns([1, 4, 2])
                
                with c1:
                    st.image(avatar, width=50)
                
                with c2:
                    st.markdown(f"**{rank_icon} {row['display_name']}**")
                    #if is_global_view:
                    st.caption(f"{row['total_points']} points")
                with c3:
                    # URL du profil de l'athlète
                    strava_profile_url = f"https://www.strava.com/athletes/{row['id_strava']}"
                    # Choix du logo (Version orange pour le lien)
                    # Affiche "120.5 km [Icone]" sur la même ligne
                    strava_icon = "https://www.strava.com/favicon.ico"
                    st.markdown(
                        f"**{row['total_points']}** points "
                        f'<a href="{strava_profile_url}" target="_blank">'
                        f'<img src="{strava_icon}" width="15" style="margin-left: 5px; margin-bottom: 3px;">'
                        f'</a>', 
                        unsafe_allow_html=True
                    )
                if i == 2:    
                    break

            # --- 5. VISUALISATION (GRAPHIQUE) ---
            chart = alt.Chart(final_leaderboard).mark_bar().encode(
                x=alt.X('total_points:Q', title='Points cumulés'),
                y=alt.Y('display_name:N', sort='-x', title='Athlète'),
                color=alt.Color(
                    'total_points:Q',
                    legend=None,
                    scale=alt.Scale(range=["#5E5D5D", '#E62E2D'])),
                    #scale=alt.Scale(scheme='goldorange')),
                tooltip=['display_name', 'total_points']
            ).properties(height=max(400, len(final_leaderboard)*30))
            
            st.altair_chart(chart, use_container_width=True)

            # --- 6. TABLEAUX DÉTAILLÉS ---
            #with st.expander("📊 Classement complet et détails mois par mois", expanded=True):
                
            # A. CLASSEMENT GÉNÉRAL
            """
            st.markdown("#### 🏆 Classement Général")
            
            final_leaderboard['Rang'] = [
                f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'#{i+1}'} {row['firstname']}"
                for i, row in final_leaderboard.iterrows()
            ]
            
            st.dataframe(
                final_leaderboard[['avatar_url', 'Rang', 'total_points']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "avatar_url": st.column_config.ImageColumn("", width="small"),
                    "Rang": st.column_config.TextColumn("Athlète"),
                    "total_points": st.column_config.ProgressColumn(
                        "Points Total",
                        format="%d pts",
                        min_value=0,
                        max_value=int(final_leaderboard['total_points'].max())
                    ),
                }
            )

            st.divider()
            """

            # B. TABLEAU DÉTAILLÉ (PIVOT)
            #st.markdown("#### 🗓️ Détail : points gagnés par mois (sera complété avec les kms correspondants)")
            
            # Création du Pivot Table : Lignes=Noms, Colonnes=Mois, Valeurs=Points
            pivot_df1 = df_scores.pivot_table(
                index=['display_name'],
                columns='month_name',
                values='points_month',
                fill_value=0
            ).astype(int)

            # Pivot sur la colonne 'display_text' qu'on a créée plus haut
            pivot_df2 = df_scores.pivot_table(
                index=['display_name'],
                columns='month_name',
                values='display_text',
                aggfunc='first',
                fill_value="0 pts (0 km)"
            )

            # 1. Trier les lignes (Athlètes) selon le classement général
            # On utilise l'ordre de 'final_leaderboard'
            ordered_names = final_leaderboard.set_index(['display_name']).index
            # On filtre pour ne garder que ceux présents (sécurité)
            existing_names = [n for n in ordered_names if n in pivot_df1.index]
            pivot_df1 = pivot_df1.reindex(existing_names)

            # 2. Trier les colonnes (Mois) chronologiquement et pas alphabétiquement
            # On recrée la liste des mois dans l'ordre de leur apparition
            months_order = df_scores.sort_values('month_num', ascending=False)['month_name'].unique()
            pivot_df1 = pivot_df1[months_order]

            nb_lignes = len(final_leaderboard)
            hauteur_calculee = (nb_lignes * 35) + 40

            # Affichage
            """
            st.dataframe(
                pivot_df1, 
                use_container_width=True,
                height=hauteur_calculee,
                column_config={
                    col: st.column_config.NumberColumn(
                        col, 
                        width='small',
                        format="%d pts" 
                    ) for col in pivot_df1.columns
                }
            )
            """
            # Affichage du tableau final
            """
            st.dataframe(
                pivot_df2, 
                use_container_width=True,
                column_config={
                    col: st.column_config.TextColumn(col, width="medium") 
                    for col in pivot_df2.columns
                }
            )
            """

            # --- 6. TABLEAU DÉTAILLÉ (LISTE VERTICALE POUR MOBILE) ---
            st.divider()
            st.markdown("#### 📜 Historique détaillé par mois")

            # On trie d'abord par Mois (numérique) puis par Points (décroissant)
            df_details = df_scores.sort_values(
                by=['month_num', 'points_month'], 
                ascending=[False, False]
            ).copy()

            # On prépare une colonne propre pour le mois
            # (ex: "01 - January") pour assurer un bon tri dans l'affichage
            df_details['Mois'] = df_details.apply(
                lambda x: f"{str(x['month_num']).zfill(2)} - {x['month_name']}", axis=1
            )

            # On renomme pour l'affichage
            df_details = df_details.rename(columns={
                'display_name': 'Athlète',
                'display_text': 'Résultat'
            })

            # Calcul de la hauteur pour éviter le double scroll
            nb_lignes = len(df_details)
            hauteur_tab = (nb_lignes * 35) + 40

            st.dataframe(
                df_details[['Mois', 'Athlète', 'Résultat']],
                use_container_width=True,
                hide_index=True,
                height=hauteur_tab,
                column_config={
                    "Mois": st.column_config.TextColumn("Mois", width="medium"),
                    "Athlète": st.column_config.TextColumn("Athlète", width="medium"),
                    "Résultat": st.column_config.TextColumn("Points (KM)", width="large"),
                }
)


        else:
            st.warning("Pas assez de données pour calculer la régularité.")
            
    else:
        st.info(f"Aucune activité trouvée pour {selected_year}.")