from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from services.http import get_json, get_text
from services.parsers import AuCoffreOffer, VendorQuote, parse_aucoffre_catalog, parse_godot_napoleon, parse_goldfr_napoleon

BINANCE_BASES = (
    "https://data-api.binance.vision", "https://api-gcp.binance.com", "https://api1.binance.com",
    "https://api2.binance.com", "https://api3.binance.com", "https://api4.binance.com", "https://api.binance.com",
)
TROY_OUNCE_GRAMS = 31.1034768
GODOT_NAPOLEON_URL = "https://www.achat-or-et-argent.fr/or/20-francs-marianne-coq/17"
GOLDFR_NAPOLEON_URL = "https://www.gold.fr/achat-or/napoleon-or-20-francs-louis-or/"

@dataclass(frozen=True)
class ProductSpec:
    key: str
    label: str
    family: str
    fine_gold_g: float
    aliases: tuple[str, ...]
    liquidity_score: int
    tax_label: str
    aucoffre_urls: tuple[str, ...]


PRODUCTS: tuple[ProductSpec, ...] = (
    ProductSpec("napoleon", "Napoléon 20 F", "Pièce", 5.805,
                ("Napoléon 20F", "Napoléon 20 F", "20 Francs Marianne Coq"), 100,
                "Cours légal / métal précieux",
                ("https://www.aucoffre.com/recherche/metal-1/marketing_list-5/stype-1/produit",)),
    ProductSpec("suisse20", "20 F Suisse", "Pièce", 5.805,
                ("20 Francs Suisse", "20 F Suisse", "Vreneli"), 96,
                "Cours légal / métal précieux",
                ("https://www.aucoffre.com/recherche/metal-1/marketing_list-6/stype-5/produit",)),
    ProductSpec("souverain", "Souverain", "Pièce", 7.3224,
                ("Souverain Elisabeth II", "Souverain George V", "Souverain"), 92,
                "Cours légal / métal précieux",
                ("https://www.aucoffre.com/recherche/marketing_list-8/stype-6/produit",
                 "https://www.aucoffre.com/recherche/stype-3/produit")),
    ProductSpec("maple", "Maple Leaf 1 oz", "Pièce", 31.1034768,
                ("Maple Leaf 1 once - 50 Dollars", "Maple Leaf 1 once", "Maple Leaf 1 oz"), 94,
                "Cours légal",
                ("https://www.aucoffre.com/recherche/marketing_list-12/stype-18/produit",)),
    ProductSpec("krugerrand", "Krugerrand 1 oz", "Pièce", 31.1034768,
                ("Krugerrand 1 once", "Krugerrand 1 oz"), 95,
                "Cours légal",
                ("https://www.aucoffre.com/recherche/marketing_list-7/stype-2/produit",)),
    ProductSpec("philharmonique", "Philharmonique 1 oz", "Pièce", 31.1034768,
                ("Philharmonique de Vienne 1 once - 100 Euros", "Philharmonique 1 once"), 91,
                "Cours légal",
                ("https://www.aucoffre.com/recherche/marketing_list-14/stype-40/produit",)),
    ProductSpec("lingotin20", "Lingotin 20 g", "Lingotin", 20.0,
                ("20 grammes d'or pur", "Lingotin Or 20 grammes", "Lingotin 20 grammes"), 82,
                "Métal précieux",
                ("https://www.aucoffre.com/recherche/metal-1/product_type-2/produit",)),
    ProductSpec("lingotin50", "Lingotin 50 g", "Lingotin", 50.0,
                ("50 grammes d'or pur", "Lingotin Or 50 grammes", "Lingotin 50 grammes"), 86,
                "Métal précieux",
                ("https://www.aucoffre.com/recherche/metal-1/product_type-2/produit",)),
    ProductSpec("lingotin100", "Lingotin 100 g", "Lingotin", 100.0,
                ("100 grammes d'or pur (LSP)", "100 grammes d'or pur", "Lingotin 100 grammes"), 89,
                "Métal précieux",
                ("https://www.aucoffre.com/recherche/metal-1/marketing_list-21/stype-80/produit",)),
)


@dataclass(frozen=True)
class MarketData:
    paxg_usd_oz: float | None
    eur_usd: float | None
    spot_eur_oz: float | None
    spot_eur_g: float | None


@dataclass(frozen=True)
class ProductSnapshot:
    timestamp: datetime
    market: MarketData
    product: ProductSpec
    theoretical_value: float | None
    godot: VendorQuote | None
    goldfr: VendorQuote | None
    aucoffre_offers: tuple[AuCoffreOffer, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class Scenario:
    vendor: str
    label: str
    displayed_price: float | None
    entry_cost: float | None
    storage_cost: float
    total_cost: float | None
    premium_pct: float | None
    point_mort_pct: float | None
    score: int | None
    note: str


def binance_price(symbol: str) -> float:
    errors: list[str] = []
    for base in BINANCE_BASES:
        try:
            return float(get_json(f"{base}/api/v3/ticker/price?symbol={symbol}")["price"])
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("; ".join(errors[-2:]))


def load_market(errors: list[str]) -> MarketData:
    paxg = eurusd = None
    try:
        paxg = binance_price("PAXGUSDT")
    except Exception as exc:
        errors.append(f"Binance PAXGUSDT : {exc}")
    try:
        eurusd = binance_price("EURUSDT")
    except Exception as exc:
        errors.append(f"Binance EURUSDT : {exc}")
    spot_oz = paxg / eurusd if paxg is not None and eurusd else None
    spot_g = spot_oz / TROY_OUNCE_GRAMS if spot_oz is not None else None
    return MarketData(paxg, eurusd, spot_oz, spot_g)


def _load_aucoffre(product: ProductSpec, errors: list[str]) -> tuple[AuCoffreOffer, ...]:
    # Chaque produit utilise désormais sa propre page AuCOFFRE.
    # La V6 interrogeait aussi la page Napoléon pour tous les boutons, ce qui
    # produisait de fausses offres à 710,47 € sur le Souverain et les autres produits.
    collected: dict[tuple, AuCoffreOffer] = {}
    for url in product.aucoffre_urls:
        try:
            offers = parse_aucoffre_catalog(get_text(url), product.aliases)
            for offer in offers:
                key = (offer.product_name, offer.price, offer.livrable, offer.is_lsp)
                collected[key] = offer
        except Exception as exc:
            errors.append(f"AuCOFFRE ({product.label}) : {exc}")
    return tuple(sorted(collected.values(), key=lambda offer: offer.price))


def load_product_snapshot(product_key: str) -> ProductSnapshot:
    product = next((p for p in PRODUCTS if p.key == product_key), PRODUCTS[0])
    errors: list[str] = []
    market = load_market(errors)
    theoretical = market.spot_eur_g * product.fine_gold_g if market.spot_eur_g is not None else None
    godot = goldfr = None
    if product.key == "napoleon":
        try:
            godot = parse_godot_napoleon(get_text(GODOT_NAPOLEON_URL), GODOT_NAPOLEON_URL)
        except Exception as exc:
            errors.append(f"Godot : {exc}")
        try:
            goldfr = parse_goldfr_napoleon(get_text(GOLDFR_NAPOLEON_URL), GOLDFR_NAPOLEON_URL)
        except Exception as exc:
            errors.append(f"Gold.fr : {exc}")
    aucoffre = _load_aucoffre(product, errors)
    return ProductSnapshot(datetime.now(timezone.utc), market, product, theoretical, godot, goldfr, aucoffre, tuple(errors))


def build_scenarios(snapshot: ProductSnapshot, selected_offer: AuCoffreOffer | None, horizon_months: int,
                    goldfr_phone_fee: bool, godot_extra_pct: float, goldfr_extra_pct: float) -> list[Scenario]:
    rows: list[Scenario] = []

    def make(vendor: str, label: str, price: float | None, fee_pct: float, storage: float, opacity_penalty: int, note: str) -> Scenario:
        entry = price * (1 + fee_pct / 100) if price is not None else None
        total = entry + storage if entry is not None else None
        premium = ((entry / snapshot.theoretical_value) - 1) * 100 if entry is not None and snapshot.theoretical_value else None
        point_mort = ((total / snapshot.theoretical_value) - 1) * 100 if total is not None and snapshot.theoretical_value else None
        score = None
        if premium is not None and point_mort is not None:
            raw = 100 - max(premium, 0) * 2.2 - max(point_mort - premium, 0) * 1.5 - opacity_penalty
            raw += (snapshot.product.liquidity_score - 85) * 0.25
            score = max(0, min(100, round(raw)))
        return Scenario(vendor, label, price, entry, storage, total, premium, point_mort, score, note)

    if snapshot.godot and snapshot.godot.price is not None:
        rows.append(make("Godot", "Prix web", snapshot.godot.price, godot_extra_pct, 0, 4, "Surcharge manuelle uniquement si elle est constatée."))
    if snapshot.goldfr and snapshot.goldfr.price is not None:
        phone_pct = 3.3 if goldfr_phone_fee else 0
        effective = phone_pct + goldfr_extra_pct
        rows.append(make("Gold.fr", "Cours public", snapshot.goldfr.price, effective, 0, 9, "Le cours public n'est pas forcément un prix de panier ferme."))
    if selected_offer is not None:
        storage = 0.0 if selected_offer.is_lsp else 30.0 * max(horizon_months, 0)
        label = "LSP" if selected_offer.is_lsp else "Standard"
        rows.append(make("AuCOFFRE", label, selected_offer.price, 0.5, storage, 6 if selected_offer.is_lsp else 12,
                         "0,5 % à l'achat. Garde nulle seulement si les conditions LSP sont réellement respectées."))
    return rows
