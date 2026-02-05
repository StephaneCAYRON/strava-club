import streamlit as st
import pandas as pd
import altair as alt
from strava_operations import *
from db_operations import *
from ui_components import common_critria

def render_tab_dplus(texts):
    """Contenu de l'onglet Leaderboard avec Cumul du dénivelé (D+) pour l'année"""
    
    # --- 1. SÉLECTION GROUPE et ANNEE ---
    selected_g, selected_year = common_critria("dplus")

    if selected_g == "":
        st.info("No group yet")
        return

    res = get_leaderboard_by_group_by_year(selected_g['group_id'], selected_year)
    
    if res.data:
        df = pd.DataFrame(res.data)
        
        # Traitement Date
        df['start_date'] = pd.to_datetime(df['start_date'])
        df['Year'] = df['start_date'].dt.year
        df['Mois'] = df['start_date'].dt.month_name()
        df['Mois_Num'] = df['start_date'].dt.month
    
        df_year = df[df['Year'] == selected_year]

        months_in_data = df_year.sort_values('Mois_Num')['Mois'].unique().tolist()
        
        option_all = texts["all_year"]
        options_list = [option_all] + months_in_data
        
        # Sélection par défaut : toute l'année
        selected_period = st.segmented_control("Mois", options_list, selection_mode="single", default=options_list[0])

        # --- LOGIQUE DE FILTRAGE ---
        if selected_period == option_all:
            df_final = df_year
            title_suffix = f"{selected_year}"
        else:
            df_final = df_year[df_year['Mois'] == selected_period]
            title_suffix = f"{selected_period} {selected_year}"

        # --- CLASSEMENT (AGGRÉGATION MULTIPLE) ---
        # Note: 'total_elevation_gain' est le nom standard Strava pour le D+
        leaderboard = df_final.groupby(['id_strava','firstname', 'avatar_url']).agg(
            total_dplus=('total_elevation_gain', 'sum'),
            total_rides=('total_elevation_gain', 'count') 
        ).sort_values('total_dplus', ascending=False).reset_index()

        st.markdown(f"### Cumul dénivelé : {title_suffix}")
        
        if not leaderboard.empty:
            
            # --- TOP 3 ---
            for i, row in leaderboard.iterrows():
                rank_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
                avatar = get_safe_avatar_url(row['avatar_url'])
                
                c1, c2, c3 = st.columns([1, 4, 2])
                
                with c1:
                    st.image(avatar, width=50)
                
                with c2:
                    st.markdown(f"**{rank_icon} {row['firstname']}**")
                    st.caption(f"{row['total_rides']} {texts['rides']}")
                with c3:
                    strava_profile_url = f"https://www.strava.com/athletes/{row['id_strava']}"
                    strava_icon = "https://www.strava.com/favicon.ico"
                    st.markdown(
                        f"**{int(row['total_dplus'])}** m "
                        f'<a href="{strava_profile_url}" target="_blank">'
                        f'<img src="{strava_icon}" width="15" style="margin-left: 5px; margin-bottom: 3px;">'
                        f'</a>', 
                        unsafe_allow_html=True
                    )
                if i == 2:    
                    break

            # --- 6. GRAPHIQUE D'ÉVOLUTION CUMULÉE ---
            st.write("")
            st.subheader("Progression mensuelle (D+)")

            # 1. Groupe par athlète et mois (Somme du D+)
            df_chart = df_year.groupby(['firstname', 'Mois_Num', 'Mois'])['total_elevation_gain'].sum().reset_index(name='monthly_sum')

            # 2. Cumul par athlète
            df_chart = df_chart.sort_values(['firstname', 'Mois_Num'])
            df_chart['cumul_dplus'] = df_chart.groupby('firstname')['monthly_sum'].cumsum()

            # 3. Création du graphique Altair
            line_chart = alt.Chart(df_chart).mark_line(point=True).encode(
                x=alt.X('Mois_Num:O', title="Mois", axis=alt.Axis(labelAngle=0)),
                y=alt.Y('cumul_dplus:Q', title="Dénivelé cumulé (m)"),
                color=alt.Color('firstname:N', title="Athlète"),
                tooltip=['firstname', 'Mois', alt.Tooltip('cumul_dplus:Q', format=',.0f', title="Cumul D+ (m)")]
            ).properties(
                height=500
            ).interactive()

            st.altair_chart(line_chart, use_container_width=True)    

            # --- TABLEAU COMPLET ---
            with st.expander("Classement complet", True):
                leaderboard['Athlete'] = [
                    f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'#{i+1}'} {row['firstname']}"
                    for i, row in leaderboard.iterrows()
                ]
                st.dataframe(
                    leaderboard[['avatar_url','Athlete', 'total_dplus', 'total_rides']], 
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "avatar_url": st.column_config.ImageColumn("", width=10),
                        "Athlete": st.column_config.TextColumn("Rang & Nom"),
                        "total_dplus": st.column_config.NumberColumn("Dénivelé (m)", format="%d m"),
                        "total_rides": st.column_config.NumberColumn("Sorties")
                    }
                )
        else:
            st.warning("Aucune activité trouvée pour cette période.")

    else:
        st.info("Aucune donnée disponible pour ce groupe.")