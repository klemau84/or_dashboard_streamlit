from __future__ import annotations
import html
import re
from dataclasses import dataclass


def clean_number(value: str | None) -> float | None:
    if value is None:
        return None
    value = html.unescape(str(value)).replace("\u202f", " ").replace("\xa0", " ")
    value = re.sub(r"[^\d,.\-+\s]", "", value).replace(" ", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def text_only(raw: str) -> str:
    text = html.unescape(raw)
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def first_match(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return clean_number(match.group(1))
    return None


@dataclass(frozen=True)
class VendorQuote:
    price: float | None
    premium: float | None
    label: str
    source_url: str
    note: str = ""


@dataclass(frozen=True)
class AuCoffreOffer:
    product_name: str
    price: float
    premium: float | None
    livrable: str | None
    fiscalite: str | None
    coffre: str | None
    etat: str | None
    is_lsp: bool


def parse_godot_napoleon(raw: str, source_url: str) -> VendorQuote:
    text = text_only(raw)
    price = first_match([
        r'name=["\']pxAU["\'][^>]*value=["\']([0-9]+[,.][0-9]+)["\']',
        r'id=["\']pxAU["\'][^>]*value=["\']([0-9]+[,.][0-9]+)["\']',
        r'id=["\']pa9["\'][^>]*>\s*([0-9]+[,.][0-9]+)',
        r'"price"\s*:\s*"([0-9]+[,.][0-9]+)"',
    ], raw)
    premium = first_match([r"Prime\s*\??\s*:\s*([+-]?\s*[0-9\s]+[,.][0-9]+)\s*%"], text)
    return VendorQuote(price, premium, "Godot & Fils", source_url, "Prix web détecté")


def parse_goldfr_napoleon(raw: str, source_url: str) -> VendorQuote:
    text = text_only(raw)
    price = first_match([
        r"Cours\s+boursable\s+du\s+Napoléon\s+20\s+Frs.*?([0-9\s]+[,.][0-9]+)\s*€",
        r"Napoléon\s+20\s+Frs.*?([0-9\s]+[,.][0-9]+)\s*€",
    ], text)
    premium = first_match([
        r"Cours\s+boursable\s+du\s+Napoléon\s+20\s+Frs.*?([+-]?\s*[0-9\s]+[,.][0-9]+)\s*%",
        r"Napoléon\s+20\s+Frs.*?([+-]?\s*[0-9\s]+[,.][0-9]+)\s*%",
    ], text)
    return VendorQuote(price, premium, "Gold.fr / Comptoir", source_url, "Cours public détecté, pas forcément panier ferme")


def parse_aucoffre_catalog(raw: str, aliases: tuple[str, ...]) -> tuple[AuCoffreOffer, ...]:
    text = text_only(raw)
    escaped = "|".join(re.escape(a) for a in aliases)
    starts = list(re.finditer(rf"(?i)(?={escaped})", text))
    candidates: list[AuCoffreOffer] = []
    for idx, match in enumerate(starts):
        end = starts[idx + 1].start() if idx + 1 < len(starts) else min(len(text), match.start() + 1800)
        sample = text[match.start(): min(end, match.start() + 1800)]
        price = first_match([r"([0-9][0-9\s\u202f]*[,.][0-9]{2})\s*€"], sample)
        if price is None:
            continue
        premium = first_match([r"prime\s*:\s*([+-]?[0-9\s]+(?:[,.][0-9]+)?)\s*%"], sample)
        name_match = re.match(r"(.{3,180}?)(?=\s+Coffre\s*:|\s+Livrable\s*:|\s+[0-9][0-9\s]*[,.][0-9]{2}\s*€)", sample, flags=re.I)
        name = re.sub(r"\s+", " ", name_match.group(1)).strip() if name_match else aliases[0]
        liv = re.search(r"Livrable\s*:\s*(Oui|Non)", sample, flags=re.I)
        fisc = re.search(r"Fiscalité\s*:\s*([^€]+?)(?:Plus de détails|[0-9][0-9\s]*[,.][0-9]{2}\s*€)", sample, flags=re.I)
        coffre = re.search(r"Coffre\s*:\s*(France|Suisse|Belgique|Gibraltar)", sample, flags=re.I)
        etat = re.search(r"État\s*:\s*([A-Z]{2,5})", sample, flags=re.I)
        is_lsp = bool(re.search(r"\bLSP\b", sample[:350], flags=re.I))
        candidates.append(AuCoffreOffer(
            product_name=name[:180], price=price, premium=premium,
            livrable=liv.group(1).capitalize() if liv else None,
            fiscalite=re.sub(r"\s+", " ", fisc.group(1)).strip() if fisc else None,
            coffre=coffre.group(1).capitalize() if coffre else None,
            etat=etat.group(1).upper() if etat else None,
            is_lsp=is_lsp,
        ))
    unique: dict[tuple, AuCoffreOffer] = {}
    for offer in candidates:
        unique[(offer.product_name, offer.price, offer.livrable, offer.is_lsp)] = offer
    return tuple(sorted(unique.values(), key=lambda x: x.price))
