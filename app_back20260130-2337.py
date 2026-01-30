import streamlit as st
import pandas as pd
from strava_operations import *
from db_operations import sync_profile_and_activities, get_leaderboard_data


# APP  déployée
# Param Strava https://www.strava.com/settings/api, callback = strava-club-challenge.streamlit.app, pour 
# STRAVA_REDIRECT_URI = 'https://strava-club-challenge.streamlit.app'

# APP  locale
# Param Strava https://www.strava.com/settings/api,  callback = localhost
# STRAVA_REDIRECT_URI = 'http://localhost:8501'


# Constantes
JAN_1_2026 = 1735689600

st.set_page_config(page_title="Club Amicale Cyclo Escalquens 2026", page_icon="🚴", layout="wide")

# --- SESSION STATE ---
for key in ['access_token', 'refresh_token', 'athlete']:
    if key not in st.session_state:
        st.session_state[key] = None

# --- AUTH LOGIC ---
if "code" in st.query_params and st.session_state.access_token is None:
    data = exchange_code_for_token(st.query_params["code"])
    if data:
        st.session_state.access_token = data['access_token']
        st.session_state.refresh_token = data['refresh_token']
        st.session_state.athlete = data['athlete']

        # DEBUG
        print(st.session_state.access_token)

        st.query_params.clear()
        st.rerun()

# --- UI ---
st.title("🚴 Challenge Amicale Cyclo Escalquens")

if st.session_state.access_token is None:
    st.link_button("Se connecter avec Strava", get_strava_auth_url())
else:
    athlete = st.session_state.athlete
    st.sidebar.image(athlete.get("profile_medium"), width=100)
    st.sidebar.success(f"Connecté : {athlete.get('firstname')}")
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.access_token = None
        st.rerun()

    # 1. Synchronisation
    if st.button("🔄 Synchroniser mes activités 2026"):
        with st.spinner("Récupération Strava..."):
            activities = fetch_strava_activities(st.session_state.access_token, JAN_1_2026)
            if activities:
                # On stocke dans la session pour l'affichage graphique
                # DEBUG DEBUG 
                st.write(f"DEBUG: Première activité trouvée le {activities[-1]['start_date']}")
                # DEBUG DEBUG 
                st.session_state.last_activities = activities 
                if sync_profile_and_activities(athlete, activities, st.session_state.refresh_token):
                    st.success(f"{len(activities)} activités envoyées à la base !")
            else:
                st.warning("Aucune nouvelle activité trouvée depuis le 01/01/2026.")

        # 2. Affichage du graphique personnel (si des données ont été chargées)
        if 'last_activities' in st.session_state and st.session_state.last_activities:
            st.subheader("📊 Mes dernières sorties (2026)")
            df_personal = pd.DataFrame(st.session_state.last_activities)
            
            # Petit nettoyage pour le graphique
            df_personal['distance_km'] = df_personal['distance'] / 1000
            
            # Affichage du graphique
            st.bar_chart(df_personal, x="start_date", y="distance_km")
            
            # Affichage du tableau détaillé
            st.dataframe(df_personal[['start_date', 'name', 'distance_km', 'type']], use_container_width=True)
   
    
    st.sidebar.divider()
    st.sidebar.subheader("Zone Administration")

    if st.sidebar.button("🚀 Récupérer tout l'historique Strava"):
        with st.spinner("Récupération de toutes les activités (parallèle)..."):
            # 1. Récupération rapide via threads
            all_activities = fetch_all_activities_parallel(st.session_state.access_token)
            
            if all_activities:
                st.info(f"{len(all_activities)} activités récupérées. Synchronisation avec la base de données...")
                
                # 2. Stockage en base (on ne traite pas l'affichage ici comme demandé)
                success = sync_profile_and_activities(
                    st.session_state.athlete, 
                    all_activities, 
                    st.session_state.refresh_token
                )
                
                if success:
                    st.success("Historique complet synchronisé avec succès !")
                else:
                    st.error("Erreur lors de l'enregistrement en base de données.")
            else:
                st.warning("Aucune activité trouvée sur ce compte.")
# --- LEADERBOARD ---
st.divider()
st.header("🏆 Classement général")

response = get_leaderboard_data()
if response.data:
    raw_df = pd.DataFrame(response.data)
    # Aplatissage des données profils
    raw_df['Athlete'] = raw_df['profiles'].apply(lambda x: x['firstname'] if x else "Inconnu")
    raw_df['Photo'] = raw_df['profiles'].apply(lambda x: x['avatar_url'] if x else "")

    leaderboard = raw_df.groupby(['Athlete', 'Photo'])['distance_km'].sum().sort_values(ascending=False).reset_index()

    # Affichage des colonnes
    cols = st.columns(min(len(leaderboard), 4))
    for i, row in leaderboard.iterrows():
        with cols[i % 4]:
            st.image(row['Photo'], width=70)
            st.metric(label=f"#{i+1} {row['Athlete']}", value=f"{row['distance_km']:.1f} km")
else:
    st.info("En attente de la première synchronisation...")