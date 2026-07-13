from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from services.http import get_json, get_text
from services.parsers import GodotQuote, GoldFrQuote, parse_godot, parse_goldfr

BINANCE_BASE = "https://api.binance.com/api/v3/ticker/price"
GODOT_URL = "https://www.achat-or-et-argent.fr/or/20-francs-marianne-coq/17"
GOLDFR_URL = "https://www.gold.fr/achat-or/napoleon-or-20-francs-louis-or/"
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
    return float(get_json(f"{BINANCE_BASE}?symbol={symbol}")["price"])


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
    spot_eur_oz = paxg / eurusd if paxg and eurusd else None
    spot_eur_g = spot_eur_oz / TROY_OUNCE_GRAMS if spot_eur_oz else None
    return MarketData(paxg, eurusd, spot_eur_oz, spot_eur_g)


def load_snapshot() -> MarketSnapshot:
    errors: list[str] = []
    market = load_market(errors)
    try:
        godot = parse_godot(get_text(GODOT_URL))
    except Exception as exc:
        errors.append(f"Godot : {exc}")
        godot = GodotQuote(None, None, None, None, None, None)
    try:
        goldfr = parse_goldfr(get_text(GOLDFR_URL))
    except Exception as exc:
        errors.append(f"Gold.fr : {exc}")
        goldfr = GoldFrQuote(None, None, None)

    theoretical = round(market.spot_eur_g * FINE_GOLD_20F_GRAMS, 2) if market.spot_eur_g is not None else None
    offers = []
    if godot.achat is not None:
        offers.append(BestOffer("Godot", godot.achat))
    if goldfr.achat is not None:
        offers.append(BestOffer("Gold.fr", goldfr.achat))
    best = min(offers, key=lambda x: x.price) if offers else None

    if godot.achat is not None and goldfr.achat is not None:
        difference = round(abs(godot.achat - goldfr.achat), 2)
        highest = max(godot.achat, goldfr.achat)
        saving_pct = round(difference / highest * 100, 2) if highest else None
    else:
        difference = saving_pct = None

    godot_gap = round(godot.achat - theoretical, 2) if godot.achat is not None and theoretical is not None else None
    goldfr_gap = round(goldfr.achat - theoretical, 2) if goldfr.achat is not None and theoretical is not None else None

    return MarketSnapshot(
        datetime.now(timezone.utc), market, godot, goldfr, theoretical, best,
        difference, saving_pct, godot_gap, goldfr_gap, tuple(errors)
    )
