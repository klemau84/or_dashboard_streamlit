from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.data import MarketSnapshot, load_snapshot

st.set_page_config(page_title="Tableau de bord Or", page_icon="🟡", layout="wide")


def fmt(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "Indisponible"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",") + suffix


@st.cache_data(ttl=300, show_spinner=False)
def get_data() -> MarketSnapshot:
    return load_snapshot()


def bar_chart(labels: list[str], values: list[float], suffix: str, y_title: str) -> go.Figure:
    fig = go.Figure(go.Bar(x=labels, y=values, text=[fmt(v, 2, suffix) for v in values]))
    fig.update_traces(textposition="outside")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), yaxis_title=y_title, showlegend=False)
    return fig


st.title("🟡 Tableau de bord Or")
st.caption("Napoléon 20 francs — Binance, Godot & Fils et Gold.fr")

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
godot_col, goldfr_col = st.columns(2)
with godot_col:
    st.subheader("Godot & Fils")
    a, b = st.columns(2)
    a.metric("Prix d'achat", fmt(snapshot.godot.achat, 2, " €"))
    b.metric("Cotation", fmt(snapshot.godot.cotation, 2, " €"))
    a, b = st.columns(2)
    a.metric("Valeur intrinsèque", fmt(snapshot.godot.intrinseque, 2, " €"))
    b.metric("Prime", fmt(snapshot.godot.prime, 2, " %"))
    st.metric("Écart achat / cotation", fmt(snapshot.godot.spread, 2, " €"))

with goldfr_col:
    st.subheader("Gold.fr / Comptoir")
    a, b = st.columns(2)
    a.metric("Cours Napoléon 20F", fmt(snapshot.goldfr.achat, 2, " €"))
    b.metric("Prime affichée", fmt(snapshot.goldfr.prime, 2, " %"))
    st.metric("Once EUR", fmt(snapshot.goldfr.once_eur, 2, " €/oz"))

st.divider()
st.subheader("Comparaison")
best = snapshot.best_offer
cols = st.columns(4)
cols[0].metric("Meilleur vendeur", best.shop if best else "Indisponible")
cols[1].metric("Meilleur prix", fmt(best.price if best else None, 2, " €"))
cols[2].metric("Écart entre vendeurs", fmt(snapshot.vendor_difference, 2, " €"))
cols[3].metric("Économie", fmt(snapshot.vendor_saving_pct, 2, " %"))

price_labels, price_values = [], []
for label, value in (("Godot", snapshot.godot.achat), ("Gold.fr", snapshot.goldfr.achat), ("Théorique", snapshot.theoretical_20f_eur)):
    if value is not None:
        price_labels.append(label); price_values.append(value)

premium_labels, premium_values = [], []
for label, value in (("Godot", snapshot.godot.prime), ("Gold.fr", snapshot.goldfr.prime)):
    if value is not None:
        premium_labels.append(label); premium_values.append(value)

c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(bar_chart(price_labels, price_values, " €", "EUR"), use_container_width=True)
with c2:
    st.plotly_chart(bar_chart(premium_labels, premium_values, " %", "Prime (%)"), use_container_width=True)

st.dataframe(
    pd.DataFrame([
        {"Source": "Godot", "Prix achat (€)": snapshot.godot.achat, "Prime (%)": snapshot.godot.prime, "Écart au théorique (€)": snapshot.godot_gap},
        {"Source": "Gold.fr", "Prix achat (€)": snapshot.goldfr.achat, "Prime (%)": snapshot.goldfr.prime, "Écart au théorique (€)": snapshot.goldfr_gap},
    ]),
    hide_index=True,
    use_container_width=True,
)

st.caption("Données publiques, susceptibles d'évoluer. Ce tableau de bord ne constitue pas un conseil financier.")
