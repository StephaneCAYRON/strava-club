import streamlit as st
import pandas as pd
import altair as alt
import datetime
from db_operations import supabase
from ui_components_statistics import calculate_eddington, render_stat_card, render_epic_rides_scatter

def format_time(seconds):
    """Convertit des secondes en format lisible Hh Mm Ss"""
    if pd.isna(seconds) or seconds == 0:
        return "0h 0m 0s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"

def update_state(key, value):
    """Fonction de callback pour mettre à jour le state avant le rerun"""
    st.session_state[key] = value

def render_filter_ui(title, options, key_prefix, default_val=None):
    """Génère un filtre multi-sélection avec isolation par callbacks (on_click)"""
    ms_key = f"filter_{key_prefix}"
    
    # Initialisation avec la valeur par défaut fournie (ou toutes les options si None)
    if ms_key not in st.session_state:
        st.session_state[ms_key] = default_val if default_val is not None else options
        #st.session_state[ms_key] = options
        
    st.markdown(f"**{title}**")
    
    col1, col2 = st.columns(2)
    
    # 2. Boutons d'action utilisant on_click
    # Cela garantit que l'action est isolée à CE bouton précis
    col1.button(
        "🔄 Rien", 
        key=f"btn_res_{key_prefix}", 
        on_click=update_state, 
        args=(ms_key, []), 
        use_container_width=True
    )
    
    col2.button(
        "✅ Tout", 
        key=f"btn_all_{key_prefix}", 
        on_click=update_state, 
        args=(ms_key, options), 
        use_container_width=True
    )
    
    # 3. Le widget st.pills lié au session_state
    selected = st.pills(
        title, 
        options, 
        selection_mode="multi", 
        key=ms_key,
        label_visibility="collapsed"
    )
    
    return selected

def render_tab_advanced_stats(texts):
    st.title("📈 Statistiques perso")
    
    athlete_id = st.session_state.athlete['id']
    
    # --- 1. RÉCUPÉRATION DE TOUTES LES DONNÉES ---
    # On bypass db_operations.get_activities_for_athlete car elle force type="Ride"
    res = supabase.table("activities").select("*").eq("id_strava", athlete_id).order("start_date", desc=True).execute()
    
    if not res.data:
        st.warning("Aucune activité trouvée.")
        return
        
    df = pd.DataFrame(res.data)
    
    # Préparation des données
    df['start_date'] = pd.to_datetime(df['start_date'])
    df['year'] = df['start_date'].dt.year
    df['month_num'] = df['start_date'].dt.month
    df['month'] = df['start_date'].dt.month_name()
    
    # Conversion forcée en numérique + calculs
    df['distance_km'] = pd.to_numeric(df['distance_km'], errors='coerce').fillna(0)
    df['total_elevation_gain'] = pd.to_numeric(df['total_elevation_gain'], errors='coerce').fillna(0)
    df['moving_time'] = pd.to_numeric(df['moving_time'], errors='coerce').fillna(0)
    df['moving_time_hr'] = df['moving_time'] / 3600
    
    # Calcul de la pente moyenne (gradient)
    df['gradient'] = (df['total_elevation_gain'] / (df['distance_km'].replace(0, pd.NA) * 1000)) * 100
    df['gradient'] = df['gradient'].fillna(0)
    
    # Extraction des listes uniques pour les filtres
    all_years = sorted(df['year'].unique().tolist(), reverse=True)
    current_year = datetime.datetime.now().year
    # Définition de l'année par défaut (Année en cours si présente, sinon la plus récente)
    default_year = [current_year] if current_year in all_years else [all_years[0]]

    # Dictionnaire pour trier les mois correctement
    months_order = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin', 
        7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }
    df['month'] = df['month_num'].map(months_order)
    present_months_nums = sorted(df['month_num'].unique().tolist())
    all_months = [months_order[m] for m in present_months_nums]
    
    all_types = sorted(df['type'].unique().tolist())

    # --- 2. ZONE DE FILTRES ---
    with st.expander("🛠️ Filtres", expanded=True):
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1: selected_years = render_filter_ui("Années", all_years, "years", default_val=default_year)
        with f_col2: selected_months = render_filter_ui("Mois", all_months, "months", default_val=all_months)
        with f_col3: selected_types = render_filter_ui("Sports", all_types, "types", default_val=all_types)

    # Si rien n'est sélectionné, on arrête l'affichage ici
    if not selected_years or not selected_months or not selected_types:
        st.info("Veuillez sélectionner au moins une année, un mois et un sport pour voir les statistiques.")
        return

    # Application des filtres
    df_filtered = df[
        (df['year'].isin(selected_years)) & 
        (df['month'].isin(selected_months)) & 
        (df['type'].isin(selected_types))
    ].copy()

    if df_filtered.empty:
        st.warning("Aucune activité ne correspond à ces critères.")
        return

    # 5.2 STACKED BAR CHART
    with st.expander("📊 Cumul Annuel & Mensuel", expanded=False):
        metric_choice = st.segmented_control(
            "Donnée à afficher (Axe Y)", 
            options=["Distance (km)", "Dénivelé (m)", "Temps (heures)"],
            default="Distance (km)"
        )
        
        if metric_choice == "Distance (km)":
            y_col = 'distance_km'
            tooltip_format = '.1f'
        elif metric_choice == "Dénivelé (m)":
            y_col = 'total_elevation_gain'
            tooltip_format = '.0f'
        else:
            y_col = 'moving_time_hr'
            tooltip_format = '.1f'

        # Agrégation des données pour le graphique
        df_agg = df_filtered.groupby(['year', 'month', 'month_num'])[y_col].sum().reset_index()
        
        # Conversion de l'année en string pour éviter l'affichage de type "2,024"
        df_agg['year'] = df_agg['year'].astype(str)
        color_scale = alt.Scale(scheme='reds')
        stacked_bar = alt.Chart(df_agg).mark_bar().encode(
            x=alt.X('year:N', title='Année'),
            y=alt.Y(f'{y_col}:Q', title=metric_choice),
            # On utilise le mois pour la couleur, et on trie selon le numéro du mois (month_num)
            # On utilise month:N pour la légende mais on scale sur month_num pour le dégradé
            color=alt.Color(
                'month:N', 
                title='Mois', 
                sort=alt.EncodingSortField(field='month_num', order='ascending'),
                scale=color_scale
            ),
            # L'ASTUCE EST ICI : on force l'ordre d'empilement sur month_num
            order=alt.Order('month_num:O', sort='ascending'),
            tooltip=[
                alt.Tooltip('year:N', title='Année'),
                alt.Tooltip('month:N', title='Mois'),
                alt.Tooltip(f'{y_col}:Q', title=metric_choice, format=tooltip_format)
            ]
        ).properties(height=500).interactive()
        
        st.altair_chart(stacked_bar, use_container_width=True)

    # 5.1 SCATTER PLOT EPIC RIDES (Réutilisation de la fonction existante)
    with st.expander("🌌 Km / D+", expanded=False):
        render_epic_rides_scatter(df_filtered)

    # --- 3. MÉTRIQUES RECORD ---
    with st.expander("🏆 Records (sur la sélection)", expanded=False):
        # Max calculs
        max_dist = df_filtered['distance_km'].max()
        max_elev = df_filtered['total_elevation_gain'].max()
        max_time_sec = df_filtered['moving_time'].max()
        max_grad = df_filtered['gradient'].max()

        # Logique Eddington : "Si Ride est dans la liste des sports sélectionnés"
        show_eddington = "Ride" in selected_types
        
        # Affichage dynamique des colonnes
        cols_metric = st.columns(5 if show_eddington else 4)
        
        col_idx = 0
        if show_eddington:
            # IMPORTANT : On calcule l'Eddington uniquement sur les activités 'Ride' 
            # présentes dans le dataframe déjà filtré par année/mois
            df_rides_only = df_filtered[df_filtered['type'] == "Ride"]
            edd = calculate_eddington(df_rides_only['distance_km'])
            with cols_metric[col_idx]:
                render_stat_card("🎩", "Eddington", f"{edd}", "Vélo uniquement", "#9b59b6")
            col_idx += 1
            
        with cols_metric[col_idx]:
            render_stat_card("📏", "Max Distance", f"{max_dist:.1f} km", "", "#3498db")
        with cols_metric[col_idx+1]:
            render_stat_card("⛰️", "Max Dénivelé", f"{max_elev:.0f} m", "", "#e67e22")
        with cols_metric[col_idx+2]:
            render_stat_card("⏱️", "Max Durée", format_time(max_time_sec), "", "#2ecc71")
        with cols_metric[col_idx+3]:
            render_stat_card("📈", "Max Pente", f"{max_grad:.1f} %", "Moyenne", "#e74c3c")

  
    with st.expander("📋 Le Top 10 en détail", expanded=False):
    # --- 4. TABLEAUX TOP 5 ---
    #st.subheader("📋 Le Top 5 en détail")
    
        df_filtered['strava_url'] = "https://www.strava.com/activities/" + df_filtered['id_activity'].astype(str)
        df_filtered['date_str'] = df_filtered['start_date'].dt.strftime('%d/%m/%Y')
        df_filtered['duree_str'] = df_filtered['moving_time'].apply(format_time)
        
        # Configuration commune pour st.dataframe
        base_cols = ['date_str', 'name']
        col_config = {
            "date_str": "Date",
            "name": "Activité",
            "distance_km": st.column_config.NumberColumn("Km", format="%.1f"),
            "total_elevation_gain": st.column_config.NumberColumn("D+ (m)", format="%d"),
            "duree_str": "Durée",
            "gradient": st.column_config.NumberColumn("Pente (%)", format="%.1f"),
            "strava_url": st.column_config.LinkColumn("Lien", display_text="🔗")
        }

        #t1, t2 = st.columns(2)
        #with t1:
        st.markdown("**📏 Top distance**")
        st.dataframe(df_filtered.nlargest(10, 'distance_km')[base_cols + ['distance_km', 'strava_url']], 
                    hide_index=True, use_container_width=True, column_config=col_config)
        
        st.markdown("**⏱️ Top durée**")
        st.dataframe(df_filtered.nlargest(10, 'moving_time')[base_cols + ['duree_str', 'strava_url']], 
                    hide_index=True, use_container_width=True, column_config=col_config)
                        
        #with t2:
        st.markdown("**⛰️ Top dénivelé**")
        st.dataframe(df_filtered.nlargest(10, 'total_elevation_gain')[base_cols + ['total_elevation_gain', 'strava_url']], 
                    hide_index=True, use_container_width=True, column_config=col_config)
                    
        st.markdown("**📈 Top pente moyenne**")
        st.dataframe(df_filtered.nlargest(10, 'gradient')[base_cols + ['gradient', 'strava_url']], 
                    hide_index=True, use_container_width=True, column_config=col_config)

    
    
    