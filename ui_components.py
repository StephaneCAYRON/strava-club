import streamlit as st
import pandas as pd
import altair as alt
from strava_operations import *
from db_operations import *

def render_tab_stats(texts):
    """Contenu de l'onglet Statistiques Personnelles."""
    # --- STATS MACROS ---
    total_db = st.session_state.get('total_activities', 0)
    athlete = st.session_state.athlete
    result = get_strava_stats(st.session_state.access_token, athlete.get('id'))
    if isinstance(result, tuple) and len(result) == 2:
        stats_string, total_strava = result
        st.info(f"{stats_string}, total: {total_db}")

    if 'last_activities' in st.session_state and st.session_state.last_activities:
        st.subheader(texts["last_activities"])
        df_p = pd.DataFrame(st.session_state.last_activities)
        
        if 'distance_km' not in df_p.columns:
            df_p['distance_km'] = df_p['distance'] / 1000
        
        df_p['start_date'] = pd.to_datetime(df_p['start_date'])
        df_p['strava_url'] = "https://www.strava.com/activities/" + df_p['id_activity'].astype(str)

        chart = alt.Chart(df_p).mark_bar(cursor='pointer').encode(
            x=alt.X('start_date:T', title='Date'),
            y=alt.Y('distance_km:Q', title='Distance (km)'),
            #href='strava_url:N',
            tooltip=[
                alt.Tooltip('name:N', title='Nom'),
                alt.Tooltip('distance_km:Q', title='Distance (km)', format='.1f'),
                alt.Tooltip('start_date:T', title='Date', format='%Y-%m-%d') 
            ]
        ).properties(height=400).configure_mark(invalid=None).interactive()

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(df_p[['start_date', 'name', 'distance_km', 'type']], use_container_width=True)

def render_tab_groups(texts):
    """Contenu de l'onglet Gestion des Groupes."""
    athlete = st.session_state.athlete
    col_list, col_admin = st.columns([1, 1], gap="large")
    
    with col_list:
        st.subheader(texts["my_groups"])
        m_groups = get_user_memberships(athlete['id'])
        for g in m_groups.data:
            icon = "✅" if g['status'] == 'approved' else "⏳"
            st.write(f"{icon} **{g['groups']['name']}**")
        
        st.divider()
        st.subheader(texts["join_group"])
        all_g = get_all_groups()
        if all_g.data:
            already_member = [g['group_id'] for g in m_groups.data]
            available = [g for g in all_g.data if g['id'] not in already_member]
            if available:
                g_to_join = st.selectbox(texts["group_name"], options=available, format_func=lambda x: x['name'])
                if st.button(texts["join_group"], use_container_width=True):
                    request_to_join_group(g_to_join['id'], athlete['id'])
                    st.success(texts["request_sent"])
                    st.rerun()

    with col_admin:
        #st.markdown(athlete['id'])
        if athlete['id'] == 5251772: #desactivation pour l'instant
            st.markdown("### 🛠 Espace Administration")
            with st.expander(f"➕ {texts['create_group']}"):
                name = st.text_input(texts["group_name"], key="new_g")
                if st.button(texts["create_group"], use_container_width=True):
                    create_group(name, athlete['id'])
                    st.rerun()
            pending = get_pending_requests_for_admin(athlete['id'])
            if pending or any(g['status'] == 'approved' for g in m_groups.data):
                
                with st.container(border=True):
                    if pending and pending.data:
                        for p in pending.data:
                            c1, c2 = st.columns([2, 1])
                            c1.write(f"**{p['profiles']['firstname']}** -> {p['groups']['name']}")
                            if c2.button(texts["approve"], key=p['id'], type="primary"):
                                update_membership_status(p['id'], "approved")
                                st.rerun()
                    else:
                        st.write("Aucune demande en attente.")

def render_tab_leaderboard(texts):
    """Contenu de l'onglet Leaderboard avec Compteur de sorties pour l'année"""
    
    # 1. Récupération des données
    athlete_id = st.session_state.athlete['id']
    m_groups = get_user_memberships(athlete_id)
    my_approved = [g for g in m_groups.data if g['status'] == 'approved']
    
    if not my_approved:
        st.info(texts["no_group"])
        return
    
    # Crée un dictionnaire de correspondance Nom -> Objet
    group_dict = {g['groups']['name']: g for g in my_approved}
    group_names = list(group_dict.keys())

    # Affiche les pills avec les noms uniquement
    selected_name = st.pills(
        "Groupe", 
        options=group_names, 
        selection_mode="single", 
        default=group_names[0]
    )

    # Récupère l'objet complet à partir du nom sélectionné
    selected_g = group_dict[selected_name]

    years = get_years_for_group(selected_g['group_id'])
    if years:
        #selected_year = col_filter1.selectbox("Année", years)
        # Au lieu de selectbox pour l'année
        selected_year = st.pills("Année", years, selection_mode="single", default=years[0])
    else:
        selected_year = 2026 # Valeur par défaut si problème

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
            title_suffix = f"{selected_year} (Global)"
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

        st.markdown(f"### 🏆 Classement : {title_suffix}")
        
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
                    if is_global_view:
                        st.caption(f"{row['total_rides']} {texts['rides']}")
                
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

def render_tab_sunday(texts):
    """Onglet classement des sorties du Dimanche matin avec filtre mensuel et tableau détaillé"""
    
    # --- 1. SÉLECTION DU GROUPE ---
    athlete_id = st.session_state.athlete['id']
    m_groups = get_user_memberships(athlete_id)
    my_approved = [g for g in m_groups.data if g['status'] == 'approved']
    
    if not my_approved:
        st.info(texts["no_group"])
        return
    
    group_dict = {g['groups']['name']: g for g in my_approved}
    group_names = list(group_dict.keys())

    # Sélection Groupe et Année
    c_sel1, c_sel2 = st.columns(2)
    with c_sel1:
        selected_name = st.pills(
            "Groupe", 
            options=group_names, 
            selection_mode="single", 
            default=group_names[0],
            key="pills_sunday_group"
        )
    selected_g = group_dict[selected_name]

    with c_sel2:
        years = get_years_for_group(selected_g['group_id'])
        if years:
            selected_year = st.pills("Année", years, selection_mode="single", default=years[0], key="pills_sunday_year")
        else:
            selected_year = 2026

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
            (df['start_date'].dt.hour < 10)
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
                    rank_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
                    
                    c1, c2, c3 = st.columns([1, 4, 2])
                    with c1:
                        st.image(get_safe_avatar_url(row['avatar_url']), width=40)
                    with c2:
                        st.markdown(f"**{rank_icon} {row['firstname']}**")
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
                    #st.divider()

                # --- 6. GRAPHIQUE D'ÉVOLUTION CUMULÉE ---
                st.write("")
                st.subheader("Progression de l'assiduité")
                
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
                    height=350
                ).interactive()

                st.altair_chart(line_chart, use_container_width=True)

                # --- LE TABLEAU DÉTAILLÉ (AJOUTÉ ICI) ---
                with st.expander("Voir le tableau détaillé"):
                    st.dataframe(
                        leaderboard[['firstname', 'count', 'total_km']], 
                        use_container_width=True,
                        column_config={
                            "firstname": "Athlète",
                            "count": st.column_config.NumberColumn("Sorties Dominicales", format="%d 🚴"),
                            "total_km": st.column_config.NumberColumn("Distance Cumulée", format="%.1f km")
                        },
                        hide_index=True # Plus propre sans l'index 0,1,2...
                    )
            else:
                st.warning(f"Aucune sortie dominicale en {selected_period}.")
        else:
            st.warning("Aucune sortie trouvée le dimanche matin (5h-10h) pour cette année.")
    else:
        st.info("Aucune donnée disponible.")