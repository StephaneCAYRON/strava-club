from ast import Break
import streamlit as st
import pandas as pd


def render_group_milestones(total_km, total_dplus, group_name):
    """
    Affiche les accomplissements collectifs basés sur le KM et le D+
    """

    # --- CONSTANTES DE COMPARAISON ---
    
    EARTH_CIRCUMFERENCE = 40075
    TOUR_DE_FRANCE_KM = 3500
    MURAI_DE_CHINE_KM = 21196

    EVEREST_HEIGHT = 8848
    STRATOSPHERE_HEIGHT = 10000
    ISS_HEIGHT = 408000


    render_premium_milestones(total_km, total_dplus)

    st.divider()

    if False:

        # --- LAYOUT : 2 COLONNES ---
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### ⛰️ Vers les sommets")
            nb_everest = total_dplus / EVEREST_HEIGHT
            st.metric("Altitude cumulée", f"{total_dplus:,.0f} m", f"{nb_everest:.1f} Everest")
            
            # Barre de progression vers le prochain Everest
            """
            progress_iss = (total_dplus % ISS_HEIGHT) / ISS_HEIGHT
            st.write(f"**Objectif :** L'ISS, à 400 km d'altitude")
            st.progress(progress_iss)
            st.caption(f"Encore {int(ISS_HEIGHT - (total_dplus % ISS_HEIGHT))}m pour atteindre l'ISS !")
            """

        with col2:
            st.markdown("#### 🌍 L'épopée")
            nb_tdf = total_km / MURAI_DE_CHINE_KM
            st.metric("Distance cumulée", f"{total_km:,.0f} km", f"{nb_tdf:.1f} muraille de Chine")
            
            # Barre de progression vers le tour de la terre
            """
            progress_earth = min(total_km / EARTH_CIRCUMFERENCE, 1.0)
            st.write(f"**Objectif :** Le Tour de la Terre")
            st.progress(progress_earth)
            st.caption(f"Nous avons parcouru {total_km/EARTH_CIRCUMFERENCE:.2%} du globe !")
            """
        

        if False:
            st.divider()
            # --- SECTION "LE SAVIEZ-VOUS ?" (FUN FACTS) ---
            st.markdown("#### 💡 Le saviez-vous ?")
            
            # Logique pour choisir un fait marquant selon les stats
            fact_cols = st.columns(3)
            
            with fact_cols[0]:
                if total_dplus > 10000:
                    st.info("✈️ On dépasse l'altitude de croisière d'un avion de ligne.")
                else:
                    st.info("🚠 On a déjà dépassé le sommet de l'Aiguille du Midi !")

            with fact_cols[1]:
                if total_km > 1000:
                    st.success("🥖 On a assez de KM pour traverser la France du Nord au Sud.")
                else:
                    st.success("🚴 On a déjà fait plus de distance qu'un Paris-Brest-Paris !")

            with fact_cols[2]:
                calories = total_km * 30 # Estimation large : 30 kcal/km
                croissants = calories / 400
                st.warning(f"🥐 On a brûlé environ {croissants:,.0f} croissants collectifs.")


def render_premium_milestones(total_km, total_dplus):
    # Définition des constantes
    EVEREST = 8848
    EARTH = 40075

    # CSS pour un look "App Sportive Haut de Gamme"
    st.markdown("""
        <style>
        .container {
            display: flex;
            gap: 20px;
            margin: 20px 0;
        }
        .card {
            background: #ffffff;
            border-radius: 12px;
            padding: 20px;
            flex: 1;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            display: flex;
            align-items: center;
            border: 1px solid #f0f0f0;
        }
        .icon-box {
            width: 50px;
            height: 50px;
            margin-right: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .data-box {
            display: flex;
            flex-direction: column;
        }
        .label {
            color: #888;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .value {
            color: #1a1a1a;
            font-size: 26px;
            font-weight: 800;
            line-height: 1;
            margin: 4px 0;
        }
        .sub {
            color: #666;
            font-size: 13px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Icônes SVG
    svg_mountain = '''<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#E62E2D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3l4 8 5-5 5 15H2L8 3z"></path></svg>'''
    svg_road = '''<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6l-6 12-6-12"></path><path d="M4 6h16"></path><path d="M12 2v20"></path></svg>'''

    # Pour le D+
    total_dplus_str = f"{total_dplus:,.0f}".replace(",", " ")

    # Pour les KM
    total_km_str = f"{total_km:,.0f}".replace(",", " ")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f'''
            <div class="card">
                <div class="icon-box">{svg_mountain}</div>
                <div class="data-box">
                    <span class="label">Ascension Totale D+</span>
                    <span class="value">{total_dplus_str} m</span>
                    <span class="sub">{total_dplus/EVEREST:.1f} Everest cumulés</span>
                </div>
            </div>
        ''', unsafe_allow_html=True)

    with col2:
        st.markdown(f'''
            <div class="card">
                <div class="icon-box">{svg_road}</div>
                <div class="data-box">
                    <span class="label">Distance Totale</span>
                    <span class="value">{total_km_str} km</span>
                    <span class="sub">{total_km/EARTH:.2%} du tour du monde</span>
                </div>
            </div>
        ''', unsafe_allow_html=True)