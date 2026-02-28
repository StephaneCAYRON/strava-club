import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from strava_operations import *
from db_operations import *
from ui_components import common_critria

def render_tab_leaderboard(texts):
    """Page unique fusionnée avec tableau de statistiques complet en bas de page"""
    
    # --- 1. FILTRE DE MÉTRIQUE ---
    metric_choice = st.segmented_control(
        "Métrique", 
        ["Kilomètres", "Dénivelé", "Temps"], # Ajout de "Temps"
        default="Kilomètres",
        selection_mode="single"
    )

    # --- 2. FILTRES COMMUNS (Groupe & Année) ---
    selected_g, selected_year = common_critria("leaderboard")

    if selected_g == "":
        st.info("Aucun groupe disponible")
        return

    # Configuration dynamique pour le Top 3 et Graphique
    if metric_choice == "Kilomètres":
        col_target = 'distance_km'
        label_unit = "km"
        val_format = "%.1f"
        chart_label = "Total cumulé (km)"
        title_prefix = "Cumul kilométrage"
    elif metric_choice == "Dénivelé":
        col_target = 'total_elevation_gain'
        label_unit = "m"
        val_format = "%d"
        chart_label = "Dénivelé cumulé (m)"
        title_prefix = "Cumul dénivelé"
    else: # Temps
        col_target = 'moving_time_hr' # On utilisera une colonne convertie en heures
        label_unit = "h"
        val_format = "%.1f"
        chart_label = "Temps cumulé (h)"
        title_prefix = "Cumul temps de selle"

    # Récupération des données
    res = get_leaderboard_by_group_by_year_cached(selected_g['group_id'], selected_year)
    
    if res.data:
        df = pd.DataFrame(res.data)
        df['start_date'] = pd.to_datetime(df['start_date'])
        df['Year'] = df['start_date'].dt.year
        df['Mois'] = df['start_date'].dt.month_name()
        df['Mois_Num'] = df['start_date'].dt.month
        
        # Sécurité : vérifier que moving_time existe, sinon la créer à 0
        if 'moving_time' not in df.columns:
            df['moving_time'] = 0
            
        # Création de la colonne temps en heures pour le graphique et le tableau
        df['moving_time_hr'] = df['moving_time'] / 3600
    
        df_year = df[df['Year'] == selected_year]
        months_in_data = df_year.sort_values('Mois_Num')['Mois'].unique().tolist()
        option_all = texts["all_year"]
        options_list = [option_all] + months_in_data
        
        # --- 3. FILTRE DE PÉRIODE ---
        selected_period = st.segmented_control("", options_list, selection_mode="single", default=options_list[0])

        if selected_period == option_all:
            df_final = df_year
            title_suffix = f"{selected_year}"
        else:
            df_final = df_year[df_year['Mois'] == selected_period]
            title_suffix = f"{selected_period} {selected_year}"

        # --- 4. CALCUL DES STATISTIQUES COMPLETES ---
        # Calcul du gradient par activité pour la moyenne (D+ / distance en mètres) * 100
        df_final = df_final.copy()
        df_final['gradient'] = (df_final['total_elevation_gain'] / (df_final['distance_km'].replace(0, np.nan) * 1000)) * 100
        
        leaderboard = df_final.groupby(['id_strava','firstname', 'avatar_url']).agg(
            total_km=('distance_km', 'sum'),
            total_dplus=('total_elevation_gain', 'sum'),
            total_rides=('distance_km', 'count'),
            total_time=('moving_time', 'sum'),
            total_time_hr=('moving_time_hr', 'sum'), # On somme aussi les heures directement
            avg_gradient=('gradient', 'mean') # Moyenne des pentes de chaque sortie
        ).reset_index()

        # Calcul des moyennes par sortie
        leaderboard['avg_km'] = leaderboard['total_km'] / leaderboard['total_rides']
        leaderboard['avg_dplus'] = leaderboard['total_dplus'] / leaderboard['total_rides']
        
        # Calcul de la vitesse moyenne (Distance / (Temps en secondes / 3600))
        if 'total_time' in leaderboard.columns and (leaderboard['total_time'] > 0).any():
            leaderboard['avg_speed'] = leaderboard['total_km'] / (leaderboard['total_time'] / 3600)
        else:
            leaderboard['avg_speed'] = 0
        
        # Colonne pivot pour le Top 3 et le tri (basée sur le choix de l'utilisateur)
        if metric_choice == "Kilomètres":
            leaderboard['total_val'] = leaderboard['total_km']
        elif metric_choice == "Dénivelé":
            leaderboard['total_val'] = leaderboard['total_dplus']
        else:
            leaderboard['total_val'] = leaderboard['total_time_hr']
            
        leaderboard = leaderboard.sort_values('total_val', ascending=False).reset_index(drop=True)

        st.markdown(f"### {title_prefix} : {title_suffix}")
        
        if not leaderboard.empty:
            # --- TOP 3 ---
            for i, row in leaderboard.iterrows():
                rank_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
                avatar = get_safe_avatar_url(row['avatar_url'])
                c1, c2, c3 = st.columns([1, 4, 2])
                with c1: st.image(avatar, width=50)
                with c2:
                    st.markdown(f"**{rank_icon} {row['firstname']}**")
                    st.caption(f"{row['total_rides']} {texts['rides']}")
                with c3:
                    strava_profile_url = f"https://www.strava.com/athletes/{row['id_strava']}"
                    
                    # Le formatage change selon la métrique (entier pour D+, 1 décimale pour le reste)
                    if metric_choice == "Dénivelé":
                        display_val = f"{row['total_val']:,.0f}".replace(",", " ")
                    else:
                        display_val = f"{row['total_val']:.1f}"
                        
                    st.markdown(f"**{display_val}** {label_unit} "
                                f'<a href="{strava_profile_url}" target="_blank"><img src="https://www.strava.com/favicon.ico" width="15"></a>', 
                                unsafe_allow_html=True)
                if i == 2: break

            # --- 5. GRAPHIQUE D'ÉVOLUTION ---
            st.write("")
            st.subheader(f"Progression mensuelle ({label_unit})")
            df_chart = df_year.groupby(['firstname', 'Mois_Num', 'Mois'])[col_target].sum().reset_index(name='monthly_sum')
            df_chart = df_chart.sort_values(['firstname', 'Mois_Num'])
            df_chart['cumul_val'] = df_chart.groupby('firstname')['monthly_sum'].cumsum()

            line_chart = alt.Chart(df_chart).mark_line(point=True).encode(
                x=alt.X('Mois_Num:O', title="Mois"),
                y=alt.Y('cumul_val:Q', title=chart_label),
                color=alt.Color('firstname:N', title="Athlète"),
                tooltip=['firstname', 'Mois', alt.Tooltip('cumul_val:Q', format=',.1f')]
            ).properties(height=400).interactive()
            st.altair_chart(line_chart, use_container_width=True)    


            # --- 6. GRAPHIQUE ANALYTIQUE (PROFIL DES ATHLÈTES) ---
            st.write("### 📊 Profil des membres (Distance vs D+)")

            # On prépare les données pour Altair
            # On filtre les athlètes qui n'ont pas de données pour éviter les points à (0,0)
            df_scatter = leaderboard[leaderboard['total_km'] > 0].copy()

            scatter_chart = alt.Chart(df_scatter).mark_circle(size=120, opacity=0.8).encode(
                x=alt.X('total_km:Q', title="Distance Totale (km)"),
                y=alt.Y('total_dplus:Q', title="Dénivelé Total (m)"),
                color=alt.Color('avg_gradient:Q', 
                                title="Pente Moy. (%)", 
                                scale=alt.Scale(scheme='redyellowgreen', reverse=True)),
                tooltip=[
                    alt.Tooltip('firstname:N', title="Athlète"),
                    alt.Tooltip('total_km:Q', format=".1f", title="Total Km"),
                    alt.Tooltip('total_dplus:Q', format=".0f", title="Total D+"),
                    alt.Tooltip('avg_gradient:Q', format=".2f", title="Pente moy. %"),
                    alt.Tooltip('total_rides:Q', title="Sorties")
                ]
            ).properties(
                height=500
            ).interactive()

            # Ajout des noms des athlètes à côté des points (optionnel mais sympa)
            text = scatter_chart.mark_text(
                align='left',
                baseline='middle',
                dx=7
            ).encode(
                text='firstname:N'
            )

            st.altair_chart(scatter_chart + text, use_container_width=True)


            # --- 7. TABLEAU DÉTAILLÉ COMPLET ---
            st.markdown("#### 📊 Statistiques détaillées de la période")
            
            # Préparation du libellé du rang
            leaderboard['Rang'] = [f"{i+1}" for i in range(len(leaderboard))]
            nb_lignes = len(leaderboard)
            hauteur_calculee = (nb_lignes * 35) + 40

            st.dataframe(
                leaderboard[['avatar_url', 'Rang', 'firstname', 'total_km', 'total_dplus', 'total_time_hr', 'total_rides', 'avg_km', 'avg_speed', 'avg_dplus', 'avg_gradient']], 
                hide_index=True,
                use_container_width=True,
                height=hauteur_calculee,
                column_config={
                    "avatar_url": st.column_config.ImageColumn("", width=30),
                    "Rang": st.column_config.TextColumn("Pos.", width="10"),
                    "firstname": st.column_config.TextColumn("Athlète", width="10"),
                    "total_km": st.column_config.NumberColumn("Km", format="%.1f", width="10"),
                    "total_dplus": st.column_config.NumberColumn("D+ (m)", format="%d", width="10"),
                    "total_time_hr": st.column_config.NumberColumn("Temps (h)", format="%.1f", width="small"),
                    "total_rides": st.column_config.NumberColumn("Sorties", width="10"),
                    "avg_km": st.column_config.NumberColumn("Km/sortie", format="%.1f", width="10"),
                    "avg_speed": st.column_config.NumberColumn("Vit. Moy.", format="%.1f km/h", width="10"),
                    "avg_dplus": st.column_config.NumberColumn("D+/sortie", format="%d m", width="10"),
                    "avg_gradient": st.column_config.NumberColumn("% Pente moy.", format="%.2f %%", width="10")
                }
            )
        else:
            st.warning("Aucune activité trouvée.")
    else:
        st.info("Aucune donnée disponible.")