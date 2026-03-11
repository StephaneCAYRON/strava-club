import streamlit as st
import pandas as pd
import folium
import polyline
import streamlit_javascript as st_js

from folium.plugins import HeatMap
from streamlit_folium import st_folium
from db_operations import supabase
from ui_components import common_critria

def render_tab_heatmap(texts):
    st.header("🗺️ Parcours dominicaux (meilleure visualisation sur PC)")
  
    # --- 1. FILTRES ---
    selected_g, selected_year = common_critria("heatmap")

    if selected_g == "":
        st.info("Aucun groupe disponible")
        return

    # Ajout du choix du mode d'affichage
    display_mode = st.segmented_control(
        "Mode d'affichage", 
        ["🛤️ Traces","🔥 Heatmap"], 
        default="🛤️ Traces"
    )

    # --- 2. RÉCUPÉRATION DES DONNÉES ---
    query = supabase.table("activities")\
        .select("summary_polyline, start_date, name, id_activity")\
        .eq("is_sunday_challenge", True)\
        .not_.is_("summary_polyline", "null")\
        .gte("start_date", f"{selected_year}-01-01")\
        .lte("start_date", f"{selected_year}-12-31")
    
    res = query.execute()
    
    if not res.data:
        st.warning(f"Aucune trace trouvée pour l'année {selected_year}.")
        return

    # --- 3. PRÉPARATION PANDAS ET FILTRE MOIS ---
    df = pd.DataFrame(res.data)
    df['start_date'] = pd.to_datetime(df['start_date'])
    df['Mois'] = df['start_date'].dt.month_name()
    df['Mois_Num'] = df['start_date'].dt.month
    df['date_only'] = df['start_date'].dt.date 

    months_in_data = df.sort_values('Mois_Num')['Mois'].unique().tolist()
    option_all = texts.get("all_year", "Toute l'année")
    options_list = [option_all] + months_in_data
    
    selected_period = st.segmented_control("Période", options_list, selection_mode="single", default=options_list[0])

    df_final = df if selected_period == option_all else df[df['Mois'] == selected_period]

    if df_final.empty:
        st.warning("Aucune trace pour cette sélection.")
        return

    # --- 4. DÉDOUBLONNAGE (1 trace par dimanche) ---
    df_unique_sundays = df_final.drop_duplicates(subset=['date_only'])

    # --- 5. DÉCODAGE DES TRACES ---
    all_points = []      # Pour la Heatmap (liste plate de points)
    list_of_lines = []   # Pour les Polylines (liste de listes de points)
    
    for _, act in df_unique_sundays.iterrows():
        points = polyline.decode(act['summary_polyline'])
        if points:
            all_points.extend(points)
            list_of_lines.append(points)

    # --- 6. CRÉATION DE LA CARTE ---
    avg_lat = sum(p[0] for p in all_points) / len(all_points)
    avg_lon = sum(p[1] for p in all_points) / len(all_points)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=11, tiles="cartodbpositron")
    
    if display_mode == "🔥 Heatmap":
        HeatMap(all_points, radius=5, blur=5, min_opacity=0.4).add_to(m)
    else:
        # Affichage des lignes réelles avec Tooltip
        # On itère directement sur le dataframe unique pour avoir accès aux métadonnées
        for _, act in df_unique_sundays.iterrows():
            line_points = polyline.decode(act['summary_polyline'])
            if not line_points:
                continue
                
            # Préparation des infos
            date_obj = pd.to_datetime(act['start_date']).strftime('%d/%m/%Y')
            strava_url = f"https://www.strava.com/activities/{act['id_activity']}"
            
            # HTML pour le Tooltip (au survol)
            tooltip_html = f"""
                <div style="font-family: sans-serif;">
                    <b>{act['name']}</b><br>
                    📅 {date_obj}<br>
                    <span style="color: #FC4C02;">🖱️ Cliquer pour voir sur Strava</span>
                </div>
            """
            
            # HTML pour le Popup (au clic) pour permettre de cliquer sur le lien
            popup_html = f'<a href="{strava_url}" target="_blank">Ouvrir dans Strava 🔗</a>'

            folium.PolyLine(
                line_points, 
                color="#FF4B4B", 
                weight=3, 
                opacity=0.6,
                tooltip=folium.Tooltip(tooltip_html),
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(m)

    # --- 5. DÉTECTION DE LA LARGEUR POUR LE RESPONSIVE ---
    # On récupère la largeur de la fenêtre via JS
    width = st_js.st_javascript("window.innerWidth")
    
    # Par défaut on met 800, mais si JS renvoie une valeur < 768px (mobile), on passe à 400
    # Note : au tout premier chargement, width peut être 0 ou None
    map_height = 800
    if width and width < 768:
        map_height = 400

    # Modifie cette ligne à la fin de ton fichier
    st_folium(
        m, 
        use_container_width=True, 
        height=map_height,
        returned_objects=[],  # 👈 AJOUTE CECI : Empêche le déclenchement d'un rerun au mouvement
        key="map_sunday_challenge" # 👈 AJOUTE UNE CLÉ UNIQUE pour stabiliser le composant
    )
    
    # Message d'information mis à jour pour confirmer l'optimisation
    st.info(f"Carte générée à partir de **{len(df_unique_sundays)} sorties uniques** sur la période (filtrées à partir de {len(df_final)} participations globales).")
