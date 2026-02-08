import streamlit as st
import pandas as pd
import altair as alt
import datetime
from db_operations import get_leaderboard_by_group_by_year
from ui_components import common_critria
from strava_operations import *

def render_tab_sunday(texts):
    st.markdown("### 🥐 Challenge Sorties Dominicales")
    st.caption("""
    **Règle  :** Chaque dimanche, le club met en jeu **30 points**. 
    Ces points sont partagés équitablement entre tous les membres ayant réalisé la sortie club.
    **Critères de validation de la sortie :** un Dimanche :-), départ : Entre 05h00 et 09h30, Distance : > 50 km.
    Si vous êtes peu à braver la météo, c'est le **JACKPOT**.""")

    # --- 1. SÉLECTION ET DONNÉES ---
    # On récupère les filtres (Groupe, Année, Mois)
    # Note : Pour un challenge cumulatif, le filtre "Mois" servira surtout à filtrer le tableau détaillé
    selected_g, selected_year = common_critria("sunday_challenge")
    
    # Ajout manuel d'un filtre mois si tu le souhaites, sinon on peut utiliser celui de common_critria s'il renvoie le mois
    # Pour simplifier ici, je recalcule sur l'année complète pour avoir la courbe, et on filtrera l'affichage après.
    
    if selected_g == "":
        st.info("Veuillez sélectionner un groupe.")
        return

    # On récupère toutes les activités de l'année pour le groupe
    res = get_leaderboard_by_group_by_year(selected_g['group_id'], selected_year)
    
    if not res.data:
        st.info(f"Aucune activité trouvée pour {selected_year}.")
        return

    df = pd.DataFrame(res.data)
    
    # --- 2. FILTRAGE DES ACTIVITÉS (LE CŒUR DU SYSTÈME) ---
    
    # A. Conversion des dates
    df['start_date'] = pd.to_datetime(df['start_date'])
    # On s'assure que c'est le fuseau local ou UTC selon ta BDD, ici on suppose que start_date est bon.
    # Si besoin de convertir en heure locale France : .dt.tz_convert('Europe/Paris') si la donnée est timezone-aware.

    # B. Filtre : C'est un Dimanche (Sunday = 6)
    df = df[df['start_date'].dt.dayofweek == 6]

    # C. Filtre : Heure de départ entre 05:00 et 09:30
    # On crée une colonne temporaire 'time'
    df['time'] = df['start_date'].dt.time
    start_limit = datetime.time(5, 0, 0)
    end_limit = datetime.time(9, 30, 0)
    
    df = df[(df['time'] >= start_limit) & (df['time'] <= end_limit)]

    # D. Filtre : Distance > 50km (50000m)
    df = df[df['distance_km'] >= 50] # Supposant que ta vue SQL renvoie des km, sinon /1000

    if df.empty:
        st.warning("Aucune sortie dominicale éligible trouvée pour ces critères.")
        return

    # --- 3. CALCUL DES POINTS (ALGORITHME DE RÉPARTITION) ---
    
    # On groupe par date (chaque dimanche unique)
    # On prend .dt.date pour ignorer l'heure exacte
    df['date_only'] = df['start_date'].dt.date
    
    sunday_stats = []
    
    # Pour chaque dimanche unique trouvé
    unique_sundays = df['date_only'].unique()
    
    # DataFrame global pour accumuler les points par athlète
    athlete_scores = []

    for d in sorted(unique_sundays):
        # Les participants de ce dimanche
        participants = df[df['date_only'] == d]
        
        # Nombre de participants
        nb_part = len(participants)
        
        # Points par personne (30 / N)
        points_per_person = 30 / nb_part
        
        # On stocke l'historique de ce dimanche
        names_list = ", ".join(participants['firstname'].tolist())
        sunday_stats.append({
            'Date': d,
            'Points Distribués': 30,
            'Participants': nb_part,
            'Gain par athlète': round(points_per_person, 2),
            'Athlètes': names_list
        })
        
        # On attribue les points aux athlètes
        for _, row in participants.iterrows():
            athlete_scores.append({
                'date': d,
                'id_strava': row['id_strava'],
                'firstname': row['firstname'],
                'avatar_url': row['avatar_url'],
                'points': points_per_person
            })

    df_scores = pd.DataFrame(athlete_scores)
    df_history = pd.DataFrame(sunday_stats).sort_values('Date', ascending=False)

    # --- 4. AFFICHAGE : PODIUM (TOP 3) ---
    
    # Calcul du total par athlète
    leaderboard = df_scores.groupby(['id_strava', 'firstname', 'avatar_url'])['points'].sum().reset_index()
    leaderboard = leaderboard.sort_values('points', ascending=False).reset_index(drop=True)

    #st.markdown("#### 🏆 Le Podium Dominical")
    
    cols = st.columns(3)
    medals = ["🥇", "🥈", "🥉"]
    
    for i in range(min(3, len(leaderboard))):
        row = leaderboard.iloc[i]
        with cols[i]:
            #st.markdown(f"<div style='text-align:center'>{medals[i]} <b>{row['firstname']}</b></div>", unsafe_allow_html=True)
            st.markdown(f"**{medals[i]} {row['firstname']}**")
            st.image(get_safe_avatar_url(row['avatar_url']), width=50)
            # Affichage de l'avatar rond
            """
            st.markdown(
                f"'
                <div style="display: flex; justify-content: center; margin-bottom: 10px;">
                    <img src="{row['avatar_url']}" style="width: 80px; height: 80px; border-radius: 50%; border: 3px solid #E62E2D;">
                </div>
                '", 
                unsafe_allow_html=True
            )
            """
            st.metric(label="Total Points", value=f"{row['points']:.1f}")

    st.divider()

    # --- 4.5 AFFICHAGE : CLASSEMENT GÉNÉRAL COMPLET ---
    st.markdown("#### 📊 Classement Général")

    # 1. On calcule le nombre de sorties (assiduité)
    assiduite = df_scores.groupby('id_strava').size().reset_index(name='total_rides')
    
    # 2. On fusionne avec le leaderboard (qui contient déjà points et avatar)
    leaderboard = pd.merge(leaderboard, assiduite, on='id_strava')
    leaderboard = leaderboard.sort_values('points', ascending=False).reset_index(drop=True)

    # 3. Préparation des colonnes pour le style demandé
    nb_lignes = len(leaderboard)
    hauteur_calculee = (nb_lignes * 35) + 40

    # Création de la colonne combinée Rang + Prénom
    leaderboard['Athlete'] = [
        f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'#{i+1}'} {row['firstname']}"
        for i, row in leaderboard.iterrows()
    ]

    # 4. Affichage avec ImageColumn
    st.dataframe(
        leaderboard[['avatar_url', 'Athlete', 'points', 'total_rides']], 
        hide_index=True,
        use_container_width=True,
        height=hauteur_calculee,
        column_config={
            "avatar_url": st.column_config.ImageColumn("", width="small"),
            "Athlete": st.column_config.TextColumn("Rang & Nom"),
            "points": st.column_config.NumberColumn("Total Points", format="%.1f pts"),
            "total_rides": st.column_config.NumberColumn("Dimanches", format="%d 🥐")
        }
    )


    # --- 5. AFFICHAGE : GRAPHIQUE CUMULATIF ---
    st.markdown("#### 📈 La Course aux Points")
    
    # On doit calculer la somme cumulative pour chaque athlète au fil du temps
    # 1. Pivot ou Groupby date + athlète
    df_cumul = df_scores.groupby(['date', 'firstname'])['points'].sum().reset_index()
    df_cumul['date'] = pd.to_datetime(df_cumul['date'])
    
    # 2. On trie par date
    df_cumul = df_cumul.sort_values('date')
    
    # 3. CumSum par athlète
    df_cumul['cum_points'] = df_cumul.groupby('firstname')['points'].cumsum()

    # Graphique Altair
    chart = alt.Chart(df_cumul).mark_line(point=True).encode(
        x=alt.X('date:T', title='Date', axis=alt.Axis(format='%d %b')),
        y=alt.Y('cum_points:Q', title='Points Cumulés'),
        color=alt.Color('firstname:N', title='Athlète'),
        tooltip=['date', 'firstname', alt.Tooltip('cum_points', format='.1f')]
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    # --- 6. AFFICHAGE : TABLEAU DÉTAILLÉ (VUE PAR ATHLÈTE) ---
    st.divider()
    st.markdown("#### 📅 Détail des participations (vérifiez votre sortie)")

    # 1. Préparation des données "Contexte" (Le pot et le nombre de participants du jour)
    # On ne garde que les colonnes utiles de df_history pour éviter les doublons
    df_context = df_history[['Date', 'Points Distribués', 'Participants']]

    # 2. Fusion avec la liste individuelle des athlètes (df_scores)
    # On joint sur la date. df_scores contient déjà 'firstname' et 'points'
    df_detailed_view = pd.merge(
        df_scores, 
        df_context, 
        left_on='date', 
        right_on='Date', 
        how='left'
    )

    # 3. Nettoyage et Tri
    # On garde : Date, Pot, Nb Participants, Gain Perso, Nom de l'athlète
    df_final = df_detailed_view[['Date', 'Points Distribués', 'Participants', 'points', 'firstname']]
    
    # Tri : Date décroissante (plus récent en haut), puis alphabétique pour les noms
    df_final = df_final.sort_values(by=['Date', 'firstname'], ascending=[False, True])

    # 4. Affichage
    # Calcul dynamique de la hauteur
    nb_lignes = len(df_final)
    hauteur_calculee = min((nb_lignes * 35) + 40, 600) # On met un max à 600px pour éviter un scroll infini

    st.dataframe(
        df_final,
        use_container_width=True,
        height=hauteur_calculee,
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "Points Distribués": st.column_config.NumberColumn("Pot (Pts)", format="%d"),
            "Participants": st.column_config.NumberColumn("Cyclistes", format="%d 🚴"),
            "points": st.column_config.NumberColumn("Gain", format="%.2f pts"),
            "firstname": st.column_config.TextColumn("Athlète Présent", width="medium"),
        }
    )