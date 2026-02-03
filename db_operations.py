import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Initialisation (utilisée en interne)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
MAX_ROWS_FORSQL = 20000

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



def get_years_for_group(group_id):
    """Récupère les années distinctes pour un groupe spécifique"""
    # On ne sélectionne que la colonne start_date pour être léger
    response = supabase.table("group_years").select("year").eq("group_id", group_id).execute()
    if response.data:
        # response.data ressemble à: [{'year': 2026}, {'year': 2025}, {'year': 2017}]
        # On extrait juste la valeur numérique de la clé 'year'
        years = [row['year'] for row in response.data]
        
        # On trie du plus récent au plus ancien
        return sorted(years, reverse=True)
    return [2026]


# Option plus performante si vous avez des milliers d'activités
def get_leaderboard_by_group_by_year(group_id, year):
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    return supabase.table("group_activities")\
        .select("*")\
        .eq("group_id", group_id)\
        .eq("type", "Ride")\
        .gte("start_date", start_date)\
        .lte("start_date", end_date)\
        .limit(MAX_ROWS_FORSQL)\
        .execute()

def get_leaderboard_by_group(group_id):
    """Récupère les activités Ride pour un groupe, incluant la date pour le tri"""
    return supabase.table("group_activities")\
        .select("firstname, avatar_url, distance_km, start_date, type")\
        .eq("group_id", group_id)\
        .eq("type", "Ride")\
        .limit(MAX_ROWS_FORSQL)\
        .execute() # On filtre directement 'Ride' ici pour alléger le transfert

def get_athlete_summary(athlete_id):
    """Récupère le nombre total d'activités et les 30 plus récentes."""
    # 1. Compter le total
    # Si Supabase :
    count_res = supabase.table("activities").select("*", count="exact").eq("id_strava", athlete_id).execute()
    total_count = count_res.count if count_res else 0
    
    # 2. Récupérer les N dernières
    activities_res = supabase.table("activities") \
        .select("*") \
        .eq("id_strava", athlete_id) \
        .order("start_date", desc=True) \
        .limit(100) \
        .execute()
    return total_count, activities_res.data


# --- GESTION DES GROUPES ---

def create_group(name, admin_id):
    """Crée un nouveau groupe dont l'admin est l'utilisateur actuel"""
    data = {"name": name, "admin_id": admin_id}
    # On insère le groupe et on ajoute automatiquement l'admin comme membre approuvé
    response = supabase.table("groups").insert(data).execute()
    if response.data:
        group_id = response.data[0]['id']
        supabase.table("group_members").insert({
            "group_id": group_id,
            "athlete_id": admin_id,
            "status": "approved"
        }).execute()
    return response

def get_all_groups():
    """Récupère la liste de tous les groupes disponibles"""
    return supabase.table("groups").select("*").execute()

def get_user_memberships(athlete_id):
    """Récupère les groupes auxquels l'utilisateur appartient (approuvé ou non)"""
    return supabase.table("group_members")\
        .select("group_id, status, groups(name)")\
        .eq("athlete_id", athlete_id).execute()

def request_to_join_group(group_id, athlete_id):
    """Envoie une demande d'adhésion à un groupe"""
    data = {"group_id": group_id, "athlete_id": athlete_id, "status": "pending"}
    return supabase.table("group_members").insert(data).execute()

def get_pending_requests_for_admin(admin_id):
    """Récupère les demandes en attente pour les groupes gérés par cet admin"""
    # On cherche les groupes où l'utilisateur est admin
    admin_groups = supabase.table("groups").select("id").eq("admin_id", admin_id).execute()
    group_ids = [g['id'] for g in admin_groups.data]
    
    if not group_ids:
        return []

    return supabase.table("group_members")\
        .select("id, status, groups(name), profiles(firstname)")\
        .in_("group_id", group_ids)\
        .eq("status", "pending").execute()

def update_membership_status(membership_id, status="approved"):
    """Approuve ou refuse un membre"""
    return supabase.table("group_members").update({"status": status}).eq("id", membership_id).execute()


