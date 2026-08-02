from __future__ import annotations
import html
import re
from dataclasses import dataclass


def clean_number(value: str | None) -> float | None:
    if value is None:
        return None
    value = html.unescape(str(value)).replace("\u202f", " ").replace("\xa0", " ")
    value = re.sub(r"[^\d,.\-+\s]", "", value)
    value = value.replace(" ", "").replace(",", ".")
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
class GodotQuote:
    achat: float | None
    vente: float | None
    cotation: float | None
    intrinseque: float | None
    prime: float | None
    spread: float | None


@dataclass(frozen=True)
class GoldFrQuote:
    achat: float | None
    prime: float | None
    once_eur: float | None


@dataclass(frozen=True)
class AuCoffreQuote:
    achat: float | None
    prime: float | None
    product_name: str | None
    livrable: str | None
    fiscalite: str | None
    coffre: str | None
    etat: str | None = None
    is_lsp: bool = False


def parse_godot(raw: str) -> GodotQuote:
    text = text_only(raw)
    achat = first_match([
        r'name=["\']pxAU["\'][^>]*value=["\']([0-9]+[,.][0-9]+)["\']',
        r'id=["\']pxAU["\'][^>]*value=["\']([0-9]+[,.][0-9]+)["\']',
        r'id=["\']pa9["\'][^>]*>\s*([0-9]+[,.][0-9]+)',
        r'"price"\s*:\s*"([0-9]+[,.][0-9]+)"',
    ], raw)
    cotation = first_match([
        r"Cours\s+et\s+cotation.*?temps\s+réel\s*:\s*([0-9\s]+[,.][0-9]+)\s*€",
        r"Cours\s+et\s+cotation.*?:\s*([0-9\s]+[,.][0-9]+)\s*€",
    ], text)
    intrinseque = first_match([r"Valeur\s+intrinsèque\s*\??\s*:\s*([0-9\s]+[,.][0-9]+)\s*€"], text)
    prime = first_match([r"Prime\s*\??\s*:\s*([+-]?\s*[0-9\s]+[,.][0-9]+)\s*%"], text)
    spread = round(achat - cotation, 2) if achat is not None and cotation is not None else None
    return GodotQuote(achat, cotation, cotation, intrinseque, prime, spread)


def parse_goldfr(raw: str) -> GoldFrQuote:
    text = text_only(raw)
    achat = first_match([
        r"Cours\s+boursable\s+du\s+Napoléon\s+20\s+Frs.*?([0-9\s]+[,.][0-9]+)\s*€",
        r"Napoléon\s+20\s+Frs.*?([0-9\s]+[,.][0-9]+)\s*€",
    ], text)
    prime = first_match([
        r"Cours\s+boursable\s+du\s+Napoléon\s+20\s+Frs.*?([+-]\s*[0-9\s]+[,.][0-9]+)\s*%",
        r"Napoléon\s+20\s+Frs.*?([+-]\s*[0-9\s]+[,.][0-9]+)\s*%",
    ], text)
    once_eur = first_match([
        r"Once\s+d['’]\s*or\s*([0-9\s]+[,.][0-9]+)\s*€",
        r"Once\s+d['’]\s*Or\s*([0-9\s]+[,.][0-9]+)\s*€",
    ], text)
    return GoldFrQuote(achat, prime, once_eur)


def parse_aucoffre_offers(raw: str) -> tuple[AuCoffreQuote, ...]:
    """Extrait les offres Napoléon 20F visibles et les classe sans mélanger jetons/collector."""
    text = text_only(raw)
    blocks = re.split(r"(?=Napoléon\s+20F(?:\s|$))", text, flags=re.I)
    candidates: list[AuCoffreQuote] = []
    for block in blocks[1:]:
        sample = block[:1700]
        if re.search(r"\b(Jeton|Collector|Proof)\b", sample[:220], flags=re.I):
            continue
        price = first_match([r"([0-9][0-9\s\u202f]*[,.][0-9]{2})\s*€"], sample)
        if price is None:
            continue
        prime = first_match([r"prime\s*:\s*([+-]?[0-9\s]+(?:[,.][0-9]+)?)\s*%"], sample)
        name_match = re.match(r"(Napoléon\s+20F(?:\s+[^€]{0,150})?)", sample, flags=re.I)
        name = re.sub(r"\s+", " ", name_match.group(1)).strip() if name_match else "Napoléon 20F"
        liv_match = re.search(r"Livrable\s*:\s*(Oui|Non)", sample, flags=re.I)
        fisc_match = re.search(r"Fiscalité\s*:\s*([^€]+?)(?:Plus de détails|[0-9][0-9\s]*[,.][0-9]{2}\s*€)", sample, flags=re.I)
        coffre_match = re.search(r"Coffre\s*:\s*(France|Suisse|Belgique)", sample, flags=re.I)
        etat_match = re.search(r"État\s*:\s*([A-Z]{2,5})", sample, flags=re.I)
        is_lsp = bool(re.search(r"\bLSP\b", sample[:300], flags=re.I))
        candidates.append(AuCoffreQuote(
            achat=price,
            prime=prime,
            product_name=name[:150],
            livrable=liv_match.group(1).capitalize() if liv_match else None,
            fiscalite=re.sub(r"\s+", " ", fisc_match.group(1)).strip() if fisc_match else None,
            coffre=coffre_match.group(1).capitalize() if coffre_match else None,
            etat=etat_match.group(1).upper() if etat_match else None,
            is_lsp=is_lsp,
        ))
    if not candidates:
        raise ValueError("aucune offre Napoléon 20F détectée")
    unique: dict[tuple, AuCoffreQuote] = {}
    for q in candidates:
        key = (q.achat, q.product_name, q.livrable, q.coffre)
        unique[key] = q
    return tuple(sorted(unique.values(), key=lambda q: q.achat or float("inf")))


def parse_aucoffre(raw: str) -> AuCoffreQuote:
    offers = parse_aucoffre_offers(raw)

    def rank(q: AuCoffreQuote) -> tuple[int, int, int, float]:
        livrable_rank = 0 if (q.livrable or "").lower() == "oui" else 1
        france_rank = 0 if (q.coffre or "").lower() == "france" else 1
        standard_rank = 0 if not q.is_lsp else 1
        return livrable_rank, france_rank, standard_rank, q.achat or float("inf")

    return min(offers, key=rank)
