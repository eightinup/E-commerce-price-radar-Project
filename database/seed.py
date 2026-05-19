from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete

from database.db import get_session, init_db
from database.models import Alert, Competitor, PriceSnapshot, Product, ProductMatch, ScrapeRun
from database.repositories import (
    CompetitorRepository,
    PriceSnapshotRepository,
    ProductRepository,
)
from pipelines.clean_products import calculate_discount, clean_product_record
from pipelines.detect_changes import create_alerts_for_snapshot
from pipelines.match_products import create_product_matches


logger = logging.getLogger(__name__)


CATALOG: list[dict[str, Any]] = [
    {
        "category": "Smartphones",
        "brand": "Apple",
        "image_url": "https://images.unsplash.com/photo-1695048133142-1a20484d2569",
        "variants": {
            "Demo Store": ("Apple iPhone 15 Pro 256GB Natural Titanium", 1099.00),
            "MarketHub": ("Apple iPhone 15 Pro 256 GB Titanium", 1149.00),
            "ShopZone": ("iPhone 15 Pro 256Gb Natural Titanium", 1049.00),
        },
    },
    {
        "category": "Smartphones",
        "brand": "Samsung",
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf",
        "variants": {
            "Demo Store": ("Samsung Galaxy S24 Ultra 256GB Titanium Black", 1199.00),
            "MarketHub": ("Galaxy S24 Ultra 256 GB Titanium Black", 1169.00),
            "ShopZone": ("Samsung S24 Ultra 256GB Black", 1249.00),
        },
    },
    {
        "category": "Audio",
        "brand": "Sony",
        "image_url": "https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb",
        "variants": {
            "Demo Store": ("Sony WH-1000XM5 Wireless Noise Cancelling Headphones", 349.00),
            "MarketHub": ("Sony WH1000XM5 Noise Canceling Headphones", 329.00),
            "ShopZone": ("Sony WH-1000XM5 Wireless Headphones Black", 379.00),
        },
    },
    {
        "category": "Laptops",
        "brand": "Dell",
        "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853",
        "variants": {
            "Demo Store": ("Dell XPS 13 Plus 13.4 inch Laptop 16GB 512GB", 1299.00),
            "MarketHub": ("Dell XPS 13 Plus Laptop 16 GB RAM 512 GB SSD", 1349.00),
            "ShopZone": ("Dell XPS 13 Plus 512GB 16GB Laptop", 1219.00),
        },
    },
    {
        "category": "Wearables",
        "brand": "Garmin",
        "image_url": "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1",
        "variants": {
            "Demo Store": ("Garmin Forerunner 965 AMOLED GPS Watch", 599.00),
            "MarketHub": ("Garmin Forerunner 965 GPS Running Watch", 579.00),
            "ShopZone": ("Forerunner 965 Garmin AMOLED Watch", 619.00),
        },
    },
    {
        "category": "Gaming",
        "brand": "Nintendo",
        "image_url": "https://images.unsplash.com/photo-1578303512597-81e6cc155b3e",
        "variants": {
            "Demo Store": ("Nintendo Switch OLED Model White Joy-Con", 349.00),
            "MarketHub": ("Nintendo Switch OLED Console White Joy Con", 339.00),
            "ShopZone": ("Switch OLED White Joy-Con Console", 359.00),
        },
    },
]


COMPETITORS = {
    "Demo Store": "https://demo-store.local/products",
    "MarketHub": "https://markethub.local/search",
    "ShopZone": "https://shopzone.local/catalog",
}


SAMPLE_PRODUCT_URLS = {
    ("Demo Store", "Apple iPhone 15 Pro 256GB Natural Titanium"): "https://demo-store.local/products/apple-iphone-15-pro-256gb",
    ("Demo Store", "Samsung Galaxy S24 Ultra 256GB Titanium Black"): "https://demo-store.local/products/samsung-galaxy-s24-ultra",
    ("Demo Store", "Sony WH-1000XM5 Wireless Noise Cancelling Headphones"): "https://demo-store.local/products/sony-wh1000xm5",
    ("Demo Store", "Dell XPS 13 Plus 13.4 inch Laptop 16GB 512GB"): "https://demo-store.local/products/dell-xps-13-plus",
    ("Demo Store", "Garmin Forerunner 965 AMOLED GPS Watch"): "https://demo-store.local/products/garmin-forerunner-965",
    ("MarketHub", "Apple iPhone 15 Pro 256 GB Titanium"): "https://markethub.local/p/apple-iphone-15-pro-256gb",
    ("MarketHub", "Galaxy S24 Ultra 256 GB Titanium Black"): "https://markethub.local/p/galaxy-s24-ultra-256gb",
    ("MarketHub", "Sony WH1000XM5 Noise Canceling Headphones"): "https://markethub.local/p/sony-wh1000xm5",
    ("MarketHub", "Dell XPS 13 Plus Laptop 16 GB RAM 512 GB SSD"): "https://markethub.local/p/dell-xps-13-plus",
    ("MarketHub", "Nintendo Switch OLED Console White Joy Con"): "https://markethub.local/p/nintendo-switch-oled",
    ("ShopZone", "iPhone 15 Pro 256Gb Natural Titanium"): "https://shopzone.local/item/iphone-15-pro-256gb",
    ("ShopZone", "Samsung S24 Ultra 256GB Black"): "https://shopzone.local/item/samsung-s24-ultra",
    ("ShopZone", "Sony WH-1000XM5 Wireless Headphones Black"): "https://shopzone.local/item/sony-wh1000xm5-black",
    ("ShopZone", "Dell XPS 13 Plus 512GB 16GB Laptop"): "https://shopzone.local/item/dell-xps-13-plus-512gb",
    ("ShopZone", "Forerunner 965 Garmin AMOLED Watch"): "https://shopzone.local/item/garmin-forerunner-965",
}


PRICE_CURVES = {
    "Demo Store": [0.00, 0.01, 0.00, -0.02, -0.03, -0.02, 0.00, 0.02],
    "MarketHub": [0.02, 0.02, -0.01, -0.06, -0.09, -0.04, 0.03, 0.05],
    "ShopZone": [-0.01, 0.00, 0.03, 0.01, -0.02, -0.08, -0.11, -0.07],
}


def _clear_demo_data() -> None:
    with get_session() as session:
        for model in (ProductMatch, Alert, PriceSnapshot, ScrapeRun, Product, Competitor):
            session.execute(delete(model))


def _availability_for(product_name: str, competitor_name: str, index: int) -> str:
    if "Sony" in product_name and competitor_name == "MarketHub" and index in {5, 6}:
        return "out_of_stock"
    if "Garmin" in product_name and competitor_name == "ShopZone" and index >= 6:
        return "out_of_stock"
    if "Nintendo" in product_name and competitor_name == "Demo Store" and index == 3:
        return "limited_stock"
    return "in_stock"


def _review_count(base: int, index: int) -> int:
    return base + (index * 7)


def seed_sample_data(reset: bool = True) -> dict[str, int]:
    """Create deterministic demo data with realistic history and alerts."""

    init_db()
    if reset:
        _clear_demo_data()

    start_date = datetime.utcnow() - timedelta(days=28)
    snapshot_dates = [start_date + timedelta(days=4 * index) for index in range(8)]
    products_created = 0
    snapshots_created = 0
    alerts_created = 0

    with get_session() as session:
        competitors = {
            name: CompetitorRepository.get_or_create(session, name=name, website_url=url)
            for name, url in COMPETITORS.items()
        }

        for catalog_index, item in enumerate(CATALOG):
            for competitor_name, (product_name, base_price) in item["variants"].items():
                competitor = competitors[competitor_name]
                slug = product_name.lower().replace(" ", "-").replace("/", "-")
                product_url = SAMPLE_PRODUCT_URLS.get(
                    (competitor_name, product_name),
                    f"{COMPETITORS[competitor_name]}/{slug}",
                )
                product_record = clean_product_record(
                    {
                        "product_name": product_name,
                        "brand": item["brand"],
                        "category": item["category"],
                        "product_url": product_url,
                        "image_url": item["image_url"],
                        "seller_name": competitor_name if competitor_name == "Demo Store" else f"{competitor_name} Direct",
                        "current_price": base_price,
                        "old_price": None,
                        "discount_percent": None,
                        "availability": "in_stock",
                        "rating": round(4.2 + (catalog_index % 4) * 0.15, 2),
                        "review_count": 80 + catalog_index * 43,
                    }
                )
                product = ProductRepository.upsert_product(session, competitor, product_record)
                products_created += 1

                previous_snapshot = None
                for index, scraped_at in enumerate(snapshot_dates):
                    curve = PRICE_CURVES[competitor_name][index]
                    product_adjustment = ((catalog_index % 3) - 1) * 0.012
                    price = round(base_price * (1 + curve + product_adjustment), 2)
                    old_price = round(base_price * 1.06, 2) if curve <= -0.06 else None
                    availability = _availability_for(product_name, competitor_name, index)
                    snapshot_record = dict(product_record)
                    snapshot_record.update(
                        {
                            "current_price": price,
                            "old_price": old_price,
                            "discount_percent": calculate_discount(price, old_price),
                            "availability": availability,
                            "rating": product_record["rating"],
                            "review_count": _review_count(int(product_record["review_count"] or 0), index),
                            "scraped_at": scraped_at,
                        }
                    )
                    snapshot = PriceSnapshotRepository.add_snapshot(session, product.id, snapshot_record)
                    snapshots_created += 1
                    alerts_created += create_alerts_for_snapshot(session, product, snapshot, previous_snapshot)
                    previous_snapshot = snapshot

        matches_created = create_product_matches(session)

    logger.info(
        "Seeded demo data: %s products, %s snapshots, %s alerts, %s matches",
        products_created,
        snapshots_created,
        alerts_created,
        matches_created,
    )
    return {
        "products": products_created,
        "snapshots": snapshots_created,
        "alerts": alerts_created,
        "matches": matches_created,
    }
