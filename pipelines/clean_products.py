from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable


KNOWN_BRANDS = (
    "Apple",
    "Samsung",
    "Sony",
    "Dell",
    "HP",
    "Lenovo",
    "Asus",
    "Acer",
    "Garmin",
    "Bose",
    "Microsoft",
    "Google",
    "Xiaomi",
    "OnePlus",
    "Nintendo",
    "Logitech",
)


def clean_price(value: Any) -> float | None:
    """Convert messy e-commerce price strings to floats."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)

    text = str(value).strip()
    if not text or text.lower() in {"n/a", "na", "none", "-", "out of stock"}:
        return None

    text = (
        text.replace("\xa0", " ")
        .replace("USD", "")
        .replace("usd", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .strip()
    )
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        comma_parts = text.split(",")
        if len(comma_parts[-1]) == 2:
            text = "".join(comma_parts[:-1]) + "." + comma_parts[-1]
        else:
            text = text.replace(",", "")
    elif text.count(".") > 1:
        dot_parts = text.split(".")
        text = "".join(dot_parts[:-1]) + "." + dot_parts[-1]

    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None

    if amount < 0:
        return None
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def clean_product_name(name: str | None) -> str:
    if not name:
        return ""
    text = re.sub(r"\s+", " ", str(name).replace("\n", " ").replace("\t", " "))
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip(" -|")


def normalize_product_name(name: str | None) -> str:
    """Normalize names for matching while preserving useful model tokens."""

    text = clean_product_name(name).lower()
    text = text.replace("&", " and ")
    text = text.replace("cancelling", "canceling")
    text = re.sub(r"\b([a-z]{1,4})[-\s]+(\d+[a-z][a-z0-9]*)\b", r"\1\2", text)
    text = re.sub(r"(\d+)\s*(gb|tb|mb|inch|inches|hz|w|mah)\b", r"\1\2", text)
    text = re.sub(r"\bgb\b", "gb", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stopwords = {
        "new",
        "sale",
        "deal",
        "official",
        "original",
        "with",
        "for",
        "the",
        "edition",
        "smartphone",
    }
    tokens = [token for token in text.split() if token and token not in stopwords]
    return " ".join(tokens)


def extract_brand(product_name: str | None, explicit_brand: str | None = None) -> str | None:
    if explicit_brand:
        cleaned = clean_product_name(explicit_brand)
        return cleaned.title() if cleaned else None

    normalized = normalize_product_name(product_name)
    normalized_tokens = set(normalized.split())
    for brand in KNOWN_BRANDS:
        brand_tokens = normalize_product_name(brand).split()
        if all(token in normalized_tokens for token in brand_tokens):
            return brand
    return None


def calculate_discount(current_price: float | None, old_price: float | None) -> float | None:
    if current_price is None or old_price is None or old_price <= 0:
        return None
    if current_price >= old_price:
        return 0.0
    discount = (old_price - current_price) / old_price * 100
    return round(discount, 2)


def clean_availability(value: str | None) -> str:
    if not value:
        return "unknown"
    text = str(value).strip().lower()
    if any(term in text for term in ("out of stock", "sold out", "unavailable", "not available")):
        return "out_of_stock"
    if any(term in text for term in ("backorder", "preorder", "pre-order")):
        return "preorder"
    if any(term in text for term in ("limited", "few left", "low stock")):
        return "limited_stock"
    if any(term in text for term in ("in stock", "available", "ships", "ready")):
        return "in_stock"
    return "unknown"


def clean_product_record(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(record)
    product_name = clean_product_name(cleaned.get("product_name"))
    current_price = clean_price(cleaned.get("current_price"))
    old_price = clean_price(cleaned.get("old_price"))

    cleaned["product_name"] = product_name
    cleaned["normalized_name"] = cleaned.get("normalized_name") or normalize_product_name(product_name)
    cleaned["brand"] = extract_brand(product_name, cleaned.get("brand"))
    cleaned["current_price"] = current_price
    cleaned["old_price"] = old_price
    cleaned["discount_percent"] = (
        clean_price(cleaned.get("discount_percent"))
        if cleaned.get("discount_percent") not in (None, "")
        else calculate_discount(current_price, old_price)
    )
    cleaned["availability"] = clean_availability(cleaned.get("availability"))

    rating = clean_price(cleaned.get("rating"))
    cleaned["rating"] = min(rating, 5.0) if rating is not None else None

    review_count = cleaned.get("review_count")
    if review_count in (None, ""):
        cleaned["review_count"] = None
    else:
        digits = re.sub(r"[^\d]", "", str(review_count))
        cleaned["review_count"] = int(digits) if digits else None

    return cleaned


def remove_duplicates(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique_records: list[dict[str, Any]] = []
    for record in records:
        key = (
            str(record.get("competitor_name", "")).lower(),
            str(record.get("product_url", "")).lower(),
            str(record.get("normalized_name", "")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_records.append(record)
    return unique_records
