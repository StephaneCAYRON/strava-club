import streamlit as st
import pandas as pd
from strava_operations import *
from db_operations import *
from ui_components import common_critria

def render_tab_km(texts):
    """Contenu de l'onglet Leaderboard avec Compteur de sorties pour l'année"""
    
    # --- 1. SÉLECTION  GROUPE et ANNEE ---
    selected_g, selected_year = common_critria("km")

    res = get_leaderboard_by_group_by_year(selected_g['group_id'], selected_year)
    
    if res.data:
        df = pd.DataFrame(res.data)
        
        # Traitement Date
        df['start_date'] = pd.to_datetime(df['start_date'])
        df['Year'] = df['start_date'].dt.year
        df['Mois'] = df['start_date'].dt.month_name()
        df['Mois_Num'] = df['start_date'].dt.month
    
        #available_years = sorted(df['Year'].unique(), reverse=True)
        #selected_year = col_filter1.selectbox("Année", available_years)
        
        df_year = df[df['Year'] == selected_year]

        months_in_data = df_year.sort_values('Mois_Num')['Mois'].unique().tolist()
        
        option_all = texts["all_year"]
        options_list = [option_all] + months_in_data
        
        # Sélection par défaut : dernier mois actif -> remplacé par toute l'année
        # default_index = len(options_list) - 1 if len(months_in_data) > 0 else 0
        # selected_period = col_filter2.selectbox("Période", options_list, index=default_index)
        # selected_period = col_filter2.selectbox("Période", options_list, index=0)
        # selected_period = st.pills("Mois", options_list, selection_mode="single", default=options_list[0])
        selected_period =st.segmented_control("Mois", options_list, selection_mode="single", default=options_list[0])

        # --- LOGIQUE DE FILTRAGE ---
        if selected_period == option_all:
            df_final = df_year
            title_suffix = f"{selected_year}"
            is_global_view = True
        else:
            df_final = df_year[df_year['Mois'] == selected_period]
            title_suffix = f"{selected_period} {selected_year}"
            is_global_view = False

        # --- CLASSEMENT (AGGRÉGATION MULTIPLE) ---
        # On utilise .agg pour calculer la somme des km ET compter le nombre d'activités
        leaderboard = df_final.groupby(['id_strava','firstname', 'avatar_url']).agg(
            total_km=('distance_km', 'sum'),
            total_rides=('distance_km', 'count') # Compte le nombre de lignes
        ).sort_values('total_km', ascending=False).reset_index()

        st.markdown(f"### Kilométrage : {title_suffix}")
        
        if not leaderboard.empty:
            
            # On utilise un conteneur pour styliser un peu
            for i, row in leaderboard.iterrows():
                # Préparation des données
                rank_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
                avatar = get_safe_avatar_url(row['avatar_url'])
                
                # On crée une ligne avec 3 colonnes de largeurs différentes
                # [Image, Nom/Stats, Distance]
                c1, c2, c3 = st.columns([1, 4, 2])
                
                with c1:
                    st.image(avatar, width=50)
                
                with c2:
                    st.markdown(f"**{rank_icon} {row['firstname']}**")
                    #if is_global_view:
                    st.caption(f"{row['total_rides']} {texts['rides']}")
                with c3:
                    # URL du profil de l'athlète
                    strava_profile_url = f"https://www.strava.com/athletes/{row['id_strava']}"
                    # Choix du logo (Version orange pour le lien)
                    # Affiche "120.5 km [Icone]" sur la même ligne
                    strava_icon = "https://www.strava.com/favicon.ico"
                    st.markdown(
                        f"**{row['total_km']:.1f}** km "
                        f'<a href="{strava_profile_url}" target="_blank">'
                        f'<img src="{strava_icon}" width="15" style="margin-left: 5px; margin-bottom: 3px;">'
                        f'</a>', 
                        unsafe_allow_html=True
                    )
                    
                
                #st.divider() # Petite ligne de séparation entre les athlètes

            with st.expander("Voir le tableau détaillé"):
                st.dataframe(
                    leaderboard[['firstname', 'total_km', 'total_rides']], 
                    use_container_width=True,
                    column_config={
                        "firstname": "Athlète",
                        "total_km": st.column_config.NumberColumn("Distance (km)", format="%.1f"),
                        "total_rides": st.column_config.NumberColumn("Sorties")
                    }
                )
        else:
            st.warning("Aucune activité trouvée pour cette période.")

    else:
        st.info("Aucune donnée disponible pour ce groupe.")