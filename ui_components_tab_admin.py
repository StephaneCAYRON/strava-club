import sys
import io
import streamlit as st
from contextlib import redirect_stdout
from cron_sync import nightly_sync
from db_operations import *
from strava_operations import *

def render_tab_admin(texts):
    st.title("🛠️ Console d'Administration")
    
    # --- STATS GÉNÉRALES ---
    col1, col2, col3 = st.columns(3)
    
    total_users = supabase.table("profiles").select("id_strava", count="exact").execute().count
    total_acts = supabase.table("activities").select("id_activity", count="exact").execute().count
    
    col1.metric("Membres inscrits", total_users)
    col2.metric("Activités totales", total_acts)
    col3.metric("État du Cron", "❌ KO")

    # --- LISTE DES MEMBRES ET DERNIÈRE ACTIVITÉ ---
    st.subheader("État des membres")
    
    # Note: Si tu ne veux pas faire de RPC SQL, on peut le faire en Pandas
    res = supabase.table("profiles").select("firstname, lastname, id_strava, avatar_url").execute()
    df_admin = pd.DataFrame(res.data)
    # Créer l'URL du profil Strava à partir de l'ID
    df_admin['strava_link'] = df_admin['id_strava'].apply(lambda x: f"https://www.strava.com/athletes/{x}")
    # 3. Organisation des colonnes
    df_admin = df_admin[['firstname', 'lastname', 'strava_link', 'id_strava']]
    df_admin = df_admin.sort_values(by="lastname", ascending=True)
    # 4. Affichage avec configuration avancée
    nb_lignes = len(df_admin)
    hauteur_calculee = (nb_lignes * 35) + 40

    st.dataframe(
        df_admin,
        use_container_width=True,
        hide_index=True,
        height=hauteur_calculee,
        column_config={
            "avatar": st.column_config.ImageColumn("Photo", width="small"),
            "firstname": "Prénom",
            "lastname": "Nom",
            "strava_link": st.column_config.LinkColumn(
                "Profil Strava",
                help="Cliquer pour ouvrir le profil Strava",
                validate=r"^https://www.strava.com/athletes/.*",
                display_text="🔗 Voir sur Strava" # Tu peux mettre une icône ou un texte
            ),
            "id_strava": st.column_config.TextColumn("ID Strava")
        }
    )
    
    
    #st.dataframe(df_admin, use_container_width=True)

    # --- SECTION SYNCHRO ---
    st.subheader("Synchronisation Manuelle")
    st.info("Ce bouton lance la même procédure que le script qui s'exécute toutes les 2 heures (Refresh tokens + Upsert + Cleanup).")

    # 1. AJOUT DE LA CHECKBOX
    # On utilise le session_state pour que la valeur survive au rerun du bouton
    is_partial_sync = st.checkbox(
        "🔄 Partial Sync (derniers jours)", 
        value=True,
        help="Si décoché, récupère toutes les activités. Si coché, synchro partielle (derniers jours)."
    )
    st.info(f"Le bouton lancera : `nightly_sync({is_partial_sync})`.")

    # Initialisation de l'état du bouton
    if "sync_running" not in st.session_state:
        st.session_state.sync_running = False

    # Le bouton se désactive si la synchro est en cours
    btn_label = "⏳ Synchro en cours..." if st.session_state.sync_running else "🚀 Lancer la synchro"
    
    if st.button(btn_label, disabled=st.session_state.sync_running):
        st.session_state.sync_running = True
        st.rerun()

    # Si on vient de cliquer sur le bouton
    if st.session_state.sync_running:
        st.write("---")
        # Utilisation de st.status pour un affichage moderne
        with st.status("Exécution de la synchronisation...", expanded=True) as status:
            log_area = st.empty() # Zone de texte pour les logs
            output = io.StringIO()
            
            try:
                # Redirection des print vers le buffer
                with redirect_stdout(output):
                    # On exécute le script
                    # Note: pour du vrai temps réel ligne par ligne, 
                    # il faudrait modifier nightly_sync en generateur, 
                    # mais redirect_stdout fonctionne très bien ici.
                    
                    nightly_sync(is_partial_sync)
                    
                # Affichage final des logs dans un bloc de code
                log_area.code(output.getvalue())
                status.update(label="✅ Synchronisation terminée avec succès !", state="complete", expanded=False)
                
            except Exception as e:
                st.error(f"Une erreur est survenue : {e}")
                status.update(label="❌ Erreur lors de la synchronisation", state="error")
            
            finally:
                # On réactive le bouton
                st.session_state.sync_running = False
                if st.button("Réinitialiser le bouton"):
                    st.rerun()

    # --- SECTION INFO SYSTÈME ---
    st.write("---")
    st.subheader("💡 Rappel technique")
    st.caption("""
    - **GitHub Actions** : Le script tourne aussi automatiquement toutes les 2h.
    - **Cleanup** : Les activités supprimées sur Strava <TODO> sont retirées de Supabase lors de cette synchro<TODO>.
    - **Tokens** : Les refresh tokens sont mis à jour en base à chaque passage.
    """)