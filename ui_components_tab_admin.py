import sys
import io
import streamlit as st
from contextlib import redirect_stdout
from cron_sync import nightly_sync

def render_tab_admin(texts):
    st.title("🛠️ Console d'Administration")
    
    # --- SECTION SYNCHRO ---
    st.subheader("Synchronisation Manuelle")
    st.info("Ce bouton lance la même procédure que le script qui s'exécute toutes les 2 heures (Refresh tokens + Upsert + Cleanup).")

    # Initialisation de l'état du bouton
    if "sync_running" not in st.session_state:
        st.session_state.sync_running = False

    # Le bouton se désactive si la synchro est en cours
    btn_label = "⏳ Synchro en cours..." if st.session_state.sync_running else "🚀 Lancer la synchro globale"
    
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
                    nightly_sync()
                    
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