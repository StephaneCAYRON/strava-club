import streamlit as st
from strava_operations import *
from db_operations import *

def render_tab_groups(texts):
    """Contenu de l'onglet Gestion des Groupes."""
    athlete = st.session_state.athlete
    col_list, col_admin = st.columns([1, 1], gap="large")
    
    with col_list:
        st.subheader(texts["my_groups"])
        m_groups = get_user_memberships(athlete['id'])
        for g in m_groups.data:
            icon = "✅" if g['status'] == 'approved' else "⏳"
            st.write(f"{icon} **{g['groups']['name']}**")
        
        st.divider()
        st.subheader(texts["join_group"])
        all_g = get_all_groups()
        if all_g.data:
            already_member = [g['group_id'] for g in m_groups.data]
            available = [g for g in all_g.data if g['id'] not in already_member]
            if available:
                g_to_join = st.selectbox(texts["group_name"], options=available, format_func=lambda x: x['name'])
                if st.button(texts["join_group"], use_container_width=True):
                    request_to_join_group(g_to_join['id'], athlete['id'])
                    st.success(texts["request_sent"])
                    st.rerun()

    with col_admin:
        #st.markdown(athlete['id'])
        if athlete['id'] == 5251772: #desactivation pour l'instant
            st.markdown("### 🛠 Espace Administration")
            with st.expander(f"➕ {texts['create_group']}"):
                name = st.text_input(texts["group_name"], key="new_g")
                if st.button(texts["create_group"], use_container_width=True):
                    create_group(name, athlete['id'])
                    st.rerun()
            pending = get_pending_requests_for_admin(athlete['id'])
            if pending or any(g['status'] == 'approved' for g in m_groups.data):
                
                with st.container(border=True):
                    if pending and pending.data:
                        for p in pending.data:
                            c1, c2 = st.columns([2, 1])
                            c1.write(f"**{p['profiles']['firstname']}** -> {p['groups']['name']}")
                            if c2.button(texts["approve"], key=p['id'], type="primary"):
                                update_membership_status(p['id'], "approved")
                                st.rerun()
                    else:
                        st.write("Aucune demande en attente.")