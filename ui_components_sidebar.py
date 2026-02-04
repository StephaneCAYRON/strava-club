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
    #st.sidebar.success(f"{texts['sidebar_connected']} {athlete.get('firstname')}")
    