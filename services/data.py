from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from services.http import get_json, get_text
from services.parsers import AuCoffreQuote, GodotQuote, GoldFrQuote, parse_aucoffre, parse_godot, parse_goldfr

BINANCE_BASES = (
    "https://data-api.binance.vision", "https://api-gcp.binance.com", "https://api1.binance.com",
    "https://api2.binance.com", "https://api3.binance.com", "https://api4.binance.com", "https://api.binance.com",
)
GODOT_URL = "https://www.achat-or-et-argent.fr/or/20-francs-marianne-coq/17"
GOLDFR_URL = "https://www.gold.fr/achat-or/napoleon-or-20-francs-louis-or/"
AUCOFFRE_URL = "https://www.aucoffre.com/recherche/marketing_list-5/stype-1/stype-320/produit"
AUCOFFRE_TARIFFS_URL = "https://www.aucoffre.com/acheter/tarifs-aucoffre-com"
GOLDFR_TERMS_URL = "https://www.gold.fr/informations-sur-l-or/nous-connaitre/conditions-generales-dutilisation"
FINE_GOLD_20F_GRAMS = 5.805
TROY_OUNCE_GRAMS = 31.1034768

@dataclass(frozen=True)
class MarketData:
    paxg_usd_oz: float | None
    eur_usd: float | None
    spot_eur_oz: float | None
    spot_eur_g: float | None

@dataclass(frozen=True)
class FeeProfile:
    purchase_fee_pct: float = 0.0
    purchase_fee_min_eur: float = 0.0
    monthly_storage_eur: float = 0.0
    resale_fee_pct: float = 0.0
    note: str = ""

@dataclass(frozen=True)
class VendorCost:
    shop: str
    displayed_price: float | None
    purchase_fee_eur: float | None
    entry_cost: float | None
    storage_cost: float | None
    cost_after_horizon: float | None
    exit_fee_pct: float
    note: str

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
    try:
        paxg = binance_price("PAXGUSDT")
    except Exception as exc:
        errors.append(f"Binance PAXGUSDT : {exc}")
    try:
        eurusd = binance_price("EURUSDT")
    except Exception as exc:
        errors.append(f"Binance EURUSDT : {exc}")
    spot_eur_oz = paxg / eurusd if paxg is not None and eurusd else None
    spot_eur_g = spot_eur_oz / TROY_OUNCE_GRAMS if spot_eur_oz is not None else None
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
    try:
        aucoffre = parse_aucoffre(get_text(AUCOFFRE_URL))
    except Exception as exc:
        errors.append(f"AuCOFFRE : {exc}")
        aucoffre = AuCoffreQuote(None, None, None, None, None, None)
    if goldfr.once_eur is None and market.spot_eur_oz is not None:
        goldfr = GoldFrQuote(goldfr.achat, goldfr.prime, round(market.spot_eur_oz, 2))
    theoretical = round(market.spot_eur_g * FINE_GOLD_20F_GRAMS, 2) if market.spot_eur_g is not None else None
    return MarketSnapshot(datetime.now(timezone.utc), market, godot, goldfr, aucoffre, theoretical, tuple(errors))


def compute_vendor_costs(
    snapshot: MarketSnapshot,
    horizon_months: int,
    aucoffre_apply_minimum_invoice: bool,
    aucoffre_lsp_free_storage: bool,
    goldfr_phone_email_commission: bool,
    godot_extra_pct: float = 0.0,
    goldfr_extra_pct: float = 0.0,
) -> list[VendorCost]:
    profiles = {
        "Godot": FeeProfile(
            purchase_fee_pct=max(godot_extra_pct, 0.0),
            note="Prix web retenu. Aucun frais d'achat séparé identifié publiquement; surcharge manuelle réglable.",
        ),
        "Gold.fr": FeeProfile(
            purchase_fee_pct=(3.3 if goldfr_phone_email_commission else 0.0) + max(goldfr_extra_pct, 0.0),
            purchase_fee_min_eur=10.0 if goldfr_phone_email_commission else 0.0,
            note="Commission téléphone/e-mail activée: 3,3 % sous 5 000 €, minimum 10 €. Désactivable si le prix final du panier l'intègre déjà.",
        ),
        "AuCOFFRE": FeeProfile(
            purchase_fee_pct=0.5,
            monthly_storage_eur=0.0 if aucoffre_lsp_free_storage else 5.0,
            resale_fee_pct=3.0,
            note="0,5 % à l'achat; garde 5 €/mois par tranche de 100 g. Le minimum de facturation officiel de 30 € est modélisé en option.",
        ),
    }
    displayed = {
        "Godot": snapshot.godot.achat,
        "Gold.fr": snapshot.goldfr.achat,
        "AuCOFFRE": snapshot.aucoffre.achat,
    }
    result: list[VendorCost] = []
    for shop, price in displayed.items():
        profile = profiles[shop]
        if price is None:
            result.append(VendorCost(shop, None, None, None, None, None, profile.resale_fee_pct, profile.note))
            continue
        pct_fee = price * profile.purchase_fee_pct / 100
        purchase_fee = max(pct_fee, profile.purchase_fee_min_eur) if profile.purchase_fee_pct > 0 else 0.0
        entry = price + purchase_fee
        storage = profile.monthly_storage_eur * max(horizon_months, 0)
        if shop == "AuCOFFRE" and storage > 0 and aucoffre_apply_minimum_invoice:
            # Le tarif public indique un minimum de facturation de 30 €. L'app applique
            # prudemment ce plancher à la période simulée, pas à chaque mois.
            storage = max(storage, 30.0)
        total = entry + storage
        result.append(VendorCost(
            shop=shop,
            displayed_price=round(price, 2),
            purchase_fee_eur=round(purchase_fee, 2),
            entry_cost=round(entry, 2),
            storage_cost=round(storage, 2),
            cost_after_horizon=round(total, 2),
            exit_fee_pct=profile.resale_fee_pct,
            note=profile.note,
        ))
    return result
