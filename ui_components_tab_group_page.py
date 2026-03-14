import streamlit as st
import pandas as pd
from db_operations import get_leaderboard_by_group_by_year_cached, get_years_for_group
from ui_components import make_display_names
from ui_components_achievements import render_group_milestones
    
def render_tab_group_page(texts, group_info):
    """Page dédiée à un groupe : nom, critères année/mois, tableau [membre, km cumulés, D+ cumulé] et total mis en avant."""
    group_id = group_info["group_id"]
    group_name = group_info["groups"]["name"]

    #st.subheader(group_name)
    st.subheader(f"🎖️ Nos exploits collectifs")

    years = get_years_for_group(group_id)
    if not years:
        st.info("Aucune donnée pour ce groupe.")
        return

    selected_year = st.pills(
        "Année",
        years,
        selection_mode="single",
        default=years[0],
        key=f"group_page_year_{group_id}",
    )

    res = get_leaderboard_by_group_by_year_cached(group_id, selected_year)
    if not res.data:
        st.info("Aucune donnée pour cette période.")
        return

    df = pd.DataFrame(res.data)
    display_names_map = make_display_names(df)
    df['display_name'] = df['id_strava'].map(display_names_map)
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["Year"] = df["start_date"].dt.year
    df["Mois"] = df["start_date"].dt.month_name()
    df["Mois_Num"] = df["start_date"].dt.month

    df_year = df[df["Year"] == selected_year]
    months_in_data = df_year.sort_values("Mois_Num")["Mois"].unique().tolist()
    option_all = texts["all_year"]
    options_list = [option_all] + months_in_data

    selected_period = st.segmented_control(
        "",
        options_list,
        selection_mode="single",
        default=options_list[0],
        key=f"group_page_month_{group_id}",
    )

    if selected_period == option_all:
        df_final = df_year
        title_suffix = f"{selected_year}"
    else:
        df_final = df_year[df_year["Mois"] == selected_period]
        title_suffix = f"{selected_period} {selected_year}"

    leaderboard = (
        df_final.groupby(["id_strava", "display_name", "avatar_url"])
        .agg(
            km_cumules=("distance_km", "sum"),
            dplus_cumule=("total_elevation_gain", "sum"),
        )
        .sort_values("km_cumules", ascending=False)
        .reset_index()
    )

    leaderboard = leaderboard.rename(
        columns={
            "display_name": "Membre",
            "km_cumules": "Km cumulés",
            "dplus_cumule": "D+ cumulé (m)",
        }
    )

    st.markdown(f"**Période :** {title_suffix}")

    total_km = leaderboard["Km cumulés"].sum()
    total_dplus = leaderboard["D+ cumulé (m)"].sum()

    render_group_milestones(total_km, total_dplus, group_name)

    display_df = leaderboard[["Membre", "Km cumulés", "D+ cumulé (m)"]]
    nb_lignes = len(display_df)
    hauteur_calculee = (nb_lignes * 35) + 40
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=hauteur_calculee,
        column_config={
            "Membre": st.column_config.TextColumn("Membre", width="medium"),
            "Km cumulés": st.column_config.NumberColumn("Km cumulés", format="%.1f km"),
            "D+ cumulé (m)": st.column_config.NumberColumn("D+ cumulé (m)", format="%.0f m"),
        },
    )
    """
    st.markdown(
        f'<div style="background-color: #e8f5e9; padding: 12px; border-radius: 8px; margin-top: 12px;">'
        f'<strong>Total groupe</strong> — Km cumulés : <strong>{total_km:.1f} km</strong> — '
        f'D+ cumulé : <strong>{total_dplus:.0f} m</strong>'
        f"</div>",
        unsafe_allow_html=True,
    )
    """
   
