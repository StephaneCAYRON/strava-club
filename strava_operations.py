import streamlit as st
import requests
import urllib.parse
import concurrent.futures
import requests

STRAVA_CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
STRAVA_CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
STRAVA_REDIRECT_URI = st.secrets["STRAVA_REDIRECT_URI"]

def get_strava_auth_url():
    # On demande explicitement le droit de lire les activités
    scopes = "read,activity:read_all"
    
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": STRAVA_REDIRECT_URI,
        "approval_prompt": "force",
        "scope": scopes
    }
    
    # Utiliser urllib pour encoder proprement les paramètres
    import urllib.parse
    return f"https://www.strava.com/oauth/authorize?{urllib.parse.urlencode(params)}"

def exchange_code_for_token(code):
    res = requests.post("https://www.strava.com/oauth/token", data={
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    })
    return res.json() if res.status_code == 200 else None

def fetch_strava_activities(access_token, after_timestamp):
    headers = {'Authorization': f"Bearer {access_token}"}
    params = {
        'after': int(after_timestamp), 
        'per_page': 100
    }
    # DEBUG : On va voir l'URL finale générée
    req = requests.Request('GET', "https://www.strava.com/api/v3/athlete/activities", headers=headers, params=params)
    prepared = req.prepare()
    st.write(f"DEBUG URL: {prepared.url}") # <--- VÉRIFIE BIEN LE CHIFFRE APRÈS 'after='
    
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params=params)

    if res.status_code == 200:
        return res.json()
    else:
        st.error(f"Erreur Strava: {res.status_code}")
        return None

def fetch_page(access_token, page, per_page=200):
    # """Récupère une seule page d'activités."""
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'page': page, 'per_page': per_page}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    return []

def fetch_all_activities_parallel(access_token, max_pages=20):
    # """Lance plusieurs requêtes en parallèle pour aller vite."""
    all_activities = []
    
    # Utilisation d'un pool de threads (10 threads en parallèle comme demandé)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # On prépare les appels pour les pages 1 à max_pages
        future_to_page = {executor.submit(fetch_page, access_token, p): p for p in range(1, max_pages + 1)}
        
        for future in concurrent.futures.as_completed(future_to_page):
            page_data = future.result()
            if page_data:
                all_activities.extend(page_data)
    return all_activities

def get_strava_stats(access_token, athlete_id):
    url = f"https://www.strava.com/api/v3/athletes/{athlete_id}/stats"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            rides = data.get('all_ride_totals', {}).get('count', 0)
            runs = data.get('all_run_totals', {}).get('count', 0)
            swims = data.get('all_swim_totals', {}).get('count', 0)
            
            total_val = rides + runs + swims
            stats_string = f"Total : {total_val} (🚲 {rides} | 🏃 {runs} | 🏊 {swims})"
            
            # ON RENVOIE EXACTEMENT DEUX ÉLÉMENTS
            return stats_string, total_val
            
        return "Stats indisponibles", 0
    except Exception:
        return "Erreur de connexion", 0