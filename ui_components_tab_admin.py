import sys
import io
import streamlit as st
from contextlib import redirect_stdout
from cron_sync import nightly_sync, sync_single_athlete
from db_operations import *
from strava_operations import *
import pandas as pd

def render_tab_admin(texts):
    st.title("🛠️ Console d'Administration")
    
    # --- STATS GÉNÉRALES ---
    col1, col2, col3 = st.columns(3)
    
    total_users = supabase.table("profiles").select("id_strava", count="exact").execute().count
    total_acts = supabase.table("activities").select("id_activity", count="exact").execute().count
    
    col1.metric("Membres inscrits", total_users)
    col2.metric("Activités totales", total_acts)
    #col3.metric("État du Cron", "❌ KO")
    
    # --- LISTE DES MEMBRES ET DERNIÈRE ACTIVITÉ ---
    st.subheader("Utilisateurs")
    
    res = supabase.table("profiles").select("*").execute()
    df_admin = pd.DataFrame(res.data).sort_values(by="lastname")
    
    df_view = df_admin.copy()
    df_view['strava_link'] = df_view['id_strava'].apply(lambda x: f"https://www.strava.com/athletes/{x}")
    if "last_login" in df_view.columns:
        df_view["dernière_connexion"] = pd.to_datetime(df_view["last_login"], utc=True).dt.tz_convert(None).dt.strftime("%d/%m/%Y %H:%M")
    else:
        df_view["dernière_connexion"] = "—"
        
    cols = ['firstname', 'lastname', 'nb_connection','dernière_connexion', 'strava_link', 'id_strava']
    df_view = df_view[[c for c in cols if c in df_view.columns]].sort_values(by="lastname", ascending=True)
    
    hauteur_calculee = (len(df_view) * 35) + 40

    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        height=hauteur_calculee,
        column_config={
            "firstname": "Prénom",
            "lastname": "Nom",
            "nb_connection": st.column_config.NumberColumn("🚀 Connexions", format="%d"),
            "dernière_connexion": st.column_config.TextColumn("Dernière connexion", width="medium"),
            "strava_link": st.column_config.LinkColumn("Profil Strava", display_text="🔗 Voir sur Strava"),
            "id_strava": st.column_config.TextColumn("ID Strava")
        }
    )

    # --- SECTION SYNCHRO INDIVIDUELLE ---
    st.write("---")
    st.subheader("👤 Synchronisation Individuelle")
    st.caption("Sélectionnez un athlète pour mettre à jour uniquement ses données.")
    
    # Préparation du dictionnaire pour le selectbox (Nom -> Profil Complet)
    athlete_dict = {f"{row['firstname']} {row['lastname']} (ID: {row['id_strava']})": row for _, row in df_admin.iterrows()}
    selected_athlete_name = st.selectbox("Choisir un athlète :", list(athlete_dict.keys()))
    
    col_btn1, col_btn2 = st.columns(2)
    selected_profile = athlete_dict[selected_athlete_name]

    if col_btn1.button(f"🔄 Sync Partielle pour {selected_profile['firstname']}", use_container_width=True):
        with st.spinner("Synchronisation partielle en cours..."):
            success, msg = sync_single_athlete(selected_profile, is_partial=True)
            if success: st.success(msg)
            else: st.error(msg)

    if col_btn2.button(f"🚀 FULL Sync pour {selected_profile['firstname']}", type="primary", use_container_width=True):
        with st.spinner("Récupération de l'historique complet (peut prendre du temps)..."):
            # On passe force_full=True pour contourner les limites éventuelles
            success, msg = sync_single_athlete(selected_profile, is_partial=False)
            if success: st.success(msg)
            else: st.error(msg)


    # --- SECTION SYNCHRO GLOBALE ---
    st.write("---")
    st.subheader("🌍 Synchronisation, tous les utilisateurs)")
    is_partial_sync = st.checkbox("🔄 Partial Sync si coché (derniers jours uniquement)", value=True)

    if "sync_running" not in st.session_state:
        st.session_state.sync_running = False

    btn_label = "⏳ Synchro en cours..." if st.session_state.sync_running else "Lancer la synchro"
    
    if st.button(btn_label, disabled=st.session_state.sync_running):
        st.session_state.sync_running = True
        st.rerun()

    if st.session_state.sync_running:
        with st.status(f"Exécution de la synchronisation...Partial sync={is_partial_sync}", expanded=True) as status:
            log_area = st.empty()
            output = io.StringIO()
            try:
                with redirect_stdout(output):
                    nightly_sync(is_partial_sync)
                log_area.code(output.getvalue())
                status.update(label="✅ Synchronisation terminée !", state="complete", expanded=False)
            except Exception as e:
                st.error(f"Erreur globale : {e}")
                status.update(label="❌ Erreur", state="error")
            finally:
                st.session_state.sync_running = False
                if st.button("Réinitialiser l'interface"):
                    st.rerun()

    st.write("---")
    st.subheader("💡 Rappel technique")
    st.caption("- Le script complet tourne automatiquement en tâche de fond.\n- La synchronisation individuelle met à jour les tokens à la volée.")