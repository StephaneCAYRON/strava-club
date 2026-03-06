import time
import datetime
from cron_sync import nightly_sync

def run_full_migration():
    print(f"🌕 [{datetime.datetime.now()}] DÉMARRAGE DE LA SYNCHRO FULL NOCTURNE")
    print("Option : Force Full Sync = True | Pause inter-athlète = 15min")
    print("------------------------------------------------------------------")

    # On appelle nightly_sync avec False pour is_partial
    # Note : Il faut s'assurer que nightly_sync dans cron_sync.py 
    # accepte de faire une pause si on le souhaite, 
    # ou alors on réécrit la boucle ici pour un contrôle total.
    
    # Voici la version 'boucle contrôlée' pour être certain du sleep :
    from db_operations import supabase
    
    if not supabase:
        print("❌ Erreur : Supabase non connecté.")
        return

    profiles = supabase.table("profiles").select("*").execute().data
    total = len(profiles)

    for index, profile in enumerate(profiles):
        full_name = f"{profile.get('firstname')} {profile.get('lastname')}"
        print(f"\n🔄 [{index+1}/{total}] Traitement de : {full_name}")
        
        # On appelle ta fonction de synchro individuelle (importée de cron_sync)
        from cron_sync import sync_single_athlete
        
        # force_full=True pour ignorer le check des 2 jours si tu veux vraiment tout rafraîchir
        success, msg = sync_single_athlete(profile, is_partial=False, force_full=True)
        print(f"   Result: {msg}")

        # Si ce n'est pas le dernier athlète, on attend que le quota Strava se réinitialise
        if index < total - 1:
            print(f"🕒 Attente de 15 minutes pour réinitialiser le quota Strava (100 req/15min)...")
            # 901 secondes pour être sûr de dépasser la fenêtre glissante de Strava
            time.sleep(901) 

    print(f"\n✨ [{datetime.datetime.now()}] SYNCHRO FULL TERMINÉE.")

if __name__ == "__main__":
    run_full_migration()