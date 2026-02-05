import os
import datetime
import traceback
import requests
from db_operations import *
from strava_operations import *
from dotenv import load_dotenv

# --- 1. CONFIGURATION DE L'ENVIRONNEMENT ---
# Charge les variables du fichier .env (pour le local)
load_dotenv()

# On tente d'importer les modules du projet.
# ATTENTION : Vos fichiers db_operations.py et strava_operations.py doivent
# être capables de gérer l'absence de st.secrets (voir étapes précédentes).
try:
    from db_operations import supabase, sync_profile_and_activities
    from strava_operations import fetch_page
except ImportError as e:
    print("❌ ERREUR D'IMPORT : Assurez-vous que db_operations et strava_operations sont accessibles.")
    print("Si vous utilisez st.secrets dans ces fichiers, remplacez par os.getenv pour le script.")
    raise e

# Récupération des secrets depuis l'environnement
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

def exchange_refresh_token_local(refresh_token):
    """
    Fonction locale pour échanger le token sans dépendre de st.secrets.
    Renvoie le JSON complet ou None.
    """
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        print("❌ ERREUR : STRAVA_CLIENT_ID ou SECRET manquant dans les variables d'environnement.")
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
        else:
            print(f"⚠️ Erreur Strava ({res.status_code}) : {res.text}")
            return None
    except Exception as e:
        print(f"⚠️ Exception réseau lors du refresh : {e}")
        return None

def nightly_sync(yesForOnlyRecentFalseForAll):
    print(f"\n[{datetime.datetime.now()}] --- 🚀 DÉBUT DE LA SYNCHRONISATION BATCH ---")
    
    # 1. Vérification de la connexion DB
    if not supabase:
        print("❌ ERREUR : Client Supabase non initialisé (vérifiez SUPABASE_URL/KEY).")
        return

    # 2. Récupération des profils actifs
    try:
        # On récupère toutes les infos nécessaires pour reconstruire l'objet 'athlete'
        response = supabase.table("profiles").select("*").execute()
        profiles = response.data
    except Exception:
        print(traceback.format_exc())
        return

    print(f"👥 {len(profiles)} athlètes trouvés à mettre à jour.")

    success_count = 0
    error_count = 0
    updated_tokens = 0

    for profile in profiles:
        athlete_id = profile['id_strava']
        # On utilise le prénom/nom pour les logs, ou 'Inconnu' par défaut
        full_name = f"{profile.get('firstname', 'Athlète')} {profile.get('lastname', '')}".strip()
        old_refresh = profile.get('refresh_token')

        print(f"👉 Traitement de : {full_name} ({athlete_id})")

        if not old_refresh:
            print("   ⚠️ Pas de refresh token, ignoré.")
            error_count += 1
            continue

        try:
            # --- A. ROTATION DU TOKEN ---
            tokens = exchange_refresh_token_local(old_refresh)
            
            if not tokens or 'access_token' not in tokens:
                print("   ⛔ Impossible de rafraîchir le token. Accès révoqué ?")
                error_count += 1
                continue

            new_access = tokens['access_token']
            new_refresh = tokens['refresh_token']

            # --- B. SAUVEGARDE CRITIQUE DU TOKEN ---
            # On le sauvegarde tout de suite pour ne pas le perdre si la suite plante
            if new_refresh != old_refresh:
                supabase.table("profiles").update({
                    "refresh_token": new_refresh,
                    "updated_at": datetime.datetime.now().isoformat()
                }).eq("id_strava", athlete_id).execute()
                updated_tokens += 1
            
            # --- C. RÉCUPÉRATION DES ACTIVITÉS ---
            # On récupère les 30 dernières activités (permet de mettre à jour 
            # les titres modifiés ou descriptions des sorties récentes)
            if yesForOnlyRecentFalseForAll:
                gathered_activities = fetch_page(new_access, page=1, per_page=30)
            else:
                total, recent = get_athlete_summary(athlete_id)
                if total < 100:
                    print(f"👉 Moins de 100 (total:{total}), full sync launched {full_name} ({athlete_id})")
                    gathered_activities = fetch_all_activities_parallel(new_access)
                else:
                    gathered_activities = False
                    print(f"👉 Plus de 100 (total:{total}), full sync skipped {full_name} ({athlete_id})")    

            if gathered_activities:
                # --- D. RECONSTRUCTION DE L'OBJET ATHLETE ---
                # db_operations attend un dictionnaire style Strava
                athlete_obj = {
                    "id": athlete_id,
                    "firstname": profile.get("firstname"),
                    "lastname": profile.get("lastname"),
                    "profile_medium": profile.get("avatar_url")
                }

                # --- E. SYNCHRONISATION (UPSERT) ---
                # Cette fonction va mettre à jour les activités existantes et créer les nouvelles
                sync_profile_and_activities(athlete_obj, gathered_activities, new_refresh)
                print(f"   ✅ {len(gathered_activities)} activités vérifiées/synchronisées.")
                success_count += 1

                break

            else:
                print("   ℹ️ Aucune activité récente trouvée.")

        except Exception as e:
            print(f"   ❌ Erreur inattendue pour {full_name} : {e}")
            error_count += 1
            continue

    print(f"[{datetime.datetime.now()}] --- TERMINÉ : {success_count} OK, {updated_tokens} Tokens rafraîchis, {error_count} Erreurs ---")


if __name__ == "__main__":
    nightly_sync(True)