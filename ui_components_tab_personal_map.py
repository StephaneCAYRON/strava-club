import streamlit as st
import pandas as pd
import folium
import polyline
import streamlit_javascript as st_js
import datetime

from folium.plugins import HeatMap
from streamlit_folium import st_folium
from db_operations import supabase

# Importation de notre fonction de filtres partagée
from ui_components_tab_advanced_stats import render_filter_ui

MAX_ACTIVITIES_FOR_TOOLTIPS = 500


@st.cache_data(ttl=300, show_spinner="Chargement des activités…")
def _fetch_activities(athlete_id):
    return supabase.table("activities")\
        .select("summary_polyline, start_date, name, id_activity, type")\
        .eq("id_strava", athlete_id)\
        .not_.is_("summary_polyline", "null")\
        .order("start_date", desc=True)\
        .execute()


def _simplify_points(points, max_points=150):
    """Sous-échantillonne une liste de points GPS par stride."""
    if len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    return points[::step]


def render_tab_personal_map(texts):
    athlete_id = st.session_state.athlete['id']

    # --- INITIALISATION DE LA HAUTEUR ---
    default_tag = "XL"
    if 'pmap_size_tag' not in st.session_state:
        st.session_state.pmap_size_tag = "XL"

    # --- 1. RÉCUPÉRATION DES DONNÉES (mise en cache) ---
    res = _fetch_activities(athlete_id)

    if not res.data:
        st.warning("Aucune activité avec trace GPS trouvée.")
        return

    df = pd.DataFrame(res.data)

    # Préparation des dates pour les filtres
    df['start_date'] = pd.to_datetime(df['start_date'])
    df['year'] = df['start_date'].dt.year
    df['month_num'] = df['start_date'].dt.month

    months_order = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
        7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }
    df['month'] = df['month_num'].map(months_order)

    # --- 2. DÉCODAGE UNIQUE DES POLYLINES ---
    df['decoded_points'] = df['summary_polyline'].apply(
        lambda s: polyline.decode(s) if s else []
    )

    # Listes uniques pour initialiser les filtres
    all_years = sorted(df['year'].unique().tolist(), reverse=True)
    current_year = datetime.datetime.now().year
    default_year = [current_year] if current_year in all_years else [all_years[0]]

    present_months_nums = sorted(df['month_num'].unique().tolist())
    all_months = [months_order[m] for m in present_months_nums]

    all_types = sorted(df['type'].unique().tolist())

    # --- 3. ZONE DE FILTRES ---
    with st.expander("🛠️ Filtres", expanded=True):
        f_col1, f_col2, f_col3 = st.columns(3)
        # IMPORTANT : On utilise des préfixes uniques ("pmap_...") pour ne pas interférer avec la page des stats avancées
        with f_col1: selected_years = render_filter_ui("Années", all_years, "pmap_years", default_val=default_year)
        with f_col2: selected_months = render_filter_ui("Mois", all_months, "pmap_months", default_val=all_months)
        with f_col3: selected_types = render_filter_ui("Sports", all_types, "pmap_types", default_val=all_types)

    # Vérification de sécurité
    if not selected_years or not selected_months or not selected_types:
        st.info("Veuillez sélectionner au moins une année, un mois et un sport pour générer la carte.")
        return

    # Application des filtres sur le dataframe
    df_filtered = df[
        (df['year'].isin(selected_years)) &
        (df['month'].isin(selected_months)) &
        (df['type'].isin(selected_types))
    ].copy()

    if df_filtered.empty:
        st.warning("Aucune trace ne correspond à vos filtres.")
        return

    # --- 4. AVERTISSEMENT SI TROP D'ACTIVITÉS ---
    too_many = len(df_filtered) > MAX_ACTIVITIES_FOR_TOOLTIPS
    if too_many:
        st.warning(
            f"⚠️ **{len(df_filtered)} activités** correspondent à vos filtres. "
            f"La carte sera affichée, mais les **infobulles sont désactivées** pour éviter de bloquer le navigateur. "
            f"Affinez vos filtres (années, mois, sports) pour réactiver les infobulles."
        )

    # --- 5. CONFIGURATION DE L'AFFICHAGE (Mode et Taille sur une ligne) ---
    c1, c2 = st.columns([1, 1])

    with c1:
        display_mode = st.segmented_control(
            "Mode d'affichage",
            ["🛤️ Traces", "🔥 Heatmap"],
            default="🛤️ Traces"
        )

    with c2:
        height_options = {"S": 400, "M": 600, "L": 800, "XL": 1000}

        selected_tag = st.segmented_control(
            "Taille de la carte",
            options=list(height_options.keys()),
            key="pmap_size_tag",
            default=default_tag
        )

        # --- SÉCURITÉ ANTI-NONE ---
        if selected_tag is None:
            selected_tag = "S"

        current_height = height_options[selected_tag]

    # --- 6. CALCUL DU CENTRE DE LA CARTE ---
    all_points = [p for pts in df_filtered['decoded_points'] for p in pts]

    if not all_points:
        st.warning("Aucune coordonnée valide n'a pu être extraite des traces.")
        return

    avg_lat = sum(p[0] for p in all_points) / len(all_points)
    avg_lon = sum(p[1] for p in all_points) / len(all_points)

    # --- 7. CRÉATION DE LA CARTE ---
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=11, tiles="cartodbpositron")

    if display_mode == "🔥 Heatmap":
        # Pour la heatmap on simplifie aussi pour alléger
        simplified_all = [p for pts in df_filtered['decoded_points'] for p in _simplify_points(pts)]
        HeatMap(simplified_all, radius=5, blur=5, min_opacity=0.4).add_to(m)
    else:
        for _, act in df_filtered.iterrows():
            line_points = _simplify_points(act['decoded_points'])
            if not line_points:
                continue

            # Choix de la couleur en fonction du sport
            act_type = act.get('type', '')
            if act_type == 'Ride':
                line_color = "#FF4B4B"
            elif act_type == 'Run':
                line_color = "#2ECC71"
            else:
                line_color = "#F1C40F"

            date_obj = act['start_date'].strftime('%d/%m/%Y')
            strava_url = f"https://www.strava.com/activities/{act['id_activity']}"
            popup_html = f'<a href="{strava_url}" target="_blank">Ouvrir dans Strava 🔗</a>'

            if too_many:
                # Tooltips désactivés pour fluidité
                folium.PolyLine(
                    line_points,
                    color=line_color,
                    weight=3,
                    opacity=0.4,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(m)
            else:
                tooltip_text = f"{act['name']} — {act_type} — {date_obj} 🖱️ Cliquer pour Strava"
                folium.PolyLine(
                    line_points,
                    color=line_color,
                    weight=3,
                    opacity=0.4,
                    tooltip=folium.Tooltip(tooltip_text),
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(m)

    st_folium(
        m,
        use_container_width=True,
        height=current_height,
        returned_objects=[],  # Empêche la page de se recharger lors des zooms/déplacements
        key="map_personal_view"
    )

    st.info(f"Carte générée à partir de **{len(df_filtered)} activités**.")
