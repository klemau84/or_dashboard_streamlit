"""Transparent manual what-if comparison. No simulated quote is represented as live."""
from dataclasses import dataclass
from math import ceil

@dataclass(frozen=True)
class Result:
    name: str
    purchase: float
    custody: float
    delivery: float
    total_delivered: float
    resale_proceeds: float | None
    break_even_pct: float | None


def estimate(name: str, unit_price: float, quantity: int, months: int,
             buy_fee_pct: float, custody_monthly: float, delivery_fee: float,
             resale_unit: float | None = None, resale_fee_pct: float = 0.0) -> Result:
    purchase = unit_price * quantity * (1 + buy_fee_pct / 100)
    custody = months * custody_monthly
    total = purchase + custody + delivery_fee
    proceeds = resale_unit * quantity * (1 - resale_fee_pct / 100) if resale_unit is not None else None
    breakeven = ((purchase + custody) / (unit_price * quantity * (1 - resale_fee_pct / 100)) - 1) * 100 if unit_price > 0 else None
    return Result(name, purchase, custody, delivery_fee, total, proceeds, breakeven)
