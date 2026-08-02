from __future__ import annotations
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from services.data import MarketSnapshot, load_snapshot

st.set_page_config(page_title="Tableau de bord Or", page_icon="🟡", layout="wide")

def fmt(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None: return "Indisponible"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",") + suffix

@st.cache_data(ttl=300, show_spinner=False)
def get_data() -> MarketSnapshot: return load_snapshot()

def bar_chart(labels, values, suffix, y_title):
    fig = go.Figure(go.Bar(x=labels, y=values, text=[fmt(v, 2, suffix) for v in values]))
    fig.update_traces(textposition="outside")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), yaxis_title=y_title, showlegend=False)
    return fig

st.title("🟡 Tableau de bord Or")
st.caption("Napoléon 20 francs — Binance, Godot & Fils, Gold.fr et AuCOFFRE.com")
left, right = st.columns([1, 4])
with left:
    if st.button("Actualiser", type="primary", use_container_width=True):
        st.cache_data.clear(); st.rerun()
snapshot = get_data()
with right:
    updated = snapshot.timestamp.astimezone(ZoneInfo("Europe/Paris"))
    st.caption(f"Dernière collecte : {updated:%d/%m/%Y à %H:%M:%S} — cache 5 minutes")
if snapshot.errors:
    with st.expander(f"Diagnostics ({len(snapshot.errors)})"):
        for error in snapshot.errors: st.warning(error)

st.subheader("Marché spot")
cols = st.columns(5)
cols[0].metric("PAXG / USD oz", fmt(snapshot.market.paxg_usd_oz, 2, " USD"))
cols[1].metric("EUR / USD", fmt(snapshot.market.eur_usd, 4))
cols[2].metric("Spot EUR / oz", fmt(snapshot.market.spot_eur_oz, 2, " €"))
cols[3].metric("Spot EUR / g", fmt(snapshot.market.spot_eur_g, 2, " €"))
cols[4].metric("Valeur théorique 20F", fmt(snapshot.theoretical_20f_eur, 2, " €"))
st.divider()

c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("Godot & Fils")
    a,b=st.columns(2); a.metric("Prix d'achat",fmt(snapshot.godot.achat,2," €")); b.metric("Cotation",fmt(snapshot.godot.cotation,2," €"))
    a,b=st.columns(2); a.metric("Valeur intrinsèque",fmt(snapshot.godot.intrinseque,2," €")); b.metric("Prime",fmt(snapshot.godot.prime,2," %"))
    st.metric("Écart achat / cotation",fmt(snapshot.godot.spread,2," €"))
with c2:
    st.subheader("Gold.fr / Comptoir")
    a,b=st.columns(2); a.metric("Cours Napoléon 20F",fmt(snapshot.goldfr.achat,2," €")); b.metric("Prime affichée",fmt(snapshot.goldfr.prime,2," %"))
    st.metric("Once EUR",fmt(snapshot.goldfr.once_eur,2," €/oz"))
with c3:
    st.subheader("AuCOFFRE.com")
    a,b=st.columns(2); a.metric("Meilleure offre 20F",fmt(snapshot.aucoffre.achat,2," €")); b.metric("Prime affichée",fmt(snapshot.aucoffre.prime,2," %"))
    st.caption(snapshot.aucoffre.product_name or "Napoléon 20F")
    x,y,z=st.columns(3); x.metric("Livrable",snapshot.aucoffre.livrable or "ND"); y.metric("Coffre",snapshot.aucoffre.coffre or "ND"); z.metric("Fiscalité",snapshot.aucoffre.fiscalite or "ND")

st.divider(); st.subheader("Comparaison")
best=snapshot.best_offer; cols=st.columns(4)
cols[0].metric("Meilleur vendeur", best.shop if best else "Indisponible")
cols[1].metric("Meilleur prix", fmt(best.price if best else None,2," €"))
cols[2].metric("Écart entre vendeurs", fmt(snapshot.vendor_difference,2," €"))
cols[3].metric("Économie", fmt(snapshot.vendor_saving_pct,2," %"))
rows=[
    {"Source":"Godot","Prix achat (€)":snapshot.godot.achat,"Prime (%)":snapshot.godot.prime,"Écart au théorique (€)":snapshot.godot_gap},
    {"Source":"Gold.fr","Prix achat (€)":snapshot.goldfr.achat,"Prime (%)":snapshot.goldfr.prime,"Écart au théorique (€)":snapshot.goldfr_gap},
    {"Source":"AuCOFFRE","Prix achat (€)":snapshot.aucoffre.achat,"Prime (%)":snapshot.aucoffre.prime,"Écart au théorique (€)":snapshot.aucoffre_gap},
]
price_labels=[r["Source"] for r in rows if r["Prix achat (€)"] is not None]; price_values=[r["Prix achat (€)"] for r in rows if r["Prix achat (€)"] is not None]
premium_labels=[r["Source"] for r in rows if r["Prime (%)"] is not None]; premium_values=[r["Prime (%)"] for r in rows if r["Prime (%)"] is not None]
a,b=st.columns(2)
with a: st.plotly_chart(bar_chart(price_labels+(["Théorique"] if snapshot.theoretical_20f_eur else []), price_values+([snapshot.theoretical_20f_eur] if snapshot.theoretical_20f_eur else []), " €", "EUR"), use_container_width=True)
with b: st.plotly_chart(bar_chart(premium_labels,premium_values," %","Prime (%)"),use_container_width=True)
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
st.info("AuCOFFRE peut afficher plusieurs offres pour un même Napoléon. Le tableau retient automatiquement la moins chère de la première page triée par prix croissant, hors produits explicitement marqués « Jeton ».")
st.caption("Données publiques, susceptibles d'évoluer. Ce tableau de bord ne constitue pas un conseil financier.")
