import os
import time
import datetime
from dateutil import parser # Utile pour parser les dates de la DB
from dotenv import load_dotenv
from db_operations import supabase, sync_profile_and_activities
from strava_operations import fetch_all_activities_parallel, exchange_refresh_token

# --- 1. CONFIGURATION ---
load_dotenv()

def run_migration():
    print(f"🚀 [{datetime.datetime.now()}] DÉMARRAGE DE LA MIGRATION HISTORIQUE")
    print("Objectif : Récupérer 'moving_time' pour toutes les activités en base.\n")

    # A. Récupérer tous les profils qui ont un refresh_token
    profiles_res = supabase.table("profiles").select("id_strava, firstname, lastname, refresh_token, avatar_url,last_full_synchro").execute()
    
    if not profiles_res.data:
        print("❌ Aucun profil trouvé dans la base de données.")
        return

    athletes = profiles_res.data
    print(f"📋 {len(athletes)} athlètes à traiter.")

    success_count = 0
    error_count = 0

    TARGET_ATHLETE_ID = 5462709

    # B. Boucle sur chaque athlète
    for athlete in athletes:
        athlete_id = athlete['id_strava']
        full_name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}"
        last_sync = athlete.get('last_full_synchro')
        refresh_token = athlete['refresh_token']

        # --- AJOUT : FILTRE SUR L'ID ---
        #if athlete_id != TARGET_ATHLETE_ID:
        #    continue  # On ignore et on passe au suivant
        
        # --- LOGIQUE DE VÉRIFICATION (24h) ---
        should_sync = True
        if last_sync:
            last_sync_date = parser.parse(last_sync)
            # Si la dernière synchro date de moins de 24h
            if datetime.datetime.now(datetime.timezone.utc) - last_sync_date < datetime.timedelta(days=1):
                should_sync = False

        if not should_sync:
            print(f"⏩ {full_name} : Synchro récente ({last_sync}). Skip.")
            continue

        print(f"\n🔄 Traitement de {full_name} (ID: {athlete_id})...")

        try:
            # 1. Obtenir un access_token frais
            token_response = exchange_refresh_token(refresh_token)
            if not token_response or 'access_token' not in token_response:
                print(f"   ⚠️ Impossible de rafraîchir le token pour {full_name}. Skip.")
                error_count += 1
                continue
            
            new_access = token_response['access_token']
            new_refresh = token_response.get('refresh_token', refresh_token)

            # 2. Fetch de TOUTES les activités (Full Sync)
            print(f"   📥 Récupération de tout l'historique Strava...")
            all_activities = fetch_all_activities_parallel(new_access)

            if all_activities:
                # 3. Préparation de l'objet athlète pour sync_profile_and_activities
                athlete_obj = {
                    "id": athlete_id,
                    "firstname": athlete.get("firstname"),
                    "lastname": athlete.get("lastname"),
                    "profile_medium": athlete.get("avatar_url")
                }

                # 4. Envoi vers Supabase (Upsert)
                # Note: Assurez-vous que db_operations.py inclut 'moving_time' dans le mapping
                sync_profile_and_activities(athlete_obj, all_activities, new_refresh, is_full_sync=True,is_from_ui=False)
                print(f"   ✅ {len(all_activities)} activités synchronisées/mises à jour.")
                success_count += 1
            else:
                print(f"   ℹ️ Aucune activité trouvée pour cet athlète.")

            # 5. Pause de sécurité pour le Rate Limit Strava (100 requêtes / 15 min)
            # fetch_all_activities_parallel fait plusieurs requêtes par athlète.
            time.sleep(2)

        except Exception as e:
            print(f"   ❌ Erreur pour {full_name} : {e}")
            error_count += 1

    print(f"\n✨ [{datetime.datetime.now()}] MIGRATION TERMINÉE")
    print(f"📊 Résultat : {success_count} succès, {error_count} erreurs.")

if __name__ == "__main__":
    run_migration()