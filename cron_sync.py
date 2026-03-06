import time
import sys
import os
import datetime
import traceback
import requests
from db_operations import *
from strava_operations import *
from dotenv import load_dotenv

# --- 1. CONFIGURATION DE L'ENVIRONNEMENT ---
load_dotenv()

try:
    from db_operations import supabase, sync_profile_and_activities, get_athlete_summary
    from strava_operations import fetch_page, fetch_all_activities_parallel
except ImportError as e:
    print("❌ ERREUR D'IMPORT : Assurez-vous que db_operations et strava_operations sont accessibles.")
    raise e

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

def exchange_refresh_token_local(refresh_token):
    """Échange le token sans dépendre de st.secrets."""
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        print("❌ ERREUR : STRAVA_CLIENT_ID ou SECRET manquant.")
        return None

    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            'client_id': STRAVA_CLIENT_ID,
            'client_secret': STRAVA_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        })
        if res.status_code == 200:
            return res.json()
        return None
    except Exception as e:
        print(f"⚠️ Exception réseau : {e}")
        return None

def sync_single_athlete(profile, is_partial=True):
    """
    Synchronise un seul athlète. 
    Retourne un tuple (succès_bool, message_string) pour l'affichage UI.
    """
    athlete_id = profile['id_strava']
    full_name = f"{profile.get('firstname', 'Athlète')} {profile.get('lastname', '')}".strip()
    old_refresh = profile.get('refresh_token')

    if not old_refresh:
        return False, f"⚠️ Pas de refresh token pour {full_name}."

    try:
        tokens = exchange_refresh_token_local(old_refresh)
        if not tokens or 'access_token' not in tokens:
            return False, f"⛔ Impossible de rafraîchir le token pour {full_name}."

        new_access = tokens['access_token']
        new_refresh = tokens['refresh_token']

        # Sauvegarde du nouveau token
        if new_refresh != old_refresh:
            supabase.table("profiles").update({
                "refresh_token": new_refresh,
                "last_login": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).eq("id_strava", athlete_id).execute()
        
        # Récupération des activités
        if is_partial:
            gathered_activities = fetch_page(new_access, page=1, per_page=5)
        else:
            total, recent = get_athlete_summary(athlete_id)
            gathered_activities = fetch_all_activities_parallel(new_access)
        
        print(f"⚠️DEBUG⚠️ : {full_name} - {len(gathered_activities)} activités récupérées sur Strava; force full={is_partial}")
        
        if gathered_activities:
            athlete_obj = {
                "id": athlete_id,
                "firstname": profile.get("firstname"),
                "lastname": profile.get("lastname"),
                "profile_medium": profile.get("avatar_url")
            }
            sync_profile_and_activities(athlete_obj, gathered_activities, new_refresh, is_from_ui=False, is_full_sync=not is_partial)
            return True, f"✅ {len(gathered_activities)} activités synchronisées pour {full_name}."
        else:
            return True, f"ℹ️ Aucune activité mise à jour pour {full_name}."

    except Exception as e:
        return False, f"❌ Erreur inattendue pour {full_name} : {e}"


def nightly_sync_old(yesForOnlyRecentFalseForAll):
    """Synchronisation de masse (Cron)"""
    print(f"\n[{datetime.datetime.now()}] --- 🚀 DÉBUT DE LA SYNCHRONISATION BATCH ---")
    if not supabase: return

    profiles = supabase.table("profiles").select("*").execute().data
    success_count = error_count = 0

    for profile in profiles:
        success, msg = sync_single_athlete(profile, is_partial=yesForOnlyRecentFalseForAll)
        print(msg)
        if success: success_count += 1
        else: error_count += 1

    print(f"[{datetime.datetime.now()}] --- TERMINÉ : {success_count} OK, {error_count} Erreurs ---")

import datetime

def nightly_sync(yesForOnlyRecentFalseForAll):
    
    is_partial = yesForOnlyRecentFalseForAll
    """Synchronisation de masse (Cron)"""
    print(f"\n[{datetime.datetime.now()}] --- 🚀 DÉBUT DE LA SYNCHRONISATION BATCH isPartial = {is_partial}---")
    if not supabase: return

    profiles = supabase.table("profiles").select("*").execute().data
    success_count = error_count = 0
    now = datetime.datetime.now(datetime.timezone.utc)

    for profile in profiles:
        athlete_id = profile.get('id_strava')
        full_name = f"{profile.get('firstname', '')} {profile.get('lastname', '')}"
        
        # --- LOGIQUE DE FILTRAGE POUR LA SYNCHRO COMPLÈTE ---
        
        
        if not is_partial:
            last_sync_str = profile.get('last_full_synchro')
            should_sync_full = True
            
            if last_sync_str:
                try:
                    # Conversion de la string ISO de la DB en objet datetime
                    # On utilise fromisoformat et on s'assure d'être en UTC
                    last_sync = datetime.datetime.fromisoformat(last_sync_str.replace('Z', '+00:00'))
                    if last_sync.tzinfo is None:
                        last_sync = last_sync.replace(tzinfo=datetime.timezone.utc)
                    
                    diff = now - last_sync
                    
                    # Si la dernière synchro date de moins de 2 jours
                    if diff.days < 2:
                        should_sync_full = False
                        print(f"⏳ {full_name} : Passé (Dernière Full Sync il y a {diff.days} jours)")
                except ValueError:
                    # En cas d'erreur de format, on force la synchro par sécurité
                    should_sync_full = True

            if not should_sync_full:
                continue # On passe à l'athlète suivant
            else:
                # --- EXÉCUTION DE LA SYNCHRO full car pâs fait depuis longtemps ---
                success, msg = sync_single_athlete(profile, is_partial)
                print(f"🕒 Attente de 10 minutes pour réinitialiser le quota Strava (100 req/15min)...")
                # 901 secondes pour être sûr de dépasser la fenêtre glissante de Strava
                time.sleep(600) 
        else:
            # --- EXÉCUTION DE LA SYNCHRO partielle ---
            success, msg = sync_single_athlete(profile, is_partial)
        
        print(msg)
        
        if success:
            success_count += 1
        else:
            error_count += 1

    print(f"[{datetime.datetime.now()}] --- TERMINÉ : {success_count} OK, {error_count} Erreurs ---")


if __name__ == "__main__":
    # Utilisation : python cron_sync.py full
    mode_full = "full" in sys.argv
    nightly_sync(not mode_full)