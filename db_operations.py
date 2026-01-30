import streamlit as st
from supabase import create_client, Client

# Initialisation (utilisée en interne)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def sync_profile_and_activities(athlete, activities, refresh_token):
    """Sauvegarde le profil et les activités dans Supabase."""
    try:
        # 1. Sauvegarde Profil
        profile_data = {
            "id_strava": athlete["id"],
            "firstname": athlete.get("firstname"),
            "lastname": athlete.get("lastname"),
            "refresh_token": refresh_token,
            "avatar_url": athlete.get("profile_medium")
        }
        supabase.table("profiles").upsert(profile_data).execute()

        # 2. Sauvegarde Activités
        if activities:
            formatted_activities = [{
                "id_activity": a["id"],
                "id_strava": athlete["id"],
                "name": a["name"],
                "distance_km": a["distance"] / 1000,
                "type": a["type"],
                "start_date": a["start_date"]
            } for a in activities]
            
            supabase.table("activities").upsert(formatted_activities).execute()
        return True
    except Exception as e:
        st.error(f"Erreur Supabase : {e}")
        return False

def get_leaderboard_data():
    """Récupère les données consolidées pour le classement."""
    return supabase.table("activities").select("distance_km, type, start_date, profiles(firstname, avatar_url)").execute()

def get_athlete_summary(athlete_id):
    """Récupère le nombre total d'activités et les 30 plus récentes."""
    # 1. Compter le total
    # Si Supabase :
    count_res = supabase.table("activities").select("*", count="exact").eq("id_strava", athlete_id).execute()
    total_count = count_res.count if count_res else 0
    
    # 2. Récupérer les 30 dernières
    activities_res = supabase.table("activities") \
        .select("*") \
        .eq("id_strava", athlete_id) \
        .order("start_date", desc=True) \
        .limit(30) \
        .execute()
    return total_count, activities_res.data


