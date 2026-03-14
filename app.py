import streamlit as st
import threading
import streamlit.components.v1 as components
from db_operations import *
from strava_operations import *
from translation import lang_dict
from ui_components_sidebar import sidebar_component
import importlib

def _lazy(module, func):
    """Import le module seulement quand la page est effectivement rendue."""
    def _render(texts):
        return getattr(importlib.import_module(module), func)(texts)
    return _render

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

ADMIN_ID = 5251772
VERSION = "v20260314.1605"

st.set_page_config(
    page_title="Amicale Cyclo Escalquens",
    page_icon="images/LogoACETransparent.png",
    layout="wide",
)

# ---------------------------------------------------
# HEADER -> none pour libérer place
# ---------------------------------------------------

# ---------------------------------------------------
# SESSION INIT
# ---------------------------------------------------
DEFAULT_SESSION = {
    "access_token": None,
    "refresh_token": None,
    "athlete": None,
    "lang": "fr",
    "auto_sync_done": False,
    "sync_started": False,
    "sync_error": None,
}
for k,v in DEFAULT_SESSION.items():
    if k not in st.session_state:
        st.session_state[k] = v
texts = lang_dict[st.session_state.lang]

# ---------------------------------------------------
# OAUTH CALLBACK
# ---------------------------------------------------

params = st.query_params
code = params.get("code")
if code and st.session_state.access_token is None:
    data = exchange_code_for_token(code)
    if data:
        st.session_state.access_token = data["access_token"]
        st.session_state.refresh_token = data["refresh_token"]
        st.session_state.athlete = data["athlete"]
        st.query_params.clear()
        st.rerun()

# ---------------------------------------------------
# LOGIN PAGE
# ---------------------------------------------------

def login_page_button():
    left, center, right = st.columns([1,2,1])
    with center:
        st.link_button(
            texts["connect"],
            get_strava_auth_url(),
            use_container_width=True,
            type="primary"
        )
    st.stop()

if not st.session_state.access_token:
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        st.image("images/LogoACETransparent.png", use_container_width=True)
        st.write(f"Version {VERSION}")
        login_page_button()

# ---------------------------------------------------
# LOCAL DATA REFRESH
# ---------------------------------------------------

def refresh_local_data():
    athlete = st.session_state.athlete
    if not athlete:
        return
    athlete_id = athlete["id"]
    total, recent = get_athlete_summary(athlete_id)
    st.session_state.total_activities = total
    st.session_state.last_activities = recent

# ---------------------------------------------------
# BACKGROUND SYNC
# ---------------------------------------------------

sync_status = {"done": False, "error": None}
def run_sync_background(athlete, access_token, refresh_token):
    try:
        latest = fetch_page(access_token, page=1, per_page=10)
        sync_profile_and_activities(
            athlete,
            latest,
            refresh_token,
            is_from_ui=True
        )

        athlete_id = athlete["id"]
        total_db, _ = get_athlete_summary(athlete_id)
        if total_db <= 100:
            history = fetch_all_activities_parallel(
                access_token,
                max_pages=100
            )
            if history:
                sync_profile_and_activities(
                    athlete,
                    history,
                    refresh_token,
                    is_from_ui=True
                )

    except Exception as e:
        sync_status["error"] = str(e)
    finally:
        sync_status["done"] = True

# ---------------------------------------------------
# START BACKGROUND SYNC
# ---------------------------------------------------

if not st.session_state.auto_sync_done:
    if not st.session_state.sync_started:
        sync_status["done"] = False
        sync_status["error"] = None
        t = threading.Thread(
            target=run_sync_background,
            args=(
                st.session_state.athlete,
                st.session_state.access_token,
                st.session_state.refresh_token
            ),
            daemon=True
        )

        t.start()
        st.session_state.sync_started = True

    @st.fragment(run_every=2)
    def check_sync():
        if sync_status["done"]:
            st.session_state.auto_sync_done = True
            st.session_state.sync_started = False
            if sync_status["error"]:
                st.session_state.sync_error = sync_status["error"]
            st.rerun()

    check_sync()

# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------

sidebar_component(texts)
if st.session_state.sync_error:
    st.error("Erreur sync : " + st.session_state.sync_error)
    st.session_state.sync_error = None
athlete = st.session_state.athlete
refresh_local_data()

# ---------------------------------------------------
# MENU PAGES
# ---------------------------------------------------

user_groups_res = get_user_memberships(athlete["id"])
has_groups = len(user_groups_res.data) > 0

# Définition de la page par défaut
if not has_groups:
    default_page = "👥 Mes Groupes"
    pages = {
        texts["group_tab"]: _lazy("ui_components_tab_groups", "render_tab_groups"),
        texts["tab_sunday"]: _lazy("ui_components_tab_sunday", "render_tab_sunday"),
        texts["tab_regularity"]: _lazy("ui_components_tab_regularity", "render_tab_regularity"),
        texts["leaderboard_tab"]: _lazy("ui_components_tab_leaderboard", "render_tab_leaderboard"),
        "🗺️ Carte Club": _lazy("ui_components_tab_heatmap", "render_tab_heatmap"),
        #texts["dplus_tab"]: render_tab_dplus,
        #texts["leaderboard_tab"]: render_tab_km,
        #texts["tab_statsPerso"]: render_tab_stats,
        "📈 Stats perso": _lazy("ui_components_tab_advanced_stats", "render_tab_advanced_stats"),
        "📍 Carte perso": _lazy("ui_components_tab_personal_map", "render_tab_personal_map"),
        "🧬 Ma Bio Sportive": _lazy("ui_components_tab_bio", "render_tab_bio"),
    }
else:
    pages = {
        texts["tab_sunday"]: _lazy("ui_components_tab_sunday", "render_tab_sunday"),
        texts["tab_regularity"]: _lazy("ui_components_tab_regularity", "render_tab_regularity"),
        texts["leaderboard_tab"]: _lazy("ui_components_tab_leaderboard", "render_tab_leaderboard"),
        "🗺️ Carte Club": _lazy("ui_components_tab_heatmap", "render_tab_heatmap"),
        #texts["dplus_tab"]: render_tab_dplus,
        #texts["leaderboard_tab"]: render_tab_km,
        #texts["tab_statsPerso"]: render_tab_stats,
        "📈 Stats perso": _lazy("ui_components_tab_advanced_stats", "render_tab_advanced_stats"),
        "📍 Carte perso": _lazy("ui_components_tab_personal_map", "render_tab_personal_map"),
        "🧬 Ma Bio Sportive": _lazy("ui_components_tab_bio", "render_tab_bio"),
        texts["group_tab"]: _lazy("ui_components_tab_groups", "render_tab_groups"),
    }

#approved = [g for g in user_groups_res.data if g["status"] == "approved"]
#for g in sorted(approved, key=lambda x: x["groups"]["name"]):
#    group_name = f"📊 Stats {g["groups"]["name"]}"
#    pages[group_name] = (lambda texts, grp=g: render_tab_group_page(texts, grp))
#
if st.session_state.athlete['id'] == ADMIN_ID: # Ton ID
    pages["🛠️ Console Admin"] = _lazy("ui_components_tab_admin", "render_tab_admin")


# ---------------------------------------------------
# SIDEBAR NAV
# ---------------------------------------------------

with st.sidebar:
    st.divider()
    selection = st.radio("", list(pages.keys()))
    st.divider()
    if st.button("🔓 Déconnexion", use_container_width=True):
        for k in DEFAULT_SESSION:
            st.session_state[k] = DEFAULT_SESSION[k]
        st.rerun()

    if st.button(texts["sync_btn"], use_container_width=True):
        with st.spinner(texts["sync_spinner"]):
            all_activities = fetch_all_activities_parallel(
                st.session_state.access_token
            )
            if all_activities:
                success = sync_profile_and_activities(
                    athlete,
                    all_activities,
                    st.session_state.refresh_token
                )
                if success:
                    st.session_state.pop("leaderboard_cache", None)
                    get_athlete_summary.clear()
                    get_user_memberships.clear()
                    st.sidebar.success(texts["sync_success"])
                    st.rerun() # Ne s'exécute QUE si success est True
                else:
                    # Si success est False, le code s'arrête ici.
                    # L'erreur affichée par st.error() dans db_operations restera visible.
                    st.warning("La synchronisation a échoué. Vérifiez les messages d'erreur ci-dessus.")
    st.divider()
    st.info("Groupe WhatsApp [🔗ici](https://chat.whatsapp.com/JRpGyeubaI89ulRTu21TYE) pour déclarer les bugs ou proposer des idées.")
    st.divider()
    st.write(f"Version {VERSION}")

# ---------------------------------------------------
# PAGE RENDER
# ---------------------------------------------------

render_func = pages[selection]
render_func(texts)

# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------

st.markdown("---")
c1,c2,c3 = st.columns([3,2,3])
with c2:
    st.image(
        "https://developers.strava.com/images/api_logo_pwrdBy_strava_horiz_light.png",
        width=150
    )
