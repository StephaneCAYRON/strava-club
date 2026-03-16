"""
Script one-shot : recalcule is_sunday_challenge pour toutes les activités en base.
Utilise exactement is_passing_through_escalquens() de db_operations.py.

Usage :
    python recalc_sunday_challenge.py
    python recalc_sunday_challenge.py --dry-run   (affiche sans modifier la DB)
"""

import os
import sys
import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Variables SUPABASE_URL / SUPABASE_KEY manquantes.")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

DRY_RUN = "--dry-run" in sys.argv

# --- Fonction copiée exactement depuis db_operations.py ---
import polyline as _polyline

def is_passing_through_escalquens(poly_str):
    """Vérifie si un point de la polyline est à < 3000m de la mairie."""
    try:
        points = _polyline.decode(poly_str)
        target = (43.5171, 1.5624)
        for p in points:
            if abs(p[0] - target[0]) < 0.03 and abs(p[1] - target[1]) < 0.03:
                return True
        return False
    except:
        return False


def should_be_sunday_challenge(row):
    """Reproduit exactement la logique de db_operations.save_athlete_data."""
    try:
        start_dt = datetime.datetime.fromisoformat(row["start_date"].replace("Z", "+00:00"))
    except Exception:
        return False

    if start_dt.weekday() != 6:          # doit être dimanche
        return False
    local_hour = start_dt.hour + 1       # UTC+1 estimé (même logique que le code original)
    if not (5 <= local_hour <= 10):
        return False
    if (row.get("distance_km") or 0) < 50:
        return False
    poly = row.get("summary_polyline")
    if not poly:
        return False
    return is_passing_through_escalquens(poly)


def fetch_all_activities():
    """Récupère toutes les activités par pages de 1000."""
    all_rows = []
    page = 0
    page_size = 1000
    while True:
        res = (
            supabase.table("activities")
            .select("id_activity, start_date, distance_km, summary_polyline, is_sunday_challenge")
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        rows = res.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        page += 1
    return all_rows


def main():
    print(f"{'[DRY-RUN] ' if DRY_RUN else ''}Chargement des activités...")
    rows = fetch_all_activities()
    print(f"{len(rows)} activités chargées.")

    to_update = []
    for row in rows:
        new_val = should_be_sunday_challenge(row)
        old_val = bool(row.get("is_sunday_challenge"))
        if new_val != old_val:
            to_update.append({
                "id_activity": row["id_activity"],
                "is_sunday_challenge": new_val,
            })
            flag = "✅ True" if new_val else "❌ False"
            print(f"  {flag}  id={row['id_activity']}  date={row['start_date'][:10]}")

    print(f"\n{len(to_update)} activité(s) à modifier.")

    if not to_update:
        print("Rien à faire.")
        return

    if DRY_RUN:
        print("[DRY-RUN] Aucune modification envoyée.")
        return

    # Upsert par batch de 100
    batch_size = 100
    for i in range(0, len(to_update), batch_size):
        batch = to_update[i:i + batch_size]
        supabase.table("activities").upsert(batch).execute()
        print(f"  Batch {i // batch_size + 1} envoyé ({len(batch)} lignes).")

    print("✅ Recalcul terminé.")


if __name__ == "__main__":
    main()
