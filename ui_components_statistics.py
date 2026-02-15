import streamlit as st
import pandas as pd
import altair as alt
import datetime
from db_operations import get_activities_for_athlete # Assurez-vous d'avoir cette fonction


# --- FONCTIONS UTILITAIRES ---

def calculate_eddington(series):
    """Calcule le nombre d'Eddington à partir d'une série de distances"""
    if series.empty:
        return 0
    # On trie les distances de la plus grande à la plus petite
    sorted_dist = series.sort_values(ascending=False).reset_index(drop=True)
    # On cherche l'index où la distance devient inférieure au rang
    for i, dist in enumerate(sorted_dist):
        if dist < i + 1:
            return i
    return len(sorted_dist)

def render_stat_card(icon, title, value, subtext, color="#E62E2D"):
    """Affiche une carte de stat stylisée"""
    st.markdown(f"""
        <div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 4px solid {color}; margin-bottom: 10px;">
            <div style="display: flex; align-items: center;">
                <div style="font-size: 24px; margin-right: 15px;">{icon}</div>
                <div>
                    <div style="color: #888; font-size: 12px; font-weight: bold; text-transform: uppercase;">{title}</div>
                    <div style="color: #2c3e50; font-size: 24px; font-weight: 800;">{value}</div>
                    <div style="color: #95a5a6; font-size: 12px; font-style: italic;">{subtext}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- PAGE PRINCIPALE ---

def render_advanced_stats(df_activities):
    st.markdown("### 📊 Stat vélo")

    if df_activities.empty:
        st.info("Pas assez de données pour générer les statistiques.")
        return

    # S'assurer que les dates sont au bon format
    df_activities['start_date'] = pd.to_datetime(df_activities['start_date'])
    df_activities['year'] = df_activities['start_date'].dt.year
    df_activities['month'] = df_activities['start_date'].dt.month_name()

    # --- 1. LE NOMBRE D'EDDINGTON ---
    eddington = calculate_eddington(df_activities['distance_km'])
    
    # Combien de sorties nécessaires pour le prochain niveau ?
    # On compte combien de sorties on a déjà fait > (eddington + 1)
    next_level = eddington + 1
    current_rides_for_next = len(df_activities[df_activities['distance_km'] >= next_level])
    missing_rides = next_level - current_rides_for_next

    # --- 2. LES RECORDS (MAX) ---
    max_dist = df_activities['distance_km'].max()
    max_elev = df_activities['total_elevation_gain'].max()
    max_time_min = df_activities['moving_time'].max() / 60 if 'moving_time' in df_activities.columns else 0
    max_watts = df_activities['average_watts'].max() if 'average_watts' in df_activities.columns else 0

    # AFFICHAGE DU TOP BLOC
    col1, col2, col3 = st.columns(3)
    
    with col1:
        render_stat_card("🎩", "Nombre d'Eddington", f"{eddington}", f"Manque {missing_rides} sorties de {next_level}km", "#9b59b6")
    
    with col2:
        render_stat_card("📏", "Max Distance", f"{max_dist:.1f} km", "", "#3498db")
        
    with col3:
        render_stat_card("⛰️", "Max Dénivelé", f"{max_elev:.0f} m", "", "#e67e22")

    st.write("Le numéro d'Eddington (E) est obtenu quand le nombre de kilomètre réalisés en une sortie est égale au nombre de fois où ce kilométrage a été effectué.")
    st.write("Exemple : Un cycliste à un nombre d'Eddington de 123 : cela veut dire qu'il a effectué 123 sorties d'au moins 123 km.")
    st.divider()

    # --- 3. RÉPARTITION ANNUELLE (Heatmap simplifiée) ---
    st.markdown("#### 📅 Km vélo par an")
    
    # On groupe par Année
    yearly_stats = df_activities.groupby('year').agg({
        'distance_km': 'sum',
        'total_elevation_gain': 'sum',
        'id_strava': 'count'
    }).reset_index().sort_values('year', ascending=False)
    
    # On met l'année en string pour éviter la virgule (2,024)
    yearly_stats['year'] = yearly_stats['year'].astype(str)

    # Graphique combiné (Barres pour KM, Ligne pour D+)
    base = alt.Chart(yearly_stats).encode(x=alt.X('year', title="Année"))

    bar = base.mark_bar(color='#E62E2D', opacity=0.8).encode(
        y=alt.Y('distance_km', title='Distance (km)'),
        tooltip=['year', 'distance_km', 'total_elevation_gain', 'id_strava']
    )

    text = base.mark_text(dy=-10, color='black').encode(
        y='distance_km',
        text=alt.Text('distance_km', format=',.0f')
    )

    st.altair_chart((bar + text).interactive(), use_container_width=True)

    # --- 4. TABLEAU DES RECORDS DÉTAILLÉS ---
    st.markdown("#### 🏆 Vos Records")
    
    # URL Strava pour chaque activité (id_activity présent dans les données)
    df_activities = df_activities.copy()
    if 'id_activity' in df_activities.columns:
        df_activities['strava_url'] = "https://www.strava.com/activities/" + df_activities['id_activity'].astype(str)
    
    #col_a, col_b = st.columns(2)
    
    common_column_config = {
        "start_date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
        "name": "Nom",
        "distance_km": st.column_config.NumberColumn("Km", format="%.1f"),
        "total_elevation_gain": st.column_config.NumberColumn("D+", format="%d"),
    }
    if 'strava_url' in df_activities.columns:
        common_column_config["strava_url"] = st.column_config.LinkColumn("🔗 Strava", display_text="Ouvrir")
    
    #with col_a:
    st.caption("Top 5 Distances")
    cols_dist = ['start_date', 'name', 'distance_km', 'total_elevation_gain']
    if 'strava_url' in df_activities.columns:
        cols_dist.append('strava_url')
    top_dist = df_activities.nlargest(5, 'distance_km')[cols_dist]
    st.dataframe(top_dist, hide_index=True, use_container_width=True, column_config=common_column_config)
        
    #with col_b:
    st.caption("Top 5 Dénivelés")
    cols_elev = ['start_date', 'name', 'distance_km', 'total_elevation_gain']
    if 'strava_url' in df_activities.columns:
        cols_elev.append('strava_url')
    top_elev = df_activities.nlargest(5, 'total_elevation_gain')[cols_elev]
    st.dataframe(top_elev, hide_index=True, use_container_width=True, column_config=common_column_config)

def render_epic_rides_scatter(df_activities):
    st.markdown("#### 🌌 Km / D+, vélo uniquement")
    
    # --- NETTOYAGE RIGOUREUX ---
    df_chart = df_activities.copy()
    
    # On s'assure que les colonnes sont numériques et sans NaN
    df_chart['distance_km'] = pd.to_numeric(df_chart['distance_km'], errors='coerce')
    df_chart['total_elevation_gain'] = pd.to_numeric(df_chart['total_elevation_gain'], errors='coerce')
    
    # On ne garde que les sorties valides
    df_chart = df_chart.dropna(subset=['distance_km', 'total_elevation_gain'])
    df_chart = df_chart[df_chart['distance_km'] > 0.5] # Sorties de plus de 500m
    
    # Calcul du gradient
    df_chart['gradient'] = (df_chart['total_elevation_gain'] / (df_chart['distance_km'] * 1000)) * 100
    df_chart['gradient_capped'] = df_chart['gradient'].clip(upper=10)
    
    # Conversion de la date en string pour éviter les conflits de format avec Altair
    df_chart['date_str'] = df_chart['start_date'].dt.strftime('%d/%m/%Y')
    # URL Strava pour ouvrir l'activité au clic sur le point
    if 'id_activity' in df_chart.columns:
        df_chart['strava_url'] = "https://www.strava.com/activities/" + df_chart['id_activity'].astype(str)

    if df_chart.empty:
        st.warning("Aucune donnée valide pour afficher le graphique.")
        return

    # --- GRAPHIQUE (points cliquables vers Strava) ---
    encode_kw = dict(
        x=alt.X('distance_km:Q', title='Distance (km)'),
        y=alt.Y('total_elevation_gain:Q', title='Dénivelé (m)'),
        color=alt.Color('gradient_capped:Q', scale=alt.Scale(scheme='turbo'), title='Pente %'),
        tooltip=[
            alt.Tooltip('name:N', title='Nom'),
            alt.Tooltip('date_str:N', title='Date'),
            alt.Tooltip('distance_km:Q', title='Distance', format='.1f'),
            alt.Tooltip('total_elevation_gain:Q', title='Dénivelé', format='.0f'),
            alt.Tooltip('gradient:Q', title='% moyen', format='.2f'),
        ],
    )
    if 'strava_url' in df_chart.columns:
        encode_kw['href'] = alt.Href('strava_url:N')
    scatter = alt.Chart(df_chart).mark_circle(size=100, opacity=0.7, cursor='pointer').encode(**encode_kw).properties(height=500).interactive()

    st.altair_chart(scatter, use_container_width=True)
    if 'strava_url' in df_chart.columns:
        st.caption("Cliquez sur un point pour ouvrir la sortie sur Strava.")