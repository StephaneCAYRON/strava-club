import streamlit as st
import pandas as pd
import altair as alt
from strava_operations import *
from db_operations import *
from ui_components import common_critria

def render_tab_sunday(texts):
    """Onglet classement des sorties du Dimanche matin avec filtre mensuel et tableau détaillé"""
    
    # --- 1. SÉLECTION  GROUPE et ANNEE ---
    selected_g, selected_year = common_critria("sunday")
    
    if selected_g == "":
        st.info("No group yet")
        return

    # --- 2. RÉCUPÉRATION DES DONNÉES ---
    res = get_leaderboard_by_group_by_year(selected_g['group_id'], selected_year)
    
    if res.data:
        
        df = pd.DataFrame(res.data)
        df['start_date'] = pd.to_datetime(df['start_date'])

        # --- 3. FILTRAGE DIMANCHE MATIN ---
        # Dimanche (6) entre 5h et 10h
        df_sunday = df[
            (df['start_date'].dt.dayofweek == 6) & 
            (df['start_date'].dt.hour >= 5) & 
            (df['start_date'].dt.hour <= 10)
        ].copy()

        if not df_sunday.empty:
            # --- 4. GESTION DES MOIS ---
            df_sunday['Mois'] = df_sunday['start_date'].dt.month_name()
            df_sunday['Mois_Num'] = df_sunday['start_date'].dt.month

            months_available = df_sunday.sort_values('Mois_Num')['Mois'].unique().tolist()
            
            option_all = texts["all_year"]
            options_list = [option_all] + months_available
            
            st.write("")
            selected_period = st.segmented_control(
                "Période", 
                options=options_list, 
                selection_mode="single", 
                default=option_all,
                key="seg_sunday_month"
            )

            if selected_period == option_all:
                df_final = df_sunday
                title_suffix = f"{selected_year}"
            else:
                df_final = df_sunday[df_sunday['Mois'] == selected_period]
                title_suffix = f"{selected_period} {selected_year}"

            # --- 5. CLASSEMENT ET AFFICHAGE ---
            st.markdown(f"### {texts['sunday_header']} - {title_suffix}")
            st.caption(texts["sunday_desc"])

            # Agrégation : Compte des sorties ET somme des KM
            leaderboard = df_final.groupby(['id_strava', 'firstname', 'avatar_url']).agg(
                count=('distance_km', 'count'), total_km=('distance_km', 'sum')
            ).sort_values('count', ascending=False).reset_index()
        
            #leaderboard = leaderboard.sort_values(['count'], ascending=[False])
            i = 0
            if not leaderboard.empty:
                # Affichage Visuel (Podium)
                for i, row in leaderboard.iterrows():
                    rnk_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
                    c1, c2, c3 = st.columns([1, 4, 2])
                    with c1:
                        st.image(get_safe_avatar_url(row['avatar_url']), width=40)
                    with c2:
                        st.markdown(f"**{rnk_icon} {row['firstname']}**")
                        st.caption(f"{row['total_km']:.1f} km cumulés") # Petit ajout sympa
                    with c3:
                        # URL du profil de l'athlète
                        strava_profile_url = f"https://www.strava.com/athletes/{row['id_strava']}"
                        strava_icon = "https://www.strava.com/favicon.ico"
                        #st.markdown(f"**{row['count']}** {texts['sunday_rides_count']}")
                        st.markdown(
                            f"**{row['count']}** {texts['sunday_rides_count']}"
                            f'<a href="{strava_profile_url}" target="_blank">'
                            f'<img src="{strava_icon}" width="15" style="margin-left: 5px; margin-bottom: 3px;">'
                            f'</a>', 
                            unsafe_allow_html=True
                        )
                    if i == 2:
                        break

                # --- 6. GRAPHIQUE D'ÉVOLUTION CUMULÉE ---
                st.write("")
                st.subheader("Progression mensuelle")
                
                # Préparation des données pour le graphique (on utilise df_sunday qui contient toute l'année)
                # 1. On groupe par athlète et par mois
                df_chart = df_sunday.groupby(['firstname', 'Mois_Num', 'Mois']).size().reset_index(name='monthly_count')
                
                # 2. On calcule le cumul par athlète au fil des mois
                df_chart = df_chart.sort_values(['firstname', 'Mois_Num'])
                df_chart['cumul_sorties'] = df_chart.groupby('firstname')['monthly_count'].cumsum()

                # 3. Création du graphique Altair
                line_chart = alt.Chart(df_chart).mark_line(point=True).encode(
                    x=alt.X('Mois_Num:O', title="Mois", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('cumul_sorties:Q', title="Cumul des sorties"),
                    color=alt.Color('firstname:N', title="Athlète"),
                    tooltip=['firstname', 'Mois', 'cumul_sorties']
                ).properties(
                    height=500
                ).interactive()

                st.altair_chart(line_chart, use_container_width=True)
               
                with st.expander("Classement complet", True):
                    leaderboard['Athlete'] = [
                        f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'#{i+1}'} {row['firstname']}"
                        for i, row in leaderboard.iterrows()
                    ]
                    st.dataframe(
                        leaderboard[['avatar_url','Athlete', 'count', 'total_km']], 
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "avatar_url": st.column_config.ImageColumn("", width=10),
                            "Athlete": st.column_config.TextColumn("Rang & Nom"),
                            #"count": st.column_config.NumberColumn("Sorties Dominicales", format="%d 🚴"),
                            "count": st.column_config.NumberColumn("Sorties Dominicales", format="%d"),
                            "total_km": st.column_config.NumberColumn("Distance Cumulée", format="%.1f km")
                        }
                    )
            else:
                st.warning(f"Aucune sortie dominicale en {selected_period}.")
        else:
            st.warning("Aucune sortie trouvée le dimanche matin (5h-10h) pour cette année.")
    else:
        st.info("Aucune donnée disponible.")