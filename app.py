import streamlit as st
import pandas as pd
from db_operations import get_athlete_summary, sync_profile_and_activities, get_leaderboard_data
from strava_operations import *


# APP  déployée
# Param Strava https://www.strava.com/settings/api, callback = strava-club-challenge.streamlit.app, pour 
# STRAVA_REDIRECT_URI = 'https://strava-club-challenge.streamlit.app'

# APP  locale
# Param Strava https://www.strava.com/settings/api,  callback = localhost
# STRAVA_REDIRECT_URI = 'http://localhost:8501'


# Constantes
JAN_1_2026 = 1735689600

# --- FONCTION DE MISE À JOUR UI DEPUIS LA DB ---
def refresh_local_data():
    if st.session_state.athlete:
        athlete_id = st.session_state.athlete.get('id')
        total, recent = get_athlete_summary(athlete_id)
        st.session_state.total_activities = total
        st.session_state.last_activities = recent

st.set_page_config(page_title="Club Amicale Cyclo Escalquens 2026", page_icon="🚴", layout="wide")

# --- SESSION STATE ---
for key in ['access_token', 'refresh_token', 'athlete']:
    if key not in st.session_state:
        st.session_state[key] = None

# --- AUTH LOGIC (MODIFIÉE) ---
if "code" in st.query_params and st.session_state.access_token is None:
    data = exchange_code_for_token(st.query_params["code"])
    if data:
        st.session_state.access_token = data['access_token']
        st.session_state.refresh_token = data['refresh_token']
        st.session_state.athlete = data['athlete']
        # CHARGEMENT INITIAL DEPUIS LA DB
        refresh_local_data() 
        st.query_params.clear()
        st.rerun()

# --- SESSION STATE ---
# On ajoute 'auto_sync_done' à la liste des clés à surveiller ou on l'initialise séparément
if 'auto_sync_done' not in st.session_state:
    st.session_state.auto_sync_done = False

# --- UI ---
st.title("🚴 Challenge Amicale Cyclo Escalquens")

if st.session_state.access_token is None:
    st.link_button("Se connecter avec Strava", get_strava_auth_url())
else:
    # possible to disconnect
    if st.sidebar.button("Déconnexion"):
        st.session_state.access_token = None
        st.rerun()

    athlete = st.session_state.athlete
    st.sidebar.image(athlete.get("profile_medium"), width=100)
    st.sidebar.success(f"Connecté : {athlete.get('firstname')}")
    
    # Affichage du compteur (Information issue de la base)
    total_db = st.session_state.get('total_activities', 0)
    st.sidebar.metric("Activités en base", total_db)

    st.sidebar.divider()
    st.sidebar.write("Stats Strava")
        # APPEL ET AFFICHAGE DES STATS OFFICIELLES STRAVA
    # On récupère les deux valeurs d'un coup dans deux variables distinctes
    result = get_strava_stats(st.session_state.access_token, athlete.get('id'))

    # On vérifie si on a bien reçu un tuple de 2 éléments avant de déballer
    if isinstance(result, tuple) and len(result) == 2:
        stats_string, total_val = result
    else:
        stats_string, total_val = "Données corrompues", 0

    # Affichage
    st.sidebar.info(stats_string)
    st.sidebar.write(f"{total_val} (🚲+🏃+🏊), {total_db-total_val} (others)")

    if not st.session_state.auto_sync_done:
        st.info(f"🔄 Mise à jour automatique...")
        with st.spinner("Synchronisation en arrière-plan..."):
            # On utilise ta fonction parallèle existante
            all_activities = fetch_all_activities_parallel(st.session_state.access_token, max_pages=3)
            
            if all_activities:
                success = sync_profile_and_activities(athlete, all_activities, st.session_state.refresh_token)
                if success:
                    # C'est ICI qu'on active le verrou pour empêcher la boucle au prochain rerun
                    st.session_state.auto_sync_done = True
                    # On rafraîchit les données locales pour mettre à jour le compteur et le graphique
                    refresh_local_data()
                    st.toast("✅ Données synchronisées avec succès !")
                    st.rerun()

    # BOUTON SYNCHRO (MODIFIÉ)
    if st.sidebar.button("🚀 Forcer synchronisation (Strava -> Base)"):
        with st.spinner("Synchronisation massive en cours..."):
            all_activities = fetch_all_activities_parallel(st.session_state.access_token)
            if all_activities:
                sync_profile_and_activities(athlete, all_activities, st.session_state.refresh_token)
                # MISE À JOUR APRÈS SYNCHRO
                refresh_local_data()
                st.success("Base de données mise à jour !")
                st.rerun()
    # --- AFFICHAGE (30 DERNIÈRES DE LA BASE) ---
    if 'last_activities' in st.session_state and st.session_state.last_activities:
        st.subheader(f"📊 Vos 30 dernières activités (sur {total_db} au total)")
        
        df_personal = pd.DataFrame(st.session_state.last_activities)
        
        # Nettoyage si les colonnes ne sont pas déjà en km dans ta base
        if 'distance' in df_personal.columns:
             # Si ta DB stocke en mètres comme Strava
             df_personal['distance_km'] = df_personal['distance'] / 1000
        else:
             # Si ta DB stocke déjà en km (via sync_profile_and_activities)
             df_personal['distance_km'] = df_personal['distance_km']

        # Graphique et Tableau
        st.bar_chart(df_personal, x="start_date", y="distance_km")
        st.dataframe(df_personal[['start_date', 'name', 'distance_km', 'type']], use_container_width=True)

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


