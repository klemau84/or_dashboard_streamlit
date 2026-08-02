from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from services.http import get_json, get_text
from services.parsers import AuCoffreQuote, GodotQuote, GoldFrQuote, parse_aucoffre_offers, parse_godot, parse_goldfr

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
class VendorScenario:
    shop: str
    scenario: str
    displayed_price: float | None
    purchase_fee_eur: float | None
    entry_cost: float | None
    storage_cost: float | None
    cost_after_horizon: float | None
    exit_fee_pct: float
    estimated_resale_value: float | None
    immediate_loss: float | None
    break_even_rise_pct: float | None
    effective_premium_pct: float | None
    score: int | None
    note: str


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: datetime
    market: MarketData
    godot: GodotQuote
    goldfr: GoldFrQuote
    aucoffre_offers: tuple[AuCoffreQuote, ...]
    theoretical_20f_eur: float | None
    errors: tuple[str, ...]


def binance_price(symbol: str) -> float:
    failures: list[str] = []
    for base in BINANCE_BASES:
        try:
            payload = get_json(f"{base}/api/v3/ticker/price?symbol={symbol}")
            return float(payload["price"])
        except Exception as exc:
            failures.append(str(exc))
    raise RuntimeError("; ".join(failures[-2:]))


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
        aucoffre_offers = parse_aucoffre_offers(get_text(AUCOFFRE_URL))
    except Exception as exc:
        errors.append(f"AuCOFFRE : {exc}")
        aucoffre_offers = tuple()
    if goldfr.once_eur is None and market.spot_eur_oz is not None:
        goldfr = GoldFrQuote(goldfr.achat, goldfr.prime, round(market.spot_eur_oz, 2))
    theoretical = round(market.spot_eur_g * FINE_GOLD_20F_GRAMS, 2) if market.spot_eur_g is not None else None
    return MarketSnapshot(datetime.now(timezone.utc), market, godot, goldfr, aucoffre_offers, theoretical, tuple(errors))


def _score(premium: float | None, break_even: float | None, storage: float, transparency_penalty: int) -> int | None:
    if premium is None or break_even is None:
        return None
    score = 100.0
    score -= max(premium, 0) * 3.0
    score -= max(break_even, 0) * 1.5
    score -= min(storage / 5.0, 25.0)
    score -= transparency_penalty
    return max(0, min(100, round(score)))


def _scenario(
    shop: str,
    scenario: str,
    price: float | None,
    theoretical: float | None,
    purchase_fee_pct: float,
    purchase_fee_min: float,
    storage_cost: float,
    exit_fee_pct: float,
    resale_discount_pct: float,
    transparency_penalty: int,
    note: str,
) -> VendorScenario:
    if price is None:
        return VendorScenario(shop, scenario, None, None, None, None, None, exit_fee_pct, None, None, None, None, None, note)
    pct_fee = price * max(purchase_fee_pct, 0) / 100
    purchase_fee = max(pct_fee, purchase_fee_min) if purchase_fee_pct > 0 else 0.0
    entry = price + purchase_fee
    total = entry + max(storage_cost, 0)
    market_basis = theoretical if theoretical is not None else price
    estimated_resale = market_basis * (1 - max(resale_discount_pct, 0) / 100) * (1 - max(exit_fee_pct, 0) / 100)
    loss = total - estimated_resale
    break_even = (total / estimated_resale - 1) * 100 if estimated_resale > 0 else None
    premium = (entry / theoretical - 1) * 100 if theoretical else None
    score = _score(premium, break_even, storage_cost, transparency_penalty)
    return VendorScenario(
        shop, scenario, round(price, 2), round(purchase_fee, 2), round(entry, 2), round(storage_cost, 2),
        round(total, 2), exit_fee_pct, round(estimated_resale, 2), round(loss, 2),
        round(break_even, 2) if break_even is not None else None,
        round(premium, 2) if premium is not None else None, score, note,
    )


def compute_scenarios(
    snapshot: MarketSnapshot,
    horizon_months: int,
    aucoffre_offer: AuCoffreQuote | None,
    goldfr_phone_email_commission: bool,
    godot_extra_pct: float,
    goldfr_extra_pct: float,
    godot_resale_discount_pct: float,
    goldfr_resale_discount_pct: float,
    aucoffre_resale_discount_pct: float,
) -> list[VendorScenario]:
    scenarios: list[VendorScenario] = []
    scenarios.append(_scenario(
        "Godot", "Prix web", snapshot.godot.achat, snapshot.theoretical_20f_eur,
        godot_extra_pct, 0, 0, 0, godot_resale_discount_pct, 3,
        "Prix web + éventuelle surcharge manuelle. Aucun coût de garde si la pièce est retirée.",
    ))
    gold_pct = max(goldfr_extra_pct, 0) + (3.3 if goldfr_phone_email_commission else 0)
    scenarios.append(_scenario(
        "Gold.fr", "Cours public" + (" + canal assisté" if goldfr_phone_email_commission else ""),
        snapshot.goldfr.achat, snapshot.theoretical_20f_eur, gold_pct,
        10 if goldfr_phone_email_commission else 0, 0, 0, goldfr_resale_discount_pct, 8,
        "Le cours public n'est pas garanti comme prix de panier. La commission 3,3 % n'est appliquée que si le canal téléphone/e-mail est activé.",
    ))
    if aucoffre_offer is not None:
        # Tarifs officiels : 0,5 % achat, 3 % vente, garde 5 €/mois/100g et minimum de facturation 30 €.
        # Pour une petite détention non-LSP, le plancher prudent est donc 30 € par mois facturé.
        standard_storage = 30.0 * max(horizon_months, 0)
        scenarios.append(_scenario(
            "AuCOFFRE", "Standard non-LSP", aucoffre_offer.achat, snapshot.theoretical_20f_eur,
            0.5, 0, standard_storage, 3.0, aucoffre_resale_discount_pct, 0,
            "0,5 % à l'achat, 3 % à la vente. Garde modélisée avec le minimum officiel de facturation de 30 € par facture mensuelle.",
        ))
        if aucoffre_offer.is_lsp:
            scenarios.append(_scenario(
                "AuCOFFRE", "LSP validé chaque mois", aucoffre_offer.achat, snapshot.theoretical_20f_eur,
                0.5, 0, 0, 3.0, aucoffre_resale_discount_pct, 0,
                "Garde nulle uniquement pour un produit LSP et uniquement si le programme mensuel est validé. Le coût des achats mensuels requis n'est pas ajouté.",
            ))
    return scenarios
