import streamlit as st
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
    
    
    st.sidebar.image("https://developers.strava.com/images/api_logo_pwrdBy_strava_horiz_light.png", width=150)

    athlete = st.session_state.athlete
    st.sidebar.image(get_safe_avatar_url(athlete.get("profile")), width=100)
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