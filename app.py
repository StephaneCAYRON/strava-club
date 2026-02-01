# APP  déployée
# Param Strava https://www.strava.com/settings/api, callback = strava-club-challenge.streamlit.app, pour 
# STRAVA_REDIRECT_URI = 'https://strava-club-challenge.streamlit.app'

# APP  locale
# Param Strava https://www.strava.com/settings/api,  callback = localhost
# STRAVA_REDIRECT_URI = 'http://localhost:8501'

import streamlit as st
import pandas as pd
from db_operations import *
from strava_operations import *
from translation import lang_dict  # Import de votre dictionnaire existant
import altair as alt #

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Club Amicale Cyclo Escalquens 2026", page_icon="🚴", layout="wide")

# --- INITIALISATION DU SESSION STATE ---
for key in ['access_token', 'refresh_token', 'athlete', 'lang', 'auto_sync_done']:
    if key not in st.session_state:
        # Langue par défaut : français
        st.session_state[key] = "fr" if key == 'lang' else (False if key == 'auto_sync_done' else None)

# --- SÉLECTEUR DE LANGUE (ICONES DRAPEAUX) ---
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

# Chargement des labels correspondants
texts = lang_dict[st.session_state.lang]

# --- FONCTION DE MISE À JOUR UI ---
def refresh_local_data():
    if st.session_state.athlete:
        athlete_id = st.session_state.athlete.get('id')
        total, recent = get_athlete_summary(athlete_id)
        st.session_state.total_activities = total
        st.session_state.last_activities = recent

# --- LOGIQUE D'AUTHENTIFICATION ---
if "code" in st.query_params and st.session_state.access_token is None:
    data = exchange_code_for_token(st.query_params["code"])
    if data:
        st.session_state.access_token = data['access_token']
        st.session_state.refresh_token = data['refresh_token']
        st.session_state.athlete = data['athlete']
        refresh_local_data() 
        st.query_params.clear()
        st.rerun()

# --- INTERFACE PRINCIPALE ---
st.title(texts["title"])

if st.session_state.access_token is None:
    st.link_button(texts["connect"], get_strava_auth_url())
else:
    athlete = st.session_state.athlete
    st.sidebar.image(athlete.get("profile_medium"), width=100)
    st.sidebar.success(f"{texts['sidebar_connected']} {athlete.get('firstname')}")

    # BOUTON DÉCONNEXION
    if st.sidebar.button(texts["logout"]):
        st.session_state.access_token = None
        st.session_state.auto_sync_done = False
        st.rerun()

    # BOUTON SYNCHRO MANUELLE
    if st.sidebar.button(texts["sync_btn"]):
        with st.spinner(texts["sync_spinner"]):
            st.toast(texts["sync_spinner"])
            all_activities = fetch_all_activities_parallel(st.session_state.access_token)
            if all_activities:
                sync_profile_and_activities(athlete, all_activities, st.session_state.refresh_token)
                refresh_local_data()
                st.sidebar.success(texts["sync_success"])
                st.rerun()

    # --- LOGIQUE DE SYNCHRONISATION OPTIMISÉE ---
    if not st.session_state.auto_sync_done:
        with st.spinner(texts["auto_sync"]):
            # 1. On récupère uniquement les 100 plus récentes
            # st.info(texts["auto_sync"])
            latest_activities = fetch_page(st.session_state.access_token, page=1, per_page=100)
            if latest_activities:
                sync_profile_and_activities(athlete, latest_activities, st.session_state.refresh_token)
                refresh_local_data() 
                
        # 2. Si la base est quasi vide, on lance l'historique complet
        total_db = st.session_state.get('total_activities', 0)
        if total_db <= 100:
            with st.spinner(texts["sync_spinner"]):
                all_history = fetch_all_activities_parallel(st.session_state.access_token, max_pages=20)
                if all_history:
                    sync_profile_and_activities(athlete, all_history, st.session_state.refresh_token)
                    refresh_local_data()
        
        st.session_state.auto_sync_done = True
        st.rerun()

    # --- STATS MACROS ---
    total_db = st.session_state.get('total_activities', 0)
    
    result = get_strava_stats(st.session_state.access_token, athlete.get('id'))
    if isinstance(result, tuple) and len(result) == 2:
        stats_string, total_strava = result
        st.info(f"{stats_string}, total: {total_db}")
    
    # --- TABS PRINCIPAUX ---
    tab_stats , tab_leader, tab_groups = st.tabs([texts["tab_statsPerso"], texts["leaderboard_tab"], texts["group_tab"]])

    with tab_stats:

        # --- AFFICHAGE DES ACTIVITÉS PERSONNELLES ---
        if 'last_activities' in st.session_state and st.session_state.last_activities:
            st.subheader(texts["last_activities"])
            df_personal = pd.DataFrame(st.session_state.last_activities)
            
            if 'distance_km' not in df_personal.columns and 'distance' in df_personal.columns:
                df_personal['distance_km'] = df_personal['distance'] / 1000

            st.bar_chart(df_personal, x="start_date", y="distance_km")
            st.dataframe(df_personal[['start_date', 'name', 'distance_km', 'type']], use_container_width=True)
            
            # --- AFFICHAGE DES ACTIVITÉS PERSONNELLES BIS---
            st.subheader(texts["last_activities_test"])
            df_personal = pd.DataFrame(st.session_state.last_activities)
            
            if 'distance_km' not in df_personal.columns and 'distance' in df_personal.columns:
                df_personal['distance_km'] = df_personal['distance'] / 1000

            # Construction de l'URL Strava pour chaque activité
            # L'ID de l'activité est récupéré depuis la base de données
            df_personal['strava_url'] = "https://www.strava.com/activities/" + df_personal['id_activity'].astype(str)

            # Création du graphique Altair
            chart = alt.Chart(df_personal).mark_bar(
                cursor='pointer',
            ).encode(
                x=alt.X('start_date:T', title='Date'),
                y=alt.Y('distance_km:Q', title='Distance (km)'),
                href='strava_url:N',
                tooltip=[
                    alt.Tooltip('name:N', title='Nom'),
                    alt.Tooltip('distance_km:Q', title='Distance (km)', format='.1f'),
                    alt.Tooltip('type:N', title='Sport'),
                    alt.Tooltip('start_date:T', title='Date', format='%Y-%m-%d') 
                ]
            ).properties(
                height=400
            ).configure_mark(
                # C'est cette option qui force l'ouverture dans un nouvel onglet
                invalid=None
            ).configure_view(
                stroke=None
            ).interactive()

            st.altair_chart(chart, use_container_width=True)
        
        # Tableau récapitulatif en dessous
        st.dataframe(df_personal[['start_date', 'name', 'distance_km', 'type']], use_container_width=True)

    with tab_groups:
        col_list, col_admin = st.columns([1, 1], gap="large")
        
        with col_list:
            st.subheader(texts["my_groups"])
            m_groups = get_user_memberships(athlete['id'])
            if m_groups.data:
                for g in m_groups.data:
                    status_icon = "✅" if g['status'] == 'approved' else "⏳"
                    st.write(f"{status_icon} **{g['groups']['name']}** ({g['status']})")
            else:
                st.info(texts["no_group"])
            
            st.divider()
            st.subheader(texts["join_group"])
            all_g = get_all_groups()
            if all_g.data:
                # On exclut les groupes dont l'utilisateur est déjà membre pour épurer la liste
                already_member_ids = [g['group_id'] for g in m_groups.data]
                available_groups = [g for g in all_g.data if g['id'] not in already_member_ids]
                
                if available_groups:
                    g_to_join = st.selectbox(texts["group_name"], options=available_groups, format_func=lambda x: x['name'])
                    if st.button(texts["join_group"], use_container_width=True):
                        request_to_join_group(g_to_join['id'], athlete['id'])
                        st.success(texts["request_sent"])
                        st.rerun()
                else:
                    st.write("Vous avez rejoint tous les groupes disponibles !")

        with col_admin:
            # 1. Création de groupe (accessible à tous)
            with st.expander(f"➕ {texts['create_group']}"):
                new_g_name = st.text_input(texts["group_name"], key="new_g")
                if st.button(texts["create_group"], use_container_width=True):
                    if new_g_name:
                        create_group(new_g_name, athlete['id'])
                        st.toast(f"Groupe {new_g_name} créé !")
                        st.rerun()

            st.write("") # Espacement

            # 2. Zone d'administration (visible uniquement si l'utilisateur gère des groupes)
            pending = get_pending_requests_for_admin(athlete['id'])
            
            # On vérifie si l'utilisateur est admin de groupes (même s'il n'y a pas de requêtes)
            # pour afficher le panneau de gestion
            if pending or any(g['status'] == 'approved' for g in m_groups.data): 
                st.markdown("### 🛠 Espace Administration")
                with st.container(border=True):
                    st.caption("Gestion des adhésions")
                    
                    if pending and pending.data:
                        st.info(f"Il y a {len(pending.data)} demande(s) en attente")
                        for p in pending.data:
                            with st.container():
                                c1, c2 = st.columns([2, 1])
                                c1.markdown(f"**{p['profiles']['firstname']}** souhaite rejoindre *{p['groups']['name']}*")
                                if c2.button(texts["approve"], key=p['id'], type="primary", use_container_width=True):
                                    update_membership_status(p['id'], "approved")
                                    st.rerun()
                                st.divider()
                    else:
                        st.write("Aucune demande d'adhésion en attente.")

    with tab_leader:
        # Sélecteur de groupe pour le leaderboard
        my_approved = [g for g in m_groups.data if g['status'] == 'approved']
        if my_approved:
            selected_g = st.selectbox("Sélectionner un groupe", my_approved, format_func=lambda x: x['groups']['name'])
            res = get_leaderboard_by_group(selected_g['group_id'])
            if res.data:
                ld_df = pd.DataFrame(res.data).groupby(['firstname', 'avatar_url'])['distance_km'].sum().sort_values(ascending=False).reset_index()
                cols = st.columns(4)
                for i, row in ld_df.iterrows():
                    with cols[i % 4]:
                        st.image(row['avatar_url'], width=60)
                        st.metric(f"#{i+1} {row['firstname']}", f"{row['distance_km']:.1f} km")
        else:
            st.info(texts["no_group"])   