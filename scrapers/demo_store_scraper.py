from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from config.settings import RAW_DATA_DIR
from scrapers.base_scraper import BaseScraper


class DemoStoreScraper(BaseScraper):
    competitor_name = "Demo Store"
    website_url = "sample://demo-store"

    def __init__(self) -> None:
        super().__init__(start_url=self.website_url, sample_html_path=RAW_DATA_DIR / "demo_store.html")

    def parse_products(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        products: list[dict[str, Any]] = []
        for card in soup.select(".product-card"):
            products.append(
                {
                    "product_name": card.select_one(".product-title").get_text(strip=True),
                    "brand": card.get("data-brand"),
                    "category": card.get("data-category"),
                    "current_price": card.select_one(".price-current").get_text(strip=True),
                    "old_price": card.select_one(".price-old").get_text(strip=True) if card.select_one(".price-old") else None,
                    "discount_percent": None,
                    "availability": card.select_one(".availability").get_text(strip=True),
                    "rating": card.select_one(".rating").get_text(strip=True),
                    "review_count": card.select_one(".reviews").get_text(strip=True),
                    "seller_name": "Demo Store",
                    "product_url": card.select_one("a.details")["href"],
                    "image_url": card.select_one("img")["src"],
                }
            )
        return products
