import streamlit as st
import pandas as pd
import altair as alt
from strava_operations import *
from db_operations import *

def render_tab_stats(texts):
    """Contenu de l'onglet Statistiques Personnelles."""
    # --- STATS MACROS ---
    total_db = st.session_state.get('total_activities', 0)
    athlete = st.session_state.athlete
    result = get_strava_stats(st.session_state.access_token, athlete.get('id'))
    if isinstance(result, tuple) and len(result) == 2:
        stats_string, total_strava = result
        st.info(f"{stats_string}, total: {total_db}")

    if 'last_activities' in st.session_state and st.session_state.last_activities:
        st.subheader(texts["last_activities"])
        df_p = pd.DataFrame(st.session_state.last_activities)
        
        if 'distance_km' not in df_p.columns:
            df_p['distance_km'] = df_p['distance'] / 1000
        
        df_p['start_date'] = pd.to_datetime(df_p['start_date'])
        df_p['strava_url'] = "https://www.strava.com/activities/" + df_p['id_activity'].astype(str)

        chart = alt.Chart(df_p).mark_bar(cursor='pointer').encode(
            x=alt.X('start_date:T', title='Date'),
            y=alt.Y('distance_km:Q', title='Distance (km)'),
            #href='strava_url:N',
            tooltip=[
                alt.Tooltip('name:N', title='Nom'),
                alt.Tooltip('distance_km:Q', title='Distance (km)', format='.1f'),
                alt.Tooltip('start_date:T', title='Date', format='%Y-%m-%d') 
            ]
        ).properties(height=400).configure_mark(invalid=None).interactive()

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(df_p[['start_date', 'name', 'distance_km', 'type']], use_container_width=True)

def common_critria(key_id):
    # --- 1. SÉLECTION DU GROUPE ---
    athlete_id = st.session_state.athlete['id']
    m_groups = get_user_memberships(athlete_id)
    my_approved = [g for g in m_groups.data if g['status'] == 'approved']
    
    if not my_approved:
        st.info(texts["no_group"])
        return
    
    group_dict = {g['groups']['name']: g for g in my_approved}
    group_names = list(group_dict.keys())

    # Sélection Groupe et Année
    c_sel1, c_sel2 = st.columns(2)
    with c_sel1:
        selected_name = st.pills(
            "Groupe", 
            options=group_names, 
            selection_mode="single", 
            default=group_names[0],
            key="pills_group" + key_id
        )
    selected_g = group_dict[selected_name]

    with c_sel2:
        years = get_years_for_group(selected_g['group_id'])
        if years:
            selected_year = st.pills("Année", years, selection_mode="single", default=years[0], key="pills_year"+key_id)
        else:
            selected_year = 2026   
    return selected_g, selected_year