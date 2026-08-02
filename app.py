from __future__ import annotations
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from services.data import MarketSnapshot, compute_scenarios, load_snapshot

st.set_page_config(page_title="Tableau de bord Or V5", page_icon="🟡", layout="wide")


def fmt(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "Indisponible"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",") + suffix


@st.cache_data(ttl=300, show_spinner=False)
def get_data() -> MarketSnapshot:
    return load_snapshot()


def bar_chart(labels, values, suffix, y_title):
    fig = go.Figure(go.Bar(x=labels, y=values, text=[fmt(v, 2, suffix) for v in values]))
    fig.update_traces(textposition="outside")
    fig.update_layout(height=370, margin=dict(l=10, r=10, t=30, b=10), yaxis_title=y_title, showlegend=False)
    return fig


st.title("🟡 Tableau de bord Or — V5")
st.caption("Napoléon 20 francs — coût réel, point mort et score d'investissement, hors livraison et fiscalité personnelle")

with st.sidebar:
    st.header("Simulation")
    horizon_months = st.slider("Durée de conservation", 0, 60, 12, 1, format="%d mois")
    st.subheader("Canal d'achat")
    goldfr_commission = st.toggle("Gold.fr : achat téléphone/e-mail (+3,3 %, min. 10 €)", value=False)
    godot_extra = st.number_input("Godot : surcharge constatée (%)", 0.0, 20.0, 0.0, 0.1)
    goldfr_extra = st.number_input("Gold.fr : surcharge panier constatée (%)", 0.0, 20.0, 0.0, 0.1)
    st.subheader("Hypothèse de revente")
    godot_resale = st.number_input("Décote revente Godot (%)", 0.0, 20.0, 1.5, 0.1)
    goldfr_resale = st.number_input("Décote revente Gold.fr (%)", 0.0, 20.0, 1.5, 0.1)
    aucoffre_resale = st.number_input("Décote marché AuCOFFRE avant commission (%)", 0.0, 20.0, 0.0, 0.1)
    st.caption("Les décotes de revente sont des hypothèses modifiables, faute de prix de rachat homogènes publiés en temps réel.")

left, right = st.columns([1, 4])
with left:
    if st.button("Actualiser", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
snapshot = get_data()
with right:
    updated = snapshot.timestamp.astimezone(ZoneInfo("Europe/Paris"))
    st.caption(f"Dernière collecte : {updated:%d/%m/%Y à %H:%M:%S} — cache 5 minutes")
if snapshot.errors:
    with st.expander(f"Diagnostics ({len(snapshot.errors)})"):
        for error in snapshot.errors:
            st.warning(error)

st.subheader("Marché spot")
cols = st.columns(5)
cols[0].metric("PAXG / USD oz", fmt(snapshot.market.paxg_usd_oz, 2, " USD"))
cols[1].metric("EUR / USD", fmt(snapshot.market.eur_usd, 4))
cols[2].metric("Spot EUR / oz", fmt(snapshot.market.spot_eur_oz, 2, " €"))
cols[3].metric("Spot EUR / g", fmt(snapshot.market.spot_eur_g, 2, " €"))
cols[4].metric("Valeur théorique 20F", fmt(snapshot.theoretical_20f_eur, 2, " €"))
st.divider()

st.subheader("Offres AuCOFFRE détectées")
if snapshot.aucoffre_offers:
    options = list(snapshot.aucoffre_offers)
    labels = [f"{fmt(o.achat, 2, ' €')} — {o.etat or 'état ND'} — livrable {o.livrable or 'ND'} — {'LSP' if o.is_lsp else 'non-LSP'}" for o in options]
    selected_index = st.selectbox("Offre utilisée dans la comparaison", range(len(options)), format_func=lambda i: labels[i])
    selected_offer = options[selected_index]
    offers_df = pd.DataFrame([{
        "Prix (€)": o.achat, "Prime (%)": o.prime, "État": o.etat, "Livrable": o.livrable,
        "Coffre": o.coffre, "Fiscalité": o.fiscalite, "LSP": "Oui" if o.is_lsp else "Non",
        "Produit": o.product_name,
    } for o in options[:15]])
    st.dataframe(offers_df, hide_index=True, use_container_width=True)
else:
    selected_offer = None
    st.warning("Aucune offre AuCOFFRE exploitable détectée.")

scenarios = compute_scenarios(
    snapshot, horizon_months, selected_offer, goldfr_commission, godot_extra, goldfr_extra,
    godot_resale, goldfr_resale, aucoffre_resale,
)
valid = [s for s in scenarios if s.cost_after_horizon is not None]
best = min(valid, key=lambda s: s.cost_after_horizon, default=None)
best_score = max((s for s in valid if s.score is not None), key=lambda s: s.score, default=None)

st.divider()
st.subheader("Verdict")
metrics = st.columns(4)
metrics[0].metric("Coût total le plus bas", f"{best.shop} — {best.scenario}" if best else "Indisponible")
metrics[1].metric(f"Après {horizon_months} mois", fmt(best.cost_after_horizon if best else None, 2, " €"))
metrics[2].metric("Meilleur score", f"{best_score.shop} — {best_score.scenario}" if best_score else "Indisponible")
metrics[3].metric("Score", f"{best_score.score}/100" if best_score and best_score.score is not None else "Indisponible")

rows = []
for s in scenarios:
    rows.append({
        "Vendeur": s.shop,
        "Scénario": s.scenario,
        "Prix affiché (€)": s.displayed_price,
        "Frais achat (€)": s.purchase_fee_eur,
        "Coût entrée (€)": s.entry_cost,
        f"Garde {horizon_months} mois (€)": s.storage_cost,
        f"Coût total {horizon_months} mois (€)": s.cost_after_horizon,
        "Prime réelle entrée (%)": s.effective_premium_pct,
        "Valeur revente estimée (€)": s.estimated_resale_value,
        "Perte si revente immédiate (€)": s.immediate_loss,
        "Hausse nécessaire au point mort (%)": s.break_even_rise_pct,
        "Score /100": s.score,
    })
df = pd.DataFrame(rows)
st.dataframe(df, hide_index=True, use_container_width=True)

chart_rows = [s for s in valid]
a, b = st.columns(2)
with a:
    st.plotly_chart(bar_chart([f"{s.shop}\n{s.scenario}" for s in chart_rows], [s.cost_after_horizon for s in chart_rows], " €", "Coût total"), use_container_width=True)
with b:
    scored = [s for s in chart_rows if s.break_even_rise_pct is not None]
    st.plotly_chart(bar_chart([f"{s.shop}\n{s.scenario}" for s in scored], [s.break_even_rise_pct for s in scored], " %", "Hausse nécessaire au point mort"), use_container_width=True)

st.subheader("Lecture des résultats")
for s in scenarios:
    with st.expander(f"{s.shop} — {s.scenario}"):
        st.write(s.note)
        if s.score is not None:
            st.write(f"**Score : {s.score}/100** — pénalise la prime, le point mort, les frais de garde et le manque de transparence du prix final.")

st.error(
    "Point important : pour une petite détention AuCOFFRE non-LSP, la V5 applique prudemment le minimum officiel de facturation de 30 € à chaque facture mensuelle. "
    "Une seule pièce non-LSP peut donc coûter 360 € de garde sur 12 mois. Le scénario LSP n'apparaît que si l'offre détectée est réellement marquée LSP."
)
st.info(
    "Le prix Gold.fr affiché ressemble à une cotation et non à un panier ferme. La commission de 3,3 % est désormais désactivée par défaut et ne s'applique que lorsque le canal téléphone/e-mail est sélectionné."
)
st.markdown(
    "**Tarifs de référence :** [AuCOFFRE](https://www.aucoffre.com/acheter/tarifs-aucoffre-com) · "
    "[Gold.fr](https://www.gold.fr/informations-sur-l-or/nous-connaitre/conditions-generales-dutilisation)"
)
st.caption("Comparateur indicatif. Livraison et fiscalité personnelle exclues. Vérifier le prix ferme et les conditions avant tout ordre.")
