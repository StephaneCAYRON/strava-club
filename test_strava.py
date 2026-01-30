import requests

ACCESS_TOKEN = "9dabccb98393a378008a19e8162086dabf04a4af" 
JAN_1_2026 = 1735689600

def check_everything():
    headers = {'Authorization': f"Bearer {ACCESS_TOKEN}"}
    
    # 1. On demande à Strava : "Quels sont mes droits ?"
    print("--- VÉRIFICATION DES DROITS ---")
    res_athlete = requests.get("https://www.strava.com/api/v3/athlete", headers=headers)
    
    # Les permissions sont dans les headers 'x-read-oauth-scopes'
    # Remplace la boucle de check par celle-ci pour tout voir
    print("--- HEADERS REÇUS ---")
    for k, v in res_athlete.headers.items():
        print(f"{k}: {v}")
    
    # 2. Test du filtre
    print("\n--- TEST DU FILTRE 2026 ---")
    url = f"https://www.strava.com/api/v3/athlete/activities?after={JAN_1_2026}&per_page=10"
    res_activities = requests.get(url, headers=headers)
    
    if res_activities.status_code == 200:
        data = res_activities.json()
        print(f"Nombre d'activités trouvées : {len(data)}")
        for a in data:
            print(f"- {a['start_date']} | {a['name']}")
    else:
        print(f"Erreur API : {res_activities.text}")

if __name__ == "__main__":
    check_everything()


# https://www.strava.com/oauth/authorize?client_id=4147&response_type=code&redirect_uri=http://localhost:8501&approval_prompt=force&scope=read,activity:read_all
