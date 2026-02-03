import datetime
import traceback
from db_operations import supabase, sync_profile_and_activities
from strava_operations import exchange_refresh_token, fetch_page

import os
from dotenv import load_dotenv

# Maintenant, os.getenv ira chercher soit dans le .env, soit dans les secrets GitHub
def get_secret(key):
    # 1. On essaie d'abord via Streamlit (pour l'interface web)
    try:
        result = os.getenv(key)
        print(f"[{datetime.datetime.now()}] key#value : {key}#{result}")
        return result
    except:
        # 2. Sinon on prend dans l'environnement (pour le script de nuit)
        return os.getenv(key)


def nightly_sync():

    # Charge les variables du fichier .env s'il existe
    load_dotenv()
    # Initialisation (utilisée en interne)
    SUPABASE_URL = get_secret("SUPABASE_URL")
    SUPABASE_KEY = get_secret("SUPABASE_KEY")

    print(f"[{datetime.datetime.now()}] --- DÉBUT DE LA SYNCHRONISATION NOCTURNE ---")
    
    # 1. Récupération des profils depuis Supabase
    try:
        profiles = supabase.table("profiles").select("id_strava, refresh_token, firstname").execute()
    except Exception as e:
        print(f"[{datetime.datetime.now()}] ❌ ERREUR CRITIQUE : Impossible de lire la table profiles.")
        print(traceback.format_exc())
        return

    success_count = 0
    error_count = 0

    for profile in profiles.data:
        athlete_id = profile['id_strava']
        athlete_name = profile.get('firstname', 'Inconnu')
        old_refresh_token = profile['refresh_token']
        
        print(f"[{datetime.datetime.now()}] Traitement de l'athlète : {athlete_name} ({athlete_id})...")

        try:
            # 2. Rafraîchissement du Token
            tokens = exchange_refresh_token(old_refresh_token)
            if not tokens or 'access_token' not in tokens:
                print(f"  ⚠️ ÉCHEC : Impossible de rafraîchir le token pour {athlete_name}. L'utilisateur a peut-être révoqué l'accès.")
                error_count += 1
                exit
                #continue

            new_access = tokens['access_token']
            new_refresh = tokens['refresh_token']

            # 3. Récupération des dernières activités (Page 1)
            # Note : on utilise per_page=10 pour être léger sur l'API
            latest_activities = fetch_page(new_access, page=1, per_page=10)
            
            if latest_activities is None:
                print(f"  ⚠️ ÉCHEC : Erreur lors de la récupération des activités Strava pour {athlete_name}.")
                error_count += 1
                continue

            # 4. Synchronisation Base de données
            # On crée un stub pour correspondre à la structure attendue par ta fonction
            athlete_stub = {"id": athlete_id} 
            
            sync_result = sync_profile_and_activities(athlete_stub, latest_activities, new_refresh)
            
            if sync_result:
                print(f"  ✅ SUCCÈS : {len(latest_activities)} activités traitées.")
                success_count += 1
            else:
                print(f"  ⚠️ ÉCHEC : Erreur lors de l'upsert dans Supabase pour {athlete_name}.")
                error_count += 1

        except Exception as e:
            print(f"  ❌ ERREUR INATTENDUE pour {athlete_name} : {str(e)}")
            # On n'arrête pas la boucle, on passe au suivant
            error_count += 1
            continue

    print(f"\n[{datetime.datetime.now()}] --- SYNCHRONISATION TERMINÉE ---")
    print(f"Résultat : {success_count} succès, {error_count} échecs.")

if __name__ == "__main__":
    nightly_sync()