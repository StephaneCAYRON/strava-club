import streamlit as st
import pandas as pd
import altair as alt
import plotly.graph_objects as go
from db_operations import supabase
from ui_components_statistics import calculate_eddington

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

JOURS_FR = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
             4: "Vendredi", 5: "Samedi", 6: "Dimanche"}

MOIS_FR = {1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Juin",
           7: "Jul", 8: "Aoû", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc"}

MOIS_FR_FULL = {1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai",
                6: "Juin", 7: "Juillet", 8: "Août", 9: "Septembre",
                10: "Octobre", 11: "Novembre", 12: "Décembre"}

QUOTES = [
    "\"Je n'ai pas d'addiction au vélo. Je pourrais arrêter quand je veux. Mais je ne veux pas.\"",
    "\"Mes jambes disent non, mais mon Garmin dit encore 30 km.\"",
    "\"Le vélo, c'est comme le vin : plus c'est cher, mieux tu grimpes — ou pas.\"",
    "\"J'ai un problème de vélo. Mais c'est mon problème préféré.\"",
    "\"Ma femme dit que j'ai trop de vélos. Ma femme a tort.\"",
    "\"5h du mat, beau temps, sortie vélo. 5h du mat, pluie, sortie vélo. J'appelle ça de la constance.\"",
    "\"Quelqu'un m'a dit que le café n'est pas un groupe alimentaire. Quelqu'un a tort.\"",
    "\"Mon médecin m'a dit de faire du sport. Il n'avait pas précisé de s'arrêter.\"",
    "\"Le vrai cardio, c'est vérifier son Strava toutes les 10 minutes.\"",
    "\"Je roule pour rester en forme. Et pour pouvoir manger des croissants sans culpabilité.\"",
    "\"La côte n'était pas si raide... c'est juste que mes jambes sont trop courtes.\"",
    "\"Perché sur mon vélo à 6h du mat, je me demande pourquoi. Puis je vois le lever de soleil. Bon OK.\"",
]

TITRES_CYCLISTES = [
    # (condition_fn(stats) → bool, titre, description)
    # Les conditions sont évaluées dans l'ordre, le premier qui matche gagne
]

def _score_endurance(avg_dist):
    """Score 0-100 basé sur la distance moyenne par sortie"""
    return min(100, avg_dist / 1.5)

def _score_masochisme(dplus_per_100km):
    """Score 0-100 basé sur le D+/100km"""
    return min(100, dplus_per_100km / 25)

def _score_regularite(rides_per_month):
    """Score 0-100 basé sur la fréquence mensuelle"""
    return min(100, rides_per_month * 10)

def _score_matinal(df):
    """Score 0-100 : proportion de sorties avant 8h (heure locale ≈ UTC+2)"""
    if df.empty:
        return 0
    early = df[(df['hour'] + 2) % 24 < 8]
    return min(100, len(early) / len(df) * 300)

def _score_volume(total_km):
    """Score 0-100 basé sur le total de km"""
    return min(100, total_km / 100)

def _get_titre(stats):
    """Génère un titre humoristique selon le profil."""
    dplus_per_100km = stats['dplus_per_100km']
    avg_dist = stats['avg_dist']
    pct_weekend = stats['pct_weekend']
    rides_per_month = stats['rides_per_month']

    if dplus_per_100km > 1800 and avg_dist > 80:
        return "🏔️ Seigneur des Cimes & Dévoreur d'Asphalte", \
               "Un être mystérieux qui cherche activement à souffrir. Probablement heureux en descente. Probablement menteur en descente."
    if dplus_per_100km > 1800:
        return "🏔️ Seigneur des Cimes", \
               "Monte les cols, descend les cols, redemande des cols. Le plat, c'est pour les autres."
    if dplus_per_100km < 400 and avg_dist > 100:
        return "🛣️ Grand Prêtre du Plat", \
               "Champion incontesté des routes planes. Voit une bosse et change d'itinéraire."
    if dplus_per_100km < 400:
        return "🥞 Amoureux du Plat Pays", \
               "Si ça monte, c'est un bug GPS. Spécialiste incontesté des courses contre le vent (il perd, mais il essaie)."
    if avg_dist > 120:
        return "🐘 Monstre d'Endurance", \
               "Quand les autres rentrent, lui repart pour un tour. Possède probablement plus de bidons que d'amis."
    if avg_dist < 30:
        return "🐦 Adepte du Tour du Quartier", \
               "Qualité > quantité, dit-il. Strava says otherwise. Boulanger du coin le reconnaît à l'aller ET au retour."
    if pct_weekend > 80:
        return "🥐 Cycliste du Week-End", \
               "Du lundi au vendredi : citoyen lambda. Samedi-dimanche : transforme en machine de guerre. Jusqu'à 10h, après c'est l'apéro."
    if rides_per_month > 15:
        return "🔥 Bête de Régularité", \
               "Sort par beau temps, par pluie, par grand froid, par canicule. Son vélo n'a jamais vu l'intérieur d'un garage."
    if rides_per_month < 3:
        return "🦥 Cycliste Occasionnel de Luxe", \
               "Sort quand les planètes s'alignent : bonne météo, pas de match de foot, vélo gonflé. Ça arrive."
    return "🚴 Cycliste Équilibré et Mystérieux", \
           "Ni trop, ni trop peu. Un zen du bitume. Probablement le plus raisonnable du groupe, ce qui est suspect."

def _get_masochisme_label(dplus_per_100km):
    if dplus_per_100km < 300:
        return "🥞 Plat comme une crêpe bretonne", "#27ae60"
    if dplus_per_100km < 700:
        return "🌄 Quelques bosses pour se donner bonne conscience", "#f39c12"
    if dplus_per_100km < 1200:
        return "💪 Amateur de souffrance modéré", "#e67e22"
    if dplus_per_100km < 1800:
        return "😤 Masochiste certifié", "#e74c3c"
    return "🤯 Cas désespéré — consulte un médecin", "#8e44ad"

def _get_leve_tot_label(pct_before_8h):
    if pct_before_8h < 10:
        return "🛌 Partisan du réveil en douceur"
    if pct_before_8h < 30:
        return "☕ Lève-tôt occasionnel (quand le café est prêt)"
    if pct_before_8h < 60:
        return "🌅 Crève-tôt semi-professionnel"
    return "🦅 Vampire solaire — voit plus le soleil se lever que se coucher"


# ---------------------------------------------------------------------------
# GRAPHIQUES
# ---------------------------------------------------------------------------

def _chart_par_jour(df):
    """Bar chart des sorties par jour de la semaine."""
    df['jour_num'] = df['start_date'].dt.dayofweek
    df['jour_nom'] = df['jour_num'].map(JOURS_FR)

    agg = df.groupby(['jour_num', 'jour_nom']).agg(
        nb_sorties=('distance_km', 'count'),
        total_km=('distance_km', 'sum')
    ).reset_index().sort_values('jour_num')

    chart = alt.Chart(agg).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
        x=alt.X('jour_nom:N', sort=list(JOURS_FR.values()), title=None,
                axis=alt.Axis(labelFontSize=13)),
        y=alt.Y('nb_sorties:Q', title='Nombre de sorties'),
        color=alt.condition(
            alt.datum.jour_num >= 5,
            alt.value('#E62E2D'),
            alt.value('#7f8c8d')
        ),
        tooltip=[
            alt.Tooltip('jour_nom:N', title='Jour'),
            alt.Tooltip('nb_sorties:Q', title='Sorties'),
            alt.Tooltip('total_km:Q', title='Km total', format='.0f'),
        ]
    ).properties(height=280, title="🗓️ Tes jours sacrés")

    text = chart.mark_text(dy=-10, fontSize=11, fontWeight='bold').encode(
        text=alt.Text('nb_sorties:Q')
    )
    return (chart + text).configure_view(strokeWidth=0)


def _chart_par_heure(df):
    """Bar chart des sorties par heure de départ (heure locale ≈ UTC+2)."""
    df = df.copy()
    df['heure_locale'] = (df['hour'] + 2) % 24

    agg = df.groupby('heure_locale').size().reset_index(name='nb_sorties')
    all_hours = pd.DataFrame({'heure_locale': range(24)})
    agg = all_hours.merge(agg, on='heure_locale', how='left').fillna(0)
    agg['nb_sorties'] = agg['nb_sorties'].astype(int)
    agg['label'] = agg['heure_locale'].apply(lambda h: f"{h:02d}h")

    chart = alt.Chart(agg).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X('heure_locale:O', title='Heure de départ',
                axis=alt.Axis(values=list(range(24)), labelExpr="datum.value + 'h'")),
        y=alt.Y('nb_sorties:Q', title='Nombre de sorties'),
        color=alt.condition(
            (alt.datum.heure_locale >= 5) & (alt.datum.heure_locale <= 9),
            alt.value('#E62E2D'),
            alt.value('#bdc3c7')
        ),
        tooltip=[
            alt.Tooltip('label:N', title='Heure'),
            alt.Tooltip('nb_sorties:Q', title='Sorties'),
        ]
    ).properties(height=280, title="⏰ Ton horloge interne (heure locale)")
    return chart.configure_view(strokeWidth=0)


def _chart_mensuel(df):
    """Heatmap km par mois × année."""
    df = df.copy()
    df['mois_num'] = df['start_date'].dt.month
    df['annee'] = df['start_date'].dt.year.astype(str)
    df['mois_nom'] = df['mois_num'].map(MOIS_FR)

    agg = df.groupby(['annee', 'mois_num', 'mois_nom'])['distance_km'].sum().reset_index()

    heatmap = alt.Chart(agg).mark_rect(cornerRadius=4).encode(
        x=alt.X('mois_num:O', title=None,
                axis=alt.Axis(values=list(range(1, 13)),
                              labelExpr="{1:'Jan',2:'Fév',3:'Mar',4:'Avr',5:'Mai',6:'Juin',7:'Jul',8:'Aoû',9:'Sep',10:'Oct',11:'Nov',12:'Déc'}[datum.value]")),
        y=alt.Y('annee:N', title=None, sort='descending'),
        color=alt.Color('distance_km:Q',
                        scale=alt.Scale(scheme='reds', zero=True),
                        title='Km'),
        tooltip=[
            alt.Tooltip('mois_nom:N', title='Mois'),
            alt.Tooltip('annee:N', title='Année'),
            alt.Tooltip('distance_km:Q', title='Km', format='.0f'),
        ]
    ).properties(height=max(120, len(agg['annee'].unique()) * 35),
                 title="🗓️ Ton calendrier de la foi (km/mois)")

    text = heatmap.mark_text(fontSize=10).encode(
        text=alt.Text('distance_km:Q', format='.0f'),
        color=alt.condition(alt.datum.distance_km > agg['distance_km'].quantile(0.7),
                            alt.value('white'), alt.value('#555'))
    )
    return (heatmap + text).configure_view(strokeWidth=0)


def _chart_annuel(df):
    """Évolution annuelle des km avec ligne de tendance."""
    df = df.copy()
    df['annee'] = df['start_date'].dt.year
    agg = df.groupby('annee').agg(
        total_km=('distance_km', 'sum'),
        nb_sorties=('distance_km', 'count')
    ).reset_index()
    agg['annee_str'] = agg['annee'].astype(str)

    base = alt.Chart(agg).encode(x=alt.X('annee_str:N', title='Année'))

    bars = base.mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color='#E62E2D', opacity=0.85).encode(
        y=alt.Y('total_km:Q', title='Km'),
        tooltip=[
            alt.Tooltip('annee_str:N', title='Année'),
            alt.Tooltip('total_km:Q', title='Km', format=',.0f'),
            alt.Tooltip('nb_sorties:Q', title='Sorties'),
        ]
    )
    labels = base.mark_text(dy=-12, fontWeight='bold', fontSize=12).encode(
        y='total_km:Q',
        text=alt.Text('total_km:Q', format=',.0f')
    )
    return (bars + labels).properties(height=320, title="📈 L'évolution de ton ego (km/an)").configure_view(strokeWidth=0)


def _jauge_masochisme(dplus_per_100km):
    label, _ = _get_masochisme_label(dplus_per_100km)
    val = min(dplus_per_100km, 2500)
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(dplus_per_100km),
        number={'suffix': " m/100km", 'font': {'size': 22}},
        title={'text': "🔥 Compteur de Masochisme<br><span style='font-size:13px'>" + label + "</span>",
               'font': {'size': 15}},
        gauge={
            'axis': {'range': [0, 2500], 'tickwidth': 1},
            'bar': {'color': "#E62E2D", 'thickness': 0.3},
            'steps': [
                {'range': [0, 300],    'color': '#d5f5e3'},
                {'range': [300, 700],  'color': '#fdebd0'},
                {'range': [700, 1200], 'color': '#fad7a0'},
                {'range': [1200, 1800],'color': '#f1948a'},
                {'range': [1800, 2500],'color': '#e8daef'},
            ],
            'threshold': {
                'line': {'color': "darkred", 'width': 4},
                'thickness': 0.75, 'value': dplus_per_100km
            }
        }
    ))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=60, b=10),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig


def _radar_profil(scores):
    """Radar chart du profil cycliste."""
    categories = ['Endurance', 'Masochisme<br>(D+)', 'Régularité', 'Lève-tôt', 'Volume']
    vals = [scores[k] for k in ['endurance', 'masochisme', 'regularite', 'matinal', 'volume']]
    vals_closed = vals + [vals[0]]
    cats_closed = categories + [categories[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_closed,
        theta=cats_closed,
        fill='toself',
        fillcolor='rgba(230, 46, 45, 0.25)',
        line=dict(color='#E62E2D', width=2),
        name='Ton profil'
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100],
                            tickfont=dict(size=9), showticklabels=False),
            angularaxis=dict(tickfont=dict(size=12))
        ),
        showlegend=False,
        height=320,
        margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        title=dict(text="🕸️ Ton ADN de Cycliste", font=dict(size=15), x=0.5)
    )
    return fig


def _diplomes(df, stats):
    """Génère une liste de diplômes humoristiques selon les exploits."""
    badges = []

    if stats['total_km'] >= 10000:
        badges.append(("🌍", "Grand Voyageur", f"Plus de 10 000 km parcourus — soit {stats['total_km'] / 40075:.1f} tours de la Terre"))
    elif stats['total_km'] >= 5000:
        badges.append(("🗺️", "Explorateur Confirmé", f"Plus de 5 000 km — la moitié d'un vrai explorateur"))
    else:
        badges.append(("📍", "Cycliste en Herbe", f"{stats['total_km']:.0f} km — c'est un début !"))

    if stats['total_elev'] >= 100000:
        badges.append(("🏔️", "Chevalier de l'Everest", f"{stats['total_elev'] / 8849:.1f} Everests gravis. En option : jambes en béton"))
    elif stats['total_elev'] >= 50000:
        badges.append(("⛰️", "Grimpeur Sérieux", f"{stats['total_elev'] / 8849:.1f} Everests gravis. Commence à parler en D+"))

    if stats['total_rides'] >= 200:
        badges.append(("🔥", "Addict Officiel", f"{stats['total_rides']} sorties enregistrées — vélo > tout"))
    elif stats['total_rides'] >= 50:
        badges.append(("🚴", "Cycliste Régulier", f"{stats['total_rides']} sorties — c'est bien !"))

    max_dist = df['distance_km'].max()
    if max_dist >= 200:
        badges.append(("🦁", "Avaleur de Routes", f"La plus longue sortie : {max_dist:.0f} km. Probablement rentré à la nuit"))
    elif max_dist >= 100:
        badges.append(("📏", "Centurion", f"A déjà fait plus de 100 km d'un coup. Peut en parler pendant des années"))

    # Lève-tôt badge
    early_rides = len(df[(df['hour'] + 2) % 24 < 6])
    if early_rides >= 5:
        badges.append(("🌅", "Maître de l'Aube", f"{early_rides} sorties avant 6h du mat. Probablement dérangé"))

    # Dimanche badge
    sunday_rides = len(df[df['start_date'].dt.dayofweek == 6])
    if sunday_rides >= 20:
        badges.append(("🥐", "Pèlerin du Dimanche", f"{sunday_rides} sorties dominicales. Les croissants post-ride, une religion"))

    # Hiver badge
    winter_rides = len(df[df['start_date'].dt.month.isin([12, 1, 2])])
    if winter_rides >= 10:
        badges.append(("🥶", "Courageux (ou Inconscient)", f"{winter_rides} sorties en hiver — imperméable vissé au dos"))

    # Eddington
    edd = calculate_eddington(df[df['type'] == 'Ride']['distance_km']) if 'type' in df.columns else calculate_eddington(df['distance_km'])
    if edd >= 100:
        badges.append(("🎩", "Maître Eddington", f"Eddington = {edd}. Lance la phrase en société pour impressionner"))
    elif edd >= 60:
        badges.append(("🎩", "Chevalier Eddington", f"Eddington = {edd}. Sait ce que c'est. Fier de le dire"))
    elif edd > 0:
        badges.append(("🎩", "Novice Eddington", f"Eddington = {edd}. Commence à comprendre pourquoi c'est dur"))

    return badges


# ---------------------------------------------------------------------------
# RENDER PRINCIPAL
# ---------------------------------------------------------------------------

def render_tab_bio(texts):
    athlete = st.session_state.athlete
    athlete_id = athlete['id']
    firstname = athlete.get('firstname', 'Cycliste')
    lastname = athlete.get('lastname', '')
    profile_pic = athlete.get('profile_medium') or athlete.get('profile', '')

    # --- Récupération des données ---
    res = supabase.table("activities").select("*").eq("id_strava", athlete_id).order("start_date", desc=True).execute()

    if not res.data:
        st.info("😶 Pas encore d'activités... Ton vélo prend la poussière ?")
        return

    df = pd.DataFrame(res.data)
    df['start_date'] = pd.to_datetime(df['start_date'])
    df['distance_km']          = pd.to_numeric(df['distance_km'],          errors='coerce').fillna(0)
    df['total_elevation_gain'] = pd.to_numeric(df['total_elevation_gain'], errors='coerce').fillna(0)
    df['moving_time']          = pd.to_numeric(df['moving_time'],          errors='coerce').fillna(0)
    df['hour'] = df['start_date'].dt.hour

    # --- Stats de base ---
    total_km    = df['distance_km'].sum()
    total_elev  = df['total_elevation_gain'].sum()
    total_time_h = df['moving_time'].sum() / 3600
    total_rides = len(df)
    avg_dist    = total_km / total_rides if total_rides > 0 else 0
    avg_speed   = total_km / total_time_h if total_time_h > 0 else 0
    dplus_per_100km = (total_elev / total_km * 100) if total_km > 0 else 0

    weekend_rides = len(df[df['start_date'].dt.dayofweek >= 5])
    pct_weekend   = weekend_rides / total_rides * 100 if total_rides > 0 else 0

    years_active = max(1, df['start_date'].dt.year.nunique())
    months_total = max(1, (df['start_date'].max() - df['start_date'].min()).days / 30)
    rides_per_month = total_rides / months_total

    early_rides   = len(df[(df['hour'] + 2) % 24 < 8])
    pct_before_8h = early_rides / total_rides * 100 if total_rides > 0 else 0

    stats = dict(
        total_km=total_km, total_elev=total_elev, total_rides=total_rides,
        avg_dist=avg_dist, dplus_per_100km=dplus_per_100km,
        pct_weekend=pct_weekend, rides_per_month=rides_per_month,
    )

    scores = dict(
        endurance  = _score_endurance(avg_dist),
        masochisme = _score_masochisme(dplus_per_100km),
        regularite = _score_regularite(rides_per_month),
        matinal    = _score_matinal(df),
        volume     = _score_volume(total_km),
    )

    titre, description_titre = _get_titre(stats)
    quote = QUOTES[athlete_id % len(QUOTES)]

    # =========================================================
    # HEADER
    # =========================================================
    st.markdown(f"""
    <div style="text-align:center; padding: 20px 0 10px 0;">
        <h1 style="font-size:2.2em; margin-bottom:0;">🧬 Ma Bio Sportive</h1>
        <p style="color:#888; font-style:italic; font-size:1.05em;">
            Parce que les données ne mentent pas. Elles, elles n'ont pas d'excuses.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # =========================================================
    # FICHE D'IDENTITÉ
    # =========================================================
    st.markdown("---")

    col_pic, col_id = st.columns([1, 3], gap="large")

    with col_pic:
        if profile_pic:
            st.markdown(f"""
            <div style="text-align:center;">
                <img src="{profile_pic}" style="border-radius:50%; width:130px; height:130px;
                     border:4px solid #E62E2D; box-shadow:0 4px 15px rgba(230,46,45,0.3);">
            </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align:center; margin-top:10px;">
            <div style="font-size:1.2em; font-weight:800;">{firstname} {lastname}</div>
            <div style="color:#E62E2D; font-size:1.1em; margin-top:5px;">{titre}</div>
            <div style="color:#888; font-size:0.85em; font-style:italic; margin-top:8px; line-height:1.4;">
                {description_titre}
            </div>
        </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="margin-top:18px; padding:12px; background:#f9f9f9; border-radius:10px;
                    border-left:3px solid #E62E2D; font-style:italic; font-size:0.85em; color:#555;">
            {quote}
        </div>""", unsafe_allow_html=True)

    with col_id:
        st.markdown("#### 📋 La Fiche Signalétique Officielle")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div style="background:white; border-radius:12px; padding:15px 10px; text-align:center;
                        box-shadow:0 2px 10px rgba(0,0,0,0.07); border-top:4px solid #3498db;">
                <div style="font-size:2em;">🌍</div>
                <div style="font-size:1.6em; font-weight:800; color:#3498db;">{total_km / 40075:.2f}</div>
                <div style="font-size:0.75em; color:#888;">Tours de la Terre</div>
                <div style="font-size:0.7em; color:#bbb;">{total_km:,.0f} km</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="background:white; border-radius:12px; padding:15px 10px; text-align:center;
                        box-shadow:0 2px 10px rgba(0,0,0,0.07); border-top:4px solid #e67e22;">
                <div style="font-size:2em;">🏔️</div>
                <div style="font-size:1.6em; font-weight:800; color:#e67e22;">{total_elev / 8849:.1f}</div>
                <div style="font-size:0.75em; color:#888;">Everests gravis</div>
                <div style="font-size:0.7em; color:#bbb;">{total_elev:,.0f} m</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div style="background:white; border-radius:12px; padding:15px 10px; text-align:center;
                        box-shadow:0 2px 10px rgba(0,0,0,0.07); border-top:4px solid #9b59b6;">
                <div style="font-size:2em;">⏱️</div>
                <div style="font-size:1.6em; font-weight:800; color:#9b59b6;">{total_time_h:.0f}h</div>
                <div style="font-size:0.75em; color:#888;">Sur le vélo</div>
                <div style="font-size:0.7em; color:#bbb;">≈ {total_time_h / 24:.0f} jours sans dormir</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div style="background:white; border-radius:12px; padding:15px 10px; text-align:center;
                        box-shadow:0 2px 10px rgba(0,0,0,0.07); border-top:4px solid #E62E2D;">
                <div style="font-size:2em;">🚴</div>
                <div style="font-size:1.6em; font-weight:800; color:#E62E2D;">{total_rides}</div>
                <div style="font-size:0.75em; color:#888;">Sorties</div>
                <div style="font-size:0.7em; color:#bbb;">moy. {avg_dist:.0f} km</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Comparaisons fun
        paris_brest = 1200
        tour_de_france = 3400
        c5, c6 = st.columns(2)
        with c5:
            nb_pb = total_km / paris_brest
            st.markdown(f"""
            <div style="background:#fff9f0; border-radius:10px; padding:12px; margin-top:8px;
                        border-left:3px solid #f39c12; font-size:0.9em;">
                🥖 <b>Paris-Brest-Paris</b><br>
                <span style="font-size:1.3em; font-weight:800; color:#f39c12;">{nb_pb:.1f}×</span>
                <span style="color:#888;"> l'as-tu fait en distance</span>
            </div>""", unsafe_allow_html=True)
        with c6:
            nb_tdf = total_km / tour_de_france
            st.markdown(f"""
            <div style="background:#fff0f0; border-radius:10px; padding:12px; margin-top:8px;
                        border-left:3px solid #E62E2D; font-size:0.9em;">
                🏆 <b>Tour de France</b><br>
                <span style="font-size:1.3em; font-weight:800; color:#E62E2D;">{nb_tdf:.1f}×</span>
                <span style="color:#888;"> en distance totale</span>
            </div>""", unsafe_allow_html=True)

    # =========================================================
    # RADAR + MASOCHISME
    # =========================================================
    st.markdown("---")
    st.markdown("### 🔬 Analyse Psycho-Sportive")

    col_r, col_g = st.columns([1, 1], gap="large")
    with col_r:
        st.plotly_chart(_radar_profil(scores), use_container_width=True, config={'displayModeBar': False})
        st.caption("*Scores calculés sur l'ensemble de ta carrière Strava — consultable au tribunal de l'ego.*")
    with col_g:
        st.plotly_chart(_jauge_masochisme(dplus_per_100km), use_container_width=True, config={'displayModeBar': False})
        leve_label = _get_leve_tot_label(pct_before_8h)
        avg_speed_label = "🐢 Tortue de compétition" if avg_speed < 22 else ("🐇 Allure croisière" if avg_speed < 28 else "💨 Aérodynamisme douteux mais efficace")
        st.markdown(f"""
        <div style="background:#f8f9fa; border-radius:10px; padding:14px; margin-top:10px; font-size:0.9em; line-height:1.8;">
            <b>⏰ Profil horaire :</b> {leve_label} ({pct_before_8h:.0f}% avant 8h)<br>
            <b>🗓️ Week-end warrior :</b> {pct_weekend:.0f}% des sorties le week-end<br>
            <b>💨 Vitesse moyenne :</b> {avg_speed:.1f} km/h — {avg_speed_label}<br>
            <b>📅 Fréquence :</b> {rides_per_month:.1f} sorties/mois en moyenne
        </div>""", unsafe_allow_html=True)

    # =========================================================
    # HABITUDES
    # =========================================================
    st.markdown("---")
    st.markdown("### 🕵️ Tes Habitudes Inavouables")

    col_j, col_h = st.columns(2, gap="large")
    with col_j:
        top_day = df.groupby(df['start_date'].dt.dayofweek).size().idxmax()
        day_comment = {
            0: "😤 Lundi... Sérieusement ?",
            1: "🙄 Mardi. Respect, mais soupçons.",
            2: "🤔 Mercredi, le jour des enfants et des cyclistes ?",
            3: "📆 Jeudi, le vendredi des cyclistes.",
            4: "🎉 Vendredi ! On commence le week-end tôt.",
            5: "✅ Samedi, classique, rien à dire.",
            6: "🥐 Dimanche — un homme de valeurs."
        }
        st.altair_chart(_chart_par_jour(df), use_container_width=True)
        st.caption(f"Ton jour préféré : **{JOURS_FR[top_day]}** — {day_comment.get(top_day, '')}")

    with col_h:
        top_hour = (df['hour'] + 2) % 24
        most_common_hour = top_hour.value_counts().idxmax()
        hour_comment = (
            "🦇 Même les chauves-souris sont rentrées." if most_common_hour < 5
            else "🌅 Tu vois les levers de soleil. Ou pas, t'as les yeux fermés."
            if most_common_hour < 8
            else "☕ Après le café. Raisonnable."
            if most_common_hour < 11
            else "🌞 Après le brunch. On juge pas."
            if most_common_hour < 14
            else "😴 La sieste attendra."
            if most_common_hour < 17
            else "🌆 Sortie du soir — embouteillages à vélo."
        )
        st.altair_chart(_chart_par_heure(df), use_container_width=True)
        st.caption(f"Heure de départ favorite : **{most_common_hour:02d}h** — {hour_comment}")

    # =========================================================
    # CALENDRIER + ÉVOLUTION
    # =========================================================
    st.markdown("---")
    st.markdown("### 📅 Le Calendrier de la Foi & L'Évolution de l'Ego")

    col_cal, col_an = st.columns([3, 2], gap="large")
    with col_cal:
        st.altair_chart(_chart_mensuel(df), use_container_width=True)
        # Trouver le mois le plus actif
        monthly = df.groupby(df['start_date'].dt.month)['distance_km'].sum()
        best_month_num = monthly.idxmax()
        worst_month_num = monthly.idxmin()
        st.caption(
            f"📈 Ton mois de gloire : **{MOIS_FR_FULL[best_month_num]}** — "
            f"😴 Ton mois de honte : **{MOIS_FR_FULL[worst_month_num]}** "
            f"(excuse officielle : *\"il faisait froid/chaud/nuageux\"*)"
        )
    with col_an:
        st.altair_chart(_chart_annuel(df), use_container_width=True)
        yearly = df.groupby(df['start_date'].dt.year)['distance_km'].sum()
        if len(yearly) >= 2:
            last_two = yearly.sort_index().tail(2)
            diff_pct = (last_two.iloc[1] - last_two.iloc[0]) / last_two.iloc[0] * 100
            trend = f"📈 +{diff_pct:.0f}% vs l'an dernier — t'es en feu !" if diff_pct > 5 else \
                    f"📉 {diff_pct:.0f}% vs l'an dernier — *\"je me ménage\"* 👀" if diff_pct < -5 else \
                    f"➡️ Stable ({diff_pct:+.0f}%) — ni progression, ni régression. Zen."
            st.caption(trend)

    # =========================================================
    # DIPLÔMES
    # =========================================================
    st.markdown("---")
    st.markdown("### 🏅 Tes Diplômes & Médailles Honorifiques")
    st.caption("*Décernés par le Comité International du Vélo Imaginaire (CIVI) — accrédité nulle part, respecté partout.*")

    badges = _diplomes(df, stats)
    cols = st.columns(min(3, len(badges)))
    for i, (icon, titre_b, desc_b) in enumerate(badges):
        with cols[i % 3]:
            st.markdown(f"""
            <div style="background:white; border-radius:14px; padding:16px; margin-bottom:14px;
                        box-shadow:0 3px 12px rgba(0,0,0,0.08); text-align:center;
                        border-top:3px solid #E62E2D;">
                <div style="font-size:2.2em;">{icon}</div>
                <div style="font-weight:800; margin:6px 0 4px; font-size:0.95em;">{titre_b}</div>
                <div style="font-size:0.78em; color:#888; line-height:1.4;">{desc_b}</div>
            </div>""", unsafe_allow_html=True)

    # =========================================================
    # FOOTER BIO
    # =========================================================
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align:center; padding:20px; color:#aaa; font-size:0.85em; font-style:italic;">
        Bio générée à partir de {total_rides} activités et {total_km:,.0f} km de données Strava.<br>
        Toute ressemblance avec la réalité est fortuite et légèrement gênante.<br>
        <span style="color:#E62E2D;">🚴 Pédale fort, {firstname}.</span>
    </div>""", unsafe_allow_html=True)
