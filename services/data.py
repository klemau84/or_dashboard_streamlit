from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from services.http import get_json, get_text
from services.parsers import AuCoffreQuote, GodotQuote, GoldFrQuote, parse_aucoffre, parse_godot, parse_goldfr

BINANCE_BASES = (
    "https://data-api.binance.vision", "https://api-gcp.binance.com", "https://api1.binance.com",
    "https://api2.binance.com", "https://api3.binance.com", "https://api4.binance.com", "https://api.binance.com",
)
GODOT_URL = "https://www.achat-or-et-argent.fr/or/20-francs-marianne-coq/17"
GOLDFR_URL = "https://www.gold.fr/achat-or/napoleon-or-20-francs-louis-or/"
AUCOFFRE_URL = "https://www.aucoffre.com/recherche/marketing_list-5/stype-1/stype-320/produit"
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
    aucoffre: AuCoffreQuote
    theoretical_20f_eur: float | None
    best_offer: BestOffer | None
    vendor_difference: float | None
    vendor_saving_pct: float | None
    godot_gap: float | None
    goldfr_gap: float | None
    aucoffre_gap: float | None
    errors: tuple[str, ...]


def binance_price(symbol: str) -> float:
    failures = []
    for base_url in BINANCE_BASES:
        try:
            payload = get_json(f"{base_url}/api/v3/ticker/price?symbol={symbol}", timeout=12)
            value = float(payload["price"])
            if value <= 0:
                raise ValueError(f"prix invalide : {value}")
            return value
        except Exception as exc:
            failures.append(f"{base_url}: {exc}")
    raise RuntimeError(f"aucun endpoint Binance disponible pour {symbol}. Détails : {' | '.join(failures)}")


def load_market(errors: list[str]) -> MarketData:
    paxg = eurusd = None
    try: paxg = binance_price("PAXGUSDT")
    except Exception as exc: errors.append(f"Binance PAXGUSDT : {exc}")
    try: eurusd = binance_price("EURUSDT")
    except Exception as exc: errors.append(f"Binance EURUSDT : {exc}")
    spot_eur_oz = paxg / eurusd if paxg is not None and eurusd else None
    spot_eur_g = spot_eur_oz / TROY_OUNCE_GRAMS if spot_eur_oz is not None else None
    return MarketData(paxg, eurusd, spot_eur_oz, spot_eur_g)


def load_snapshot() -> MarketSnapshot:
    errors: list[str] = []
    market = load_market(errors)
    try: godot = parse_godot(get_text(GODOT_URL))
    except Exception as exc:
        errors.append(f"Godot : {exc}")
        godot = GodotQuote(None, None, None, None, None, None)
    try: goldfr = parse_goldfr(get_text(GOLDFR_URL))
    except Exception as exc:
        errors.append(f"Gold.fr : {exc}")
        goldfr = GoldFrQuote(None, None, None)
    try: aucoffre = parse_aucoffre(get_text(AUCOFFRE_URL))
    except Exception as exc:
        errors.append(f"AuCOFFRE : {exc}")
        aucoffre = AuCoffreQuote(None, None, None, None, None, None)
    if goldfr.once_eur is None and market.spot_eur_oz is not None:
        goldfr = GoldFrQuote(goldfr.achat, goldfr.prime, round(market.spot_eur_oz, 2))
    theoretical = round(market.spot_eur_g * FINE_GOLD_20F_GRAMS, 2) if market.spot_eur_g is not None else None
    offers = [BestOffer(shop, price) for shop, price in (
        ("Godot", godot.achat), ("Gold.fr", goldfr.achat), ("AuCOFFRE", aucoffre.achat)
    ) if price is not None]
    best = min(offers, key=lambda o: o.price) if offers else None
    prices = [o.price for o in offers]
    difference = round(max(prices) - min(prices), 2) if len(prices) >= 2 else None
    saving_pct = round(difference / max(prices) * 100, 2) if difference is not None and max(prices) > 0 else None
    gap = lambda p: round(p - theoretical, 2) if p is not None and theoretical is not None else None
    return MarketSnapshot(datetime.now(timezone.utc), market, godot, goldfr, aucoffre, theoretical, best,
                          difference, saving_pct, gap(godot.achat), gap(goldfr.achat), gap(aucoffre.achat), tuple(errors))
