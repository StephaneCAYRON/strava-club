import streamlit as st
import requests
import pandas as pd
import time

from supabase import create_client, Client

# Timestamp pour le 1er janvier 2026
JAN_1_2026 = 1735689600


# --- CONFIGURATION (Remplace par tes clés Strava) ---
STRAVA_CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
STRAVA_CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
STRAVA_REDIRECT_URI = st.secrets["STRAVA_REDIRECT_URI"]

# Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialisation Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Club Strava", page_icon="🚴", layout="wide")

# --- 2. GESTION DE LA SESSION ---
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'refresh_token' not in st.session_state:
    st.session_state.refresh_token = None
if 'athlete' not in st.session_state:
    st.session_state.athlete = None

# --- 3. FONCTIONS ---

def get_strava_auth_url():
    return (f"https://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}"
            f"&response_type=code&redirect_uri={STRAVA_REDIRECT_URI}"
            f"&approval_prompt=force&scope=activity:read_all")

def exchange_code(code):
    res = requests.post("https://www.strava.com/oauth/token", data={
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    })
    return res.json() if res.status_code == 200 else None

def sync_to_supabase(athlete, activities, refresh_token):
    try:
        # Sauvegarde Profil
        profile_data = {
            "id_strava": athlete["id"],
            "firstname": athlete.get("firstname"),
            "lastname": athlete.get("lastname"),
            "refresh_token": refresh_token,
            "avatar_url": athlete.get("profile_medium")
        }
        supabase.table("profiles").upsert(profile_data).execute()

        # Sauvegarde Activités
        if activities:
            formatted_activities = []
            for a in activities:
                formatted_activities.append({
                    "id_activity": a["id"],
                    "id_strava": athlete["id"],
                    "name": a["name"],
                    "distance_km": a["distance"] / 1000,
                    "type": a["type"],
                    "start_date": a["start_date"]
                })
            supabase.table("activities").upsert(formatted_activities).execute()
        return True
    except Exception as e:
        st.error(f"Erreur de synchronisation : {e}")
        return False

# --- 4. LOGIQUE D'AUTHENTIFICATION ---
query_params = st.query_params
if "code" in query_params and st.session_state.access_token is None:
    data = exchange_code(query_params["code"])
    if data:
        st.session_state.access_token = data['access_token']
        st.session_state.refresh_token = data['refresh_token']
        st.session_state.athlete = data['athlete']
        st.query_params.clear()
        st.rerun()

# --- 5. INTERFACE UTILISATEUR ---
st.title("🚴 Dashboard Strava & Supabase")

if st.session_state.access_token is None:
    st.info("Connectez-vous pour synchroniser vos données.")
    st.link_button("Se connecter avec Strava", get_strava_auth_url())
else:
    athlete = st.session_state.athlete
    st.sidebar.image(athlete.get("profile_medium"), width=100)
    st.sidebar.write(f"Salut, {athlete.get('firstname')} !")
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.access_token = None
        st.rerun()

    # Récupération des données ------------------- -----------------
    headers = {'Authorization': f"Bearer {st.session_state.access_token}"}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    
    if res.status_code == 200:
        activities = res.json()
        df = pd.DataFrame(activities)
        
        # Bouton de synchronisation
        if st.button("🔄 Synchroniser avec la base de données"):
            with st.spinner("Envoi vers Supabase..."):
                if sync_to_supabase(athlete, activities, st.session_state.refresh_token):
                    st.success("Données enregistrées !")

        # Affichage Local
        if not df.empty:
            df['distance_km'] = df['distance'] / 1000
            st.subheader("Tes dernières sorties")
            st.bar_chart(df, x="start_date", y="distance_km")
            st.dataframe(df[['start_date', 'name', 'distance_km', 'type']], use_container_width=True)
    else:
        st.error("Impossible de récupérer les activités.")

# --- 6. LEADERBOARD (BONUS) ---
st.divider()
st.header("🏆 Classement du Club")

# 1. Récupération des données avec jointure
# On demande les km de la table activités + le prénom de la table profils liée
response = supabase.table("activities").select("distance_km, profiles(firstname, avatar_url)").execute()

if response.data:
    # 2. Transformation en DataFrame
    raw_df = pd.DataFrame(response.data)
    
    # 3. "Aplatir" les données du profil (qui arrivent sous forme de dictionnaire)
    raw_df['Athlete'] = raw_df['profiles'].apply(lambda x: x['firstname'] if x else "Inconnu")
    raw_df['Photo'] = raw_df['profiles'].apply(lambda x: x['avatar_url'] if x else "")

    # 4. Calcul du classement (Somme des km par athlète)
    leaderboard = raw_df.groupby(['Athlete', 'Photo'])['distance_km'].sum().sort_values(ascending=False).reset_index()

    # 5. Affichage stylisé
    cols = st.columns(len(leaderboard) if len(leaderboard) < 4 else 4)
    
    for i, row in leaderboard.iterrows():
        with cols[i % 4]:
            st.image(row['Photo'], width=80)
            st.metric(label=f"#{i+1} {row['Athlete']}", value=f"{row['distance_km']:.1f} km")

    # 6. Tableau récapitulatif
    st.subheader("Détails des performances")
    st.table(leaderboard[['Athlete', 'distance_km']].rename(columns={'distance_km': 'Distance Totale (km)'}))

else:

    st.info("Le classement est vide pour le moment. Synchronisez vos données !")