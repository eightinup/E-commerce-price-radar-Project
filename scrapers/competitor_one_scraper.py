from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from config.settings import RAW_DATA_DIR
from scrapers.base_scraper import BaseScraper


class CompetitorOneScraper(BaseScraper):
    competitor_name = "MarketHub"
    website_url = "sample://markethub"

    def __init__(self) -> None:
        super().__init__(start_url=self.website_url, sample_html_path=RAW_DATA_DIR / "competitor_one.html")

    def parse_products(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        products: list[dict[str, Any]] = []
        for item in soup.select("article.catalog-item"):
            meta = item.select_one(".meta")
            products.append(
                {
                    "product_name": item.select_one("h2").get_text(strip=True),
                    "brand": item.get("data-maker"),
                    "category": meta.get("data-category") if meta else None,
                    "current_price": item.select_one("[data-price]").get("data-price"),
                    "old_price": item.select_one("[data-old-price]").get("data-old-price")
                    if item.select_one("[data-old-price]")
                    else None,
                    "discount_percent": item.select_one(".badge").get_text(strip=True).replace("% off", "")
                    if item.select_one(".badge")
                    else None,
                    "availability": item.select_one(".stock").get_text(strip=True),
                    "rating": item.select_one(".score").get_text(strip=True),
                    "review_count": item.select_one(".review-count").get_text(strip=True),
                    "seller_name": "MarketHub Direct",
                    "product_url": item.select_one("a.buy-link")["href"],
                    "image_url": item.select_one("img")["src"],
                }
            )
        return products
