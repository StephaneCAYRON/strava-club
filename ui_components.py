import streamlit as st
import pandas as pd
import altair as alt
from strava_operations import *
from db_operations import *

def sidebar_component(texts):
    """Gère l'affichage et les actions de la barre latérale."""
    
    # --- SÉLECTEUR DE LANGUE (ICONES DRAPEAUX) ---
    if False: #desactivé pour l'instnat
        st.sidebar.write("Language / Langue")
        col_fr, col_en = st.sidebar.columns(2)
        with col_fr:
            if st.button("FR", use_container_width=True):
                st.session_state.lang = "fr"
                st.toast("Langue modifiée en Français ! 🇫🇷")
                st.rerun()
        with col_en:
            if st.button("EN", use_container_width=True):
                st.session_state.lang = "en"
                st.toast("Language switched to English! 🇬🇧")
                st.rerun()
    
    athlete = st.session_state.athlete
    st.sidebar.image(athlete.get("profile_medium"), width=100)
    st.sidebar.success(f"{texts['sidebar_connected']} {athlete.get('firstname')}")

    if st.sidebar.button(f"{texts['logout']}", use_container_width=True):
        st.session_state.access_token = None
        st.session_state.auto_sync_done = False
        st.rerun()

    if st.sidebar.button(texts["sync_btn"], use_container_width=True):
        from strava_operations import fetch_all_activities_parallel
        with st.spinner(texts["sync_spinner"]):
            all_activities = fetch_all_activities_parallel(st.session_state.access_token)
            if all_activities:
                sync_profile_and_activities(athlete, all_activities, st.session_state.refresh_token)
                st.sidebar.success(texts["sync_success"])
                st.rerun()

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
        st.markdown(athlete['id'])
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

def render_tab_leaderboard_old(texts):
    """Contenu de l'onglet Leaderboard."""
    m_groups = get_user_memberships(st.session_state.athlete['id'])
    my_approved = [g for g in m_groups.data if g['status'] == 'approved']
    
    if my_approved:
        selected_g = st.selectbox("Sélectionner un groupe", my_approved, format_func=lambda x: x['groups']['name'])
        res = get_leaderboard_by_group(selected_g['group_id'])
        if res.data:
            df = pd.DataFrame(res.data).groupby(['firstname', 'avatar_url'])['distance_km'].sum().sort_values(ascending=False).reset_index()
            cols = st.columns(4)
            for i, row in df.iterrows():
                with cols[i % 4]:
                    st.image(row['avatar_url'], width=60)
                    st.metric(f"#{i+1} {row['firstname']}", f"{row['distance_km']:.1f} km")
    else:
        st.info(texts["no_group"])


def render_tab_leaderboard(texts):
    """Contenu de l'onglet Leaderboard avec Compteur de sorties pour l'année"""
    
    # 1. Récupération des données
    athlete_id = st.session_state.athlete['id']
    m_groups = get_user_memberships(athlete_id)
    my_approved = [g for g in m_groups.data if g['status'] == 'approved']
    
    if not my_approved:
        st.info(texts["no_group"])
        return

    selected_g = st.selectbox(
        "Sélectionner un groupe", 
        my_approved, 
        format_func=lambda x: x['groups']['name']
    )

    # --- FILTRES UI ---
    col_filter1, col_filter2 = st.columns(2)

    years = get_years_for_group(selected_g['group_id'])
    if years:
        selected_year = col_filter1.selectbox("Année", years)
    else:
        selected_year = 2026 # Valeur par défaut

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
        
        # Sélection par défaut : dernier mois actif
        default_index = len(options_list) - 1 if len(months_in_data) > 0 else 0
        selected_period = col_filter2.selectbox("Période", options_list, index=default_index)

        # --- LOGIQUE DE FILTRAGE ---
        if selected_period == option_all:
            df_final = df_year
            title_suffix = f"{selected_year} (Global)"
            is_global_view = True
        else:
            df_final = df_year[df_year['Mois'] == selected_period]
            title_suffix = f"{selected_period} {selected_year}"
            is_global_view = False

        st.write(f"---------------DEBUG DF_FINAL: {len(df_final)} lignes trouvées")
        st.write(f"Athlètes présents: {df_final['firstname'].unique()}")
        st.write(f"---------------DEBUG DF_YEAR: {len(df_year)} lignes trouvées")
        st.write(f"Athlètes présents: {df_year['firstname'].unique()}")
        

        # --- CLASSEMENT (AGGRÉGATION MULTIPLE) ---
        # On utilise .agg pour calculer la somme des km ET compter le nombre d'activités
        leaderboard = df_final.groupby(['firstname', 'avatar_url']).agg(
            total_km=('distance_km', 'sum'),
            total_rides=('distance_km', 'count') # Compte le nombre de lignes
        ).sort_values('total_km', ascending=False).reset_index()

        st.markdown(f"### 🏆 Classement : {title_suffix}")
        
        if not leaderboard.empty:
            cols = st.columns(4)
            for i, row in leaderboard.iterrows():
                with cols[i % 4]:
                    st.image(row['avatar_url'], width=60)
                    
                    rank_icon = "🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else f"#{i+1}"
                    
                    # Préparation des valeurs à afficher
                    display_km = f"{row['total_km']:.1f} km"
                    
                    # Si c'est la vue globale, on affiche le nombre de sorties en "delta" (sous le chiffre)
                    # delta_color="off" permet de l'afficher en gris (neutre)
                    if is_global_view:
                        sub_text = f"{row['total_rides']} {texts['rides']}"
                        st.metric(
                            label=f"{rank_icon} {row['firstname']}", 
                            value=display_km, 
                            delta=sub_text, 
                            delta_color="off" 
                        )
                    else:
                        # Affichage standard pour le mois
                        st.metric(
                            label=f"{rank_icon} {row['firstname']}", 
                            value=display_km
                        )
            
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