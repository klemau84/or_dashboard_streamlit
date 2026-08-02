from __future__ import annotations
from zoneinfo import ZoneInfo
import streamlit as st
from services.data import PRODUCTS, ProductSnapshot, build_scenarios, load_product_snapshot

st.set_page_config(page_title="Tableau de bord Or V6.1", page_icon="🟡", layout="wide")


def fmt(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "Indisponible"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",") + suffix


@st.cache_data(ttl=300, show_spinner=False)
def get_data(product_key: str) -> ProductSnapshot:
    return load_product_snapshot(product_key)


if "product_key" not in st.session_state:
    st.session_state.product_key = PRODUCTS[0].key
if "selected_offer_index" not in st.session_state:
    st.session_state.selected_offer_index = 0

st.title("🟡 Tableau de bord Or — V6.1")
st.caption("Choisir un produit, puis comparer les offres réellement détectées et leur coût estimé hors livraison et fiscalité personnelle.")

st.subheader("Choisir le produit")
product_cols = st.columns(3)
for idx, product in enumerate(PRODUCTS):
    active = st.session_state.product_key == product.key
    label = f"{'✓ ' if active else ''}{product.label}"
    if product_cols[idx % 3].button(label, key=f"product_{product.key}", use_container_width=True, type="primary" if active else "secondary"):
        st.session_state.product_key = product.key
        st.session_state.selected_offer_index = 0
        st.rerun()

with st.sidebar:
    st.header("Simulation")
    horizon_months = st.slider("Durée de conservation", 0, 60, 12, 1, format="%d mois")
    st.subheader("Frais constatés")
    goldfr_commission = st.toggle("Gold.fr : téléphone/e-mail (+3,3 %, min. 10 €)", value=False)
    godot_extra = st.number_input("Godot : surcharge panier (%)", 0.0, 20.0, 0.0, 0.1)
    goldfr_extra = st.number_input("Gold.fr : surcharge panier (%)", 0.0, 20.0, 0.0, 0.1)
    st.caption("Les surcharges restent à zéro tant qu'elles ne sont pas réellement observées dans un panier ou un devis.")

left, right = st.columns([1, 4])
with left:
    if st.button("Actualiser", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

snapshot = get_data(st.session_state.product_key)
with right:
    updated = snapshot.timestamp.astimezone(ZoneInfo("Europe/Paris"))
    st.caption(f"Dernière collecte : {updated:%d/%m/%Y à %H:%M:%S} — cache 5 minutes")

if snapshot.errors:
    with st.expander(f"Diagnostics ({len(snapshot.errors)})"):
        for error in snapshot.errors:
            st.warning(error)

st.subheader(snapshot.product.label)
head = st.columns(5)
head[0].metric("Type", snapshot.product.family)
head[1].metric("Or fin", fmt(snapshot.product.fine_gold_g, 4, " g"))
head[2].metric("Spot EUR/g", fmt(snapshot.market.spot_eur_g, 2, " €"))
head[3].metric("Valeur métallique", fmt(snapshot.theoretical_value, 2, " €"))
head[4].metric("Liquidité indicative", f"{snapshot.product.liquidity_score}/100")
st.caption(f"Fiscalité produit : {snapshot.product.tax_label}")
st.divider()

st.subheader("Choisir une offre AuCOFFRE")
selected_offer = None
if snapshot.aucoffre_offers:
    visible = list(snapshot.aucoffre_offers[:9])
    card_cols = st.columns(3)
    for i, offer in enumerate(visible):
        with card_cols[i % 3]:
            selected = st.session_state.selected_offer_index == i
            with st.container(border=True):
                st.markdown(f"### {fmt(offer.price, 2, ' €')}")
                st.write(f"Prime affichée : **{fmt(offer.premium, 2, ' %')}**")
                st.write(f"État : **{offer.etat or 'ND'}**")
                st.write(f"Livrable : **{offer.livrable or 'ND'}**")
                st.write(f"Coffre : **{offer.coffre or 'ND'}**")
                st.write(f"{'LSP' if offer.is_lsp else 'Standard'}")
                if st.button("Sélectionnée" if selected else "Choisir", key=f"offer_{i}", use_container_width=True, type="primary" if selected else "secondary"):
                    st.session_state.selected_offer_index = i
                    st.rerun()
    index = min(st.session_state.selected_offer_index, len(visible) - 1)
    selected_offer = visible[index]
    with st.expander("Détails de l'offre sélectionnée"):
        st.write(selected_offer.product_name)
        st.write(f"Fiscalité affichée : {selected_offer.fiscalite or 'ND'}")
else:
    st.info("Aucune offre AuCOFFRE fiable n'a été détectée pour ce produit. Le tableau n'affiche plus une offre Napoléon par erreur.")

st.divider()
st.subheader("Comparaison du coût réel estimé")
scenarios = build_scenarios(snapshot, selected_offer, horizon_months, goldfr_commission, godot_extra, goldfr_extra)

if not scenarios:
    st.warning("Aucune offre comparable n'est disponible pour ce produit. La valeur métallique reste affichée comme repère.")
else:
    valid = [s for s in scenarios if s.total_cost is not None]
    best = min(valid, key=lambda s: s.total_cost) if valid else None
    best_score = max((s for s in valid if s.score is not None), key=lambda s: s.score, default=None)
    verdict = st.columns(4)
    verdict[0].metric("Meilleur coût", best.vendor if best else "ND")
    verdict[1].metric(f"Après {horizon_months} mois", fmt(best.total_cost if best else None, 2, " €"))
    verdict[2].metric("Meilleur score", best_score.vendor if best_score else "ND")
    verdict[3].metric("Score", f"{best_score.score}/100" if best_score and best_score.score is not None else "ND")

    cards = st.columns(len(scenarios))
    for col, scenario in zip(cards, scenarios):
        with col:
            with st.container(border=True):
                st.markdown(f"### {scenario.vendor}")
                st.caption(scenario.label)
                st.metric("Prix affiché", fmt(scenario.displayed_price, 2, " €"))
                st.metric("Coût d'entrée", fmt(scenario.entry_cost, 2, " €"))
                st.metric(f"Coût total {horizon_months} mois", fmt(scenario.total_cost, 2, " €"))
                st.metric("Prime réelle", fmt(scenario.premium_pct, 2, " %"))
                st.metric("Point mort", fmt(scenario.point_mort_pct, 2, " %"))
                st.metric("Score", f"{scenario.score}/100" if scenario.score is not None else "ND")
                st.caption(scenario.note)

st.divider()
with st.expander("Comprendre le calcul"):
    st.write("Le coût d'entrée ajoute uniquement les frais publics ou les surcharges que tu actives manuellement.")
    st.write("Pour AuCOFFRE non-LSP, la simulation applique prudemment 30 € par mois, correspondant au minimum officiel de facturation indiqué dans la version précédente du projet.")
    st.write("Le point mort mesure la hausse du métal nécessaire pour couvrir la prime et la garde, hors livraison, fiscalité personnelle et éventuel écart de rachat.")

st.caption("Comparateur indicatif. Vérifier le prix ferme, l'état exact, la livrabilité, les frais et les conditions contractuelles avant toute commande.")
