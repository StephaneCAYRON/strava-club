# APP  déployée
# Param Strava https://www.strava.com/settings/api, callback = strava-club-challenge.streamlit.app, pour 
# STRAVA_REDIRECT_URI = 'https://strava-club-challenge.streamlit.app'

# APP  locale
# Param Strava https://www.strava.com/settings/api,  callback = localhost
# STRAVA_REDIRECT_URI = 'http://localhost:8501'

import streamlit as st
import pandas as pd
from db_operations import get_athlete_summary, sync_profile_and_activities, get_leaderboard_data
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
    
    # --- AFFICHAGE DES ACTIVITÉS PERSONNELLES ---
    if 'last_activities' in st.session_state and st.session_state.last_activities:
        st.subheader(texts["last_activities"])
        df_personal = pd.DataFrame(st.session_state.last_activities)
        
        if 'distance_km' not in df_personal.columns and 'distance' in df_personal.columns:
             df_personal['distance_km'] = df_personal['distance'] / 1000

        st.bar_chart(df_personal, x="start_date", y="distance_km")
        st.dataframe(df_personal[['start_date', 'name', 'distance_km', 'type']], use_container_width=True)

    # --- AFFICHAGE DES ACTIVITÉS PERSONNELLES ---
    if 'last_activities' in st.session_state and st.session_state.last_activities:
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


# --- LEADERBOARD ---
st.divider()
st.header(texts["leaderboard"])

response = get_leaderboard_data()
if response.data:
    raw_df = pd.DataFrame(response.data)
    raw_df['Athlete'] = raw_df['profiles'].apply(lambda x: x['firstname'] if x else "???")
    raw_df['Photo'] = raw_df['profiles'].apply(lambda x: x['avatar_url'] if x else "")

    leaderboard = raw_df.groupby(['Athlete', 'Photo'])['distance_km'].sum().sort_values(ascending=False).reset_index()

    cols = st.columns(min(len(leaderboard), 4))
    for i, row in leaderboard.iterrows():
        with cols[i % 4]:
            st.image(row['Photo'], width=70)
            st.metric(label=f"#{i+1} {row['Athlete']}", value=f"{row['distance_km']:.1f} km")