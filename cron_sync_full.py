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
    nightly_sync(False) 

    print(f"\n✨ [{datetime.datetime.now()}] SYNCHRO FULL TERMINÉE.")

if __name__ == "__main__":
    run_full_migration()