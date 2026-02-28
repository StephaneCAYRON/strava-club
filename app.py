# APP  déployée
# Param Strava https://www.strava.com/settings/api, callback = strava-club-challenge.streamlit.app, pour 
# STRAVA_REDIRECT_URI = 'https://strava-club-challenge.streamlit.app'

# APP  locale
# Param Strava https://www.strava.com/settings/api,  callback = localhost
# STRAVA_REDIRECT_URI = 'http://localhost:8501'

import streamlit as st
import threading

#st.set_page_config(page_title="Amicale Cyclo Escalquens", page_icon="images/LogoACETransparent.png", layout="centered")
st.set_page_config(page_title="Amicale Cyclo Escalquens", page_icon="images/LogoACETransparent.png", layout="wide")

from db_operations import *
from strava_operations import *
from translation import lang_dict
from ui_components_sidebar import sidebar_component
from ui_components import render_tab_stats
from ui_components_tab_sunday import render_tab_sunday
#deprecated from ui_components_tab_km import render_tab_km
#deprecated from ui_components_tab_elevation import render_tab_dplus
from ui_components_tab_groups import render_tab_groups
from ui_components_tab_admin import render_tab_admin
from ui_components_tab_regularity import render_tab_regularity
from ui_components_tab_group_page import render_tab_group_page
from ui_components_tab_leaderboard import render_tab_leaderboard

ADMIN_ID = 5251772

# --- CONFIGURATION ---
col_header1, col_header2, col_header3 = st.columns([1, 2, 1])
with col_header2:
    st.image("images/LogoACETransparent.png", width=400)
st.info("Voir groupe WhatsApp dédié [🔗ici](https://chat.whatsapp.com/JRpGyeubaI89ulRTu21TYE) pour déclarer les bugs, proposer des idées, etc."
)


# --- INITIALISATION ---
for key in ['access_token', 'refresh_token', 'athlete', 'lang', 'auto_sync_done', 'sync_started']:
    if key not in st.session_state:
        st.session_state[key] = "fr" if key == 'lang' else (False if key in ('auto_sync_done', 'sync_started') else None)

texts = lang_dict[st.session_state.lang]

def redirect_button(url, text):
    st.markdown(
        f"""
        <a href="{url}" target="_self">
            <button style="
                width: 100%;
                background-color: #ff4b4b;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                ">
                {text}
            </button>
        </a>
        """,
        unsafe_allow_html=True
    )

# Statut de la sync en arrière-plan (lu par le thread principal, écrit par le thread de sync)
_sync_status = {"done": False, "error": None}

def _run_sync_background(athlete, access_token, refresh_token):
    """Exécute la synchronisation en arrière-plan. Ne touche pas à session_state."""
    try:
        latest_activities = fetch_page(access_token, page=1, per_page=10)
        if latest_activities:
            sync_profile_and_activities(athlete, latest_activities, refresh_token)
        athlete_id = athlete.get("id")
        total_db, _ = get_athlete_summary(athlete_id)
        if total_db <= 100:
            all_history = fetch_all_activities_parallel(access_token, max_pages=100)
            if all_history:
                sync_profile_and_activities(athlete, all_history, refresh_token)
        
    except Exception as e:
        _sync_status["error"] = str(e)
    finally:
        _sync_status["done"] = True
        

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
    if st.session_state.get("sync_error"):
        st.error("Synchronisation en arrière-plan : " + st.session_state.pop("sync_error", ""))
    # Sidebar et Stats
    sidebar_component(texts)

    athlete = st.session_state.athlete
    refresh_local_data()
    # --- SYNCHRONISATION EN ARRIÈRE-PLAN (invisible, non bloquante) ---
    if not st.session_state.auto_sync_done:
        if not st.session_state.sync_started:
            _sync_status["done"] = False
            _sync_status["error"] = None
            t = threading.Thread(
                target=_run_sync_background,
                args=(athlete, st.session_state.access_token, st.session_state.refresh_token),
                daemon=True,
            )
            t.start()
            st.session_state.sync_started = True

        # Fragment qui vérifie toutes les 2 s si la sync est terminée, puis refresh
        @st.fragment(run_every=2)
        def _poll_sync_done():
            if _sync_status["done"]:
                
                st.session_state.auto_sync_done = True
                st.session_state.sync_started = False
                if _sync_status.get("error"):
                    st.session_state["sync_error"] = _sync_status["error"]
                st.rerun()

        _poll_sync_done()

    # Affichage des Onglets
    tabs_names = [texts["tab_statsPerso"], texts["tab_sunday"],texts["leaderboard_tab"], texts["group_tab"]]
    
    # Rendu de la Sidebar avec Radio ou Selectbox
    # On définit les options du menu
    # On utilise un dictionnaire pour mapper les noms du menu aux fonctions de rendu
    # On récupère les adhésions de l'utilisateur (déjà existant dans votre db_operations)
    user_groups_res = get_user_memberships(athlete['id'])
    has_groups = len(user_groups_res.data) > 0

    # Définition de la page par défaut
    if not has_groups:
        default_page = "👥 Mes Groupes"
        pages = {
            texts["group_tab"]: render_tab_groups,
            texts["tab_sunday"]: render_tab_sunday,
            texts["tab_regularity"]: render_tab_regularity,
            texts["leaderboard_tab"]: render_tab_leaderboard,
            #texts["dplus_tab"]: render_tab_dplus,
            #texts["leaderboard_tab"]: render_tab_km,
            texts["tab_statsPerso"]: render_tab_stats,
        }
    else:
        pages = {
            texts["tab_sunday"]: render_tab_sunday,
            texts["tab_regularity"]: render_tab_regularity,
            texts["leaderboard_tab"]: render_tab_leaderboard,
            #texts["dplus_tab"]: render_tab_dplus,
            #texts["leaderboard_tab"]: render_tab_km,
            texts["tab_statsPerso"]: render_tab_stats,
            texts["group_tab"]: render_tab_groups
        }


    #approved = [g for g in user_groups_res.data if g["status"] == "approved"]
    #for g in sorted(approved, key=lambda x: x["groups"]["name"]):
    #    group_name = f"📊 Stats {g["groups"]["name"]}"
    #    pages[group_name] = (lambda texts, grp=g: render_tab_group_page(texts, grp))
    #
    if st.session_state.athlete['id'] == ADMIN_ID: # Ton ID
        pages["🛠️ Console Admin"] = render_tab_admin

    with st.sidebar:
        st.divider()
        selection = st.radio("", list(pages.keys()))
        st.divider()
        
        if st.button("🔓 Déconnexion", use_container_width=True):
            st.session_state.access_token = None
            st.session_state.auto_sync_done = False
            st.session_state.sync_started = False
            st.rerun()

        if st.button(texts["sync_btn"], use_container_width=True):
            with st.spinner(texts["sync_spinner"]):
                all_activities = fetch_all_activities_parallel(st.session_state.access_token)
                if all_activities:
                    sync_profile_and_activities(athlete, all_activities, st.session_state.refresh_token)
                    st.session_state.pop("leaderboard_cache", None)
                    st.sidebar.success(texts["sync_success"])
                    st.rerun()

    # APPEL DE LA FONCTION DE RENDU SELON LA SÉLECTION
    render_func = pages[selection]
    render_func(texts)  

else:
    # On crée 3 colonnes : [Marge gauche, Bouton, Marge droite]
    # Le ratio [1, 2, 1] signifie que le bouton occupe 50% de la largeur centrale
    left_co, cent_co, last_co = st.columns([1, 2, 1])

    with cent_co:
        st.link_button(texts["connect"], get_strava_auth_url(),use_container_width=True, type="primary")
        #redirect_button(get_strava_auth_url(), texts["connect"])
        
    

st.markdown("---")
col1, col2, col3 = st.columns([3, 2, 3])
with col2:
    st.image("https://developers.strava.com/images/api_logo_pwrdBy_strava_horiz_light.png", width=150)



