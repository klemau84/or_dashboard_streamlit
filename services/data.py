from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from services.http import get_json, get_text
from services.parsers import (
    GodotQuote,
    GoldFrQuote,
    parse_godot,
    parse_goldfr,
)

# Plusieurs endpoints Binance sont testés successivement.
# data-api.binance.vision est dédié aux données publiques de marché.
BINANCE_BASES = (
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
    "https://api.binance.com",
)

GODOT_URL = (
    "https://www.achat-or-et-argent.fr/"
    "or/20-francs-marianne-coq/17"
)

GOLDFR_URL = (
    "https://www.gold.fr/"
    "achat-or/napoleon-or-20-francs-louis-or/"
)

FINE_GOLD_20F_GRAMS = 5.805
TROY_OUNCE_GRAMS = 31.1034768


@dataclass(frozen=True)
class MarketData:
    paxg_usd_oz: float | None
    eur_usd: float | None
    spot_eur_oz: float | None
    spot_eur_g: float | None


@dataclass(frozen=True)
class BestOffer:
    shop: str
    price: float


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: datetime
    market: MarketData
    godot: GodotQuote
    goldfr: GoldFrQuote
    theoretical_20f_eur: float | None
    best_offer: BestOffer | None
    vendor_difference: float | None
    vendor_saving_pct: float | None
    godot_gap: float | None
    goldfr_gap: float | None
    errors: tuple[str, ...]


def binance_price(symbol: str) -> float:
    """
    Essaie successivement plusieurs endpoints Binance.

    Une erreur n'est levée que si tous les endpoints échouent.
    """
    failures: list[str] = []

    for base_url in BINANCE_BASES:
        url = f"{base_url}/api/v3/ticker/price?symbol={symbol}"

        try:
            payload = get_json(url, timeout=12)

            price = payload.get("price")
            if price is None:
                raise ValueError(f"champ price absent : {payload}")

            value = float(price)
            if value <= 0:
                raise ValueError(f"prix invalide : {value}")

            return value

        except Exception as exc:
            failures.append(f"{base_url}: {exc}")

    details = " | ".join(failures)
    raise RuntimeError(
        f"aucun endpoint Binance disponible pour {symbol}. "
        f"Détails : {details}"
    )


def load_market(errors: list[str]) -> MarketData:
    paxg: float | None = None
    eurusd: float | None = None

    try:
        paxg = binance_price("PAXGUSDT")
    except Exception as exc:
        errors.append(f"Binance PAXGUSDT : {exc}")

    try:
        eurusd = binance_price("EURUSDT")
    except Exception as exc:
        errors.append(f"Binance EURUSDT : {exc}")

    spot_eur_oz: float | None = None
    spot_eur_g: float | None = None

    if paxg is not None and eurusd is not None and eurusd > 0:
        spot_eur_oz = paxg / eurusd
        spot_eur_g = spot_eur_oz / TROY_OUNCE_GRAMS

    return MarketData(
        paxg_usd_oz=paxg,
        eur_usd=eurusd,
        spot_eur_oz=spot_eur_oz,
        spot_eur_g=spot_eur_g,
    )


def load_snapshot() -> MarketSnapshot:
    errors: list[str] = []
    market = load_market(errors)

    try:
        godot = parse_godot(get_text(GODOT_URL))
    except Exception as exc:
        errors.append(f"Godot : {exc}")
        godot = GodotQuote(
            achat=None,
            vente=None,
            cotation=None,
            intrinseque=None,
            prime=None,
            spread=None,
        )

    try:
        goldfr = parse_goldfr(get_text(GOLDFR_URL))
    except Exception as exc:
        errors.append(f"Gold.fr : {exc}")
        goldfr = GoldFrQuote(
            achat=None,
            prime=None,
            once_eur=None,
        )

    # Si Gold.fr ne fournit pas l'once, on utilise le spot EUR/oz calculé.
    if goldfr.once_eur is None and market.spot_eur_oz is not None:
        goldfr = GoldFrQuote(
            achat=goldfr.achat,
            prime=goldfr.prime,
            once_eur=round(market.spot_eur_oz, 2),
        )

    theoretical: float | None = None
    if market.spot_eur_g is not None:
        theoretical = round(
            market.spot_eur_g * FINE_GOLD_20F_GRAMS,
            2,
        )

    offers: list[BestOffer] = []

    if godot.achat is not None:
        offers.append(BestOffer(shop="Godot", price=godot.achat))

    if goldfr.achat is not None:
        offers.append(BestOffer(shop="Gold.fr", price=goldfr.achat))

    best = min(offers, key=lambda offer: offer.price) if offers else None

    difference: float | None = None
    saving_pct: float | None = None

    if godot.achat is not None and goldfr.achat is not None:
        difference = round(abs(godot.achat - goldfr.achat), 2)
        highest = max(godot.achat, goldfr.achat)

        if highest > 0:
            saving_pct = round((difference / highest) * 100, 2)

    godot_gap: float | None = None
    goldfr_gap: float | None = None

    if godot.achat is not None and theoretical is not None:
        godot_gap = round(godot.achat - theoretical, 2)

    if goldfr.achat is not None and theoretical is not None:
        goldfr_gap = round(goldfr.achat - theoretical, 2)

    return MarketSnapshot(
        timestamp=datetime.now(timezone.utc),
        market=market,
        godot=godot,
        goldfr=goldfr,
        theoretical_20f_eur=theoretical,
        best_offer=best,
        vendor_difference=difference,
        vendor_saving_pct=saving_pct,
        godot_gap=godot_gap,
        goldfr_gap=goldfr_gap,
        errors=tuple(errors),
    )
