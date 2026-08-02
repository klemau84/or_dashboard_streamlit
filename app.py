from __future__ import annotations
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from services.data import MarketSnapshot, compute_vendor_costs, load_snapshot

st.set_page_config(page_title="Tableau de bord Or V4", page_icon="🟡", layout="wide")


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
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), yaxis_title=y_title, showlegend=False)
    return fig


st.title("🟡 Tableau de bord Or — V4")
st.caption("Napoléon 20 francs — comparaison du prix affiché et du coût réel hors livraison")

with st.sidebar:
    st.header("Hypothèses de coût")
    horizon_months = st.slider("Durée de conservation simulée", 0, 60, 12, 1, format="%d mois")
    st.subheader("AuCOFFRE")
    aucoffre_minimum = st.toggle("Appliquer le minimum de facturation de 30 €", value=True)
    aucoffre_lsp = st.toggle("LSP validé chaque mois (garde gratuite)", value=False)
    st.subheader("Gold.fr")
    goldfr_commission = st.toggle("Achat par téléphone/e-mail : commission 3,3 %", value=True)
    st.subheader("Ajustements manuels")
    godot_extra = st.number_input("Godot : surcharge supplémentaire (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
    goldfr_extra = st.number_input("Gold.fr : surcharge supplémentaire (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
    st.caption("Les réglages évitent de présenter comme certain un coût qui dépend du canal de commande ou du panier final.")

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

costs = compute_vendor_costs(
    snapshot=snapshot,
    horizon_months=horizon_months,
    aucoffre_apply_minimum_invoice=aucoffre_minimum,
    aucoffre_lsp_free_storage=aucoffre_lsp,
    goldfr_phone_email_commission=goldfr_commission,
    godot_extra_pct=godot_extra,
    goldfr_extra_pct=goldfr_extra,
)
valid_costs = [c for c in costs if c.cost_after_horizon is not None]
best_entry = min((c for c in costs if c.entry_cost is not None), key=lambda c: c.entry_cost, default=None)
best_horizon = min(valid_costs, key=lambda c: c.cost_after_horizon, default=None)

st.subheader("Marché spot")
cols = st.columns(5)
cols[0].metric("PAXG / USD oz", fmt(snapshot.market.paxg_usd_oz, 2, " USD"))
cols[1].metric("EUR / USD", fmt(snapshot.market.eur_usd, 4))
cols[2].metric("Spot EUR / oz", fmt(snapshot.market.spot_eur_oz, 2, " €"))
cols[3].metric("Spot EUR / g", fmt(snapshot.market.spot_eur_g, 2, " €"))
cols[4].metric("Valeur théorique 20F", fmt(snapshot.theoretical_20f_eur, 2, " €"))
st.divider()

st.subheader("Prix publics collectés")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("### Godot & Fils")
    st.metric("Prix affiché", fmt(snapshot.godot.achat, 2, " €"))
    st.metric("Prime affichée", fmt(snapshot.godot.prime, 2, " %"))
    st.caption("Le prix web est traité comme prix d'entrée, sauf surcharge manuelle.")
with c2:
    st.markdown("### Gold.fr / Comptoir")
    st.metric("Cours affiché", fmt(snapshot.goldfr.achat, 2, " €"))
    st.metric("Prime affichée", fmt(snapshot.goldfr.prime, 2, " %"))
    st.caption("Le cours affiché n'est pas forcément le prix final : la commission téléphone/e-mail est intégrée selon le réglage.")
with c3:
    st.markdown("### AuCOFFRE.com")
    st.metric("Offre sélectionnée", fmt(snapshot.aucoffre.achat, 2, " €"))
    st.metric("Prime affichée", fmt(snapshot.aucoffre.prime, 2, " %"))
    st.caption(snapshot.aucoffre.product_name or "Napoléon 20F")
    st.caption(f"Livrable : {snapshot.aucoffre.livrable or 'ND'} · Coffre : {snapshot.aucoffre.coffre or 'ND'} · Fiscalité : {snapshot.aucoffre.fiscalite or 'ND'}")

st.divider()
st.subheader("Coût réel estimé — hors livraison")
summary_cols = st.columns(4)
summary_cols[0].metric("Meilleur coût d'entrée", best_entry.shop if best_entry else "Indisponible")
summary_cols[1].metric("Montant à l'achat", fmt(best_entry.entry_cost if best_entry else None, 2, " €"))
summary_cols[2].metric(f"Meilleur après {horizon_months} mois", best_horizon.shop if best_horizon else "Indisponible")
summary_cols[3].metric("Coût total simulé", fmt(best_horizon.cost_after_horizon if best_horizon else None, 2, " €"))

rows = []
for cost in costs:
    premium_effective = None
    if cost.entry_cost is not None and snapshot.theoretical_20f_eur:
        premium_effective = (cost.entry_cost / snapshot.theoretical_20f_eur - 1) * 100
    rows.append({
        "Source": cost.shop,
        "Prix affiché (€)": cost.displayed_price,
        "Frais achat (€)": cost.purchase_fee_eur,
        "Coût d'entrée (€)": cost.entry_cost,
        f"Garde {horizon_months} mois (€)": cost.storage_cost,
        f"Coût total {horizon_months} mois (€)": cost.cost_after_horizon,
        "Prime réelle entrée (%)": round(premium_effective, 2) if premium_effective is not None else None,
        "Frais de revente annoncés (%)": cost.exit_fee_pct,
    })

df = pd.DataFrame(rows)
st.dataframe(df, hide_index=True, use_container_width=True)

entry_labels = [c.shop for c in costs if c.entry_cost is not None]
entry_values = [c.entry_cost for c in costs if c.entry_cost is not None]
horizon_labels = [c.shop for c in costs if c.cost_after_horizon is not None]
horizon_values = [c.cost_after_horizon for c in costs if c.cost_after_horizon is not None]
a, b = st.columns(2)
with a:
    st.plotly_chart(bar_chart(entry_labels, entry_values, " €", "Coût d'entrée hors livraison"), use_container_width=True)
with b:
    st.plotly_chart(bar_chart(horizon_labels, horizon_values, " €", f"Coût après {horizon_months} mois"), use_container_width=True)

st.subheader("Détail des frais intégrés")
for cost in costs:
    with st.expander(cost.shop):
        st.write(cost.note)
        if cost.shop == "AuCOFFRE":
            st.write("La commission de revente de 3 % est affichée séparément : elle n'est pas ajoutée au coût d'achat, mais elle compte pour le point mort à la sortie.")
        elif cost.shop == "Gold.fr":
            st.write("Les conditions générales distinguent les opérations en ligne et les transactions par téléphone/e-mail. Le bouton latéral permet de tester les deux cas.")
        else:
            st.write("Aucun frais d'achat distinct n'a été ajouté par défaut. Utilise la surcharge manuelle si le panier ou l'agence en facture un.")

st.warning(
    "Les sites ne publient pas tous un prix final comparable. La V4 sépare donc le prix affiché, les frais d'achat, la garde et les frais de sortie. "
    "La livraison est volontairement exclue. Vérifie toujours le montant final avant validation."
)
st.markdown(
    "**Sources tarifaires intégrées :** "
    "[AuCOFFRE — tarifs](https://www.aucoffre.com/acheter/tarifs-aucoffre-com) · "
    "[Gold.fr — conditions générales](https://www.gold.fr/informations-sur-l-or/nous-connaitre/conditions-generales-dutilisation) · "
    "[Godot — moyens de paiement](https://www.achat-or-et-argent.fr/infos-1346-quels-sont-les-moyens-de-paiement-acceptes-chez-godot-fils)"
)
st.caption("Données publiques susceptibles d'évoluer. Ce tableau de bord ne constitue pas un conseil financier.")
