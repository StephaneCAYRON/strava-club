# APP  déployée
# Param Strava https://www.strava.com/settings/api, callback = strava-club-challenge.streamlit.app, pour 
# STRAVA_REDIRECT_URI = 'https://strava-club-challenge.streamlit.app'

# APP  locale
# Param Strava https://www.strava.com/settings/api,  callback = localhost
# STRAVA_REDIRECT_URI = 'http://localhost:8501'

import streamlit as st

st.set_page_config(page_title="Amicale Cyclo Escalquens", page_icon="images/LogoACETransparent.png", layout="centered")

from db_operations import *
from strava_operations import *
from translation import lang_dict
from ui_components_sidebar import sidebar_component
from ui_components import render_tab_stats
from ui_components_tab_sunday import render_tab_sunday
from ui_components_tab_km import render_tab_km
from ui_components_tab_groups import render_tab_groups
from ui_components_tab_admin import render_tab_admin

# --- CONFIGURATION ---
st.image("images/LogoACETransparent.png")
st.info(
    "Version béta -> Voir groupe WhatsApp dédié pour déclarer les bugs."
    "A venir (si faisable) : **revival** du challenge Segments ! "
    "🔗 [Consulter les archives 2017](http://www.cycloescalquens.fr/ChallengeStrava2017a.htm)"
)


# --- INITIALISATION ---
for key in ['access_token', 'refresh_token', 'athlete', 'lang', 'auto_sync_done']:
    if key not in st.session_state:
        st.session_state[key] = "fr" if key == 'lang' else (False if key == 'auto_sync_done' else None)

texts = lang_dict[st.session_state.lang]


# --- FONCTION DE MISE À JOUR UI ---
def refresh_local_data():
    if st.session_state.athlete:
        athlete_id = st.session_state.athlete.get('id')
        total, recent = get_athlete_summary(athlete_id)
        st.session_state.total_activities = total
        st.session_state.last_activities = recent

# --- AUTH ET SYNC ---
if "code" in st.query_params and st.session_state.access_token is None:
    data = exchange_code_for_token(st.query_params["code"])
    if data:
        st.session_state.access_token, st.session_state.refresh_token, st.session_state.athlete = data['access_token'], data['refresh_token'], data['athlete']
        st.query_params.clear(); st.rerun()

if st.session_state.access_token:
    # Sidebar et Stats
    sidebar_component(texts)

    athlete = st.session_state.athlete
    
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

    # Affichage des Onglets
    ADMIN_ID = 5251772
    tabs_names = [texts["tab_statsPerso"], texts["tab_sunday"],texts["leaderboard_tab"], texts["group_tab"]]
    
    # Si c'est l'admin, on ajoute l'onglet
    if st.session_state.athlete['id'] == ADMIN_ID:
        tabs_names.append("🛠️ Admin")
    #t_stats, t_sunday, t_leader, t_groups, t_admin = st.tabs(tabs_names)
    tabs = st.tabs(tabs_names)

    with tabs[0]: render_tab_stats(texts)
    with tabs[1]: render_tab_sunday(texts)
    with tabs[2]: render_tab_km(texts)
    with tabs[3]: render_tab_groups(texts)
    if st.session_state.athlete['id'] == ADMIN_ID: # Ton ID
          with tabs[4]: render_tab_admin(texts)
else:
    # On crée 3 colonnes : [Marge gauche, Bouton, Marge droite]
    # Le ratio [1, 2, 1] signifie que le bouton occupe 50% de la largeur centrale
    left_co, cent_co, last_co = st.columns([1, 2, 1])

    with cent_co:
        st.link_button(texts["connect"], get_strava_auth_url(),use_container_width=True, type="primary")
    

st.markdown("---")
col1, col2, col3 = st.columns([3, 2, 3])
with col2:
    st.image("https://developers.strava.com/images/api_logo_pwrdBy_strava_horiz_light.png", width=150)