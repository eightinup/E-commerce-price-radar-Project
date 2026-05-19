from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from config.settings import RAW_DATA_DIR
from scrapers.base_scraper import BaseScraper


class CompetitorTwoScraper(BaseScraper):
    competitor_name = "ShopZone"
    website_url = "sample://shopzone"

    def __init__(self) -> None:
        super().__init__(start_url=self.website_url, sample_html_path=RAW_DATA_DIR / "competitor_two.html")

    def parse_products(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        products: list[dict[str, Any]] = []
        for tile in soup.select("li.offer-tile"):
            products.append(
                {
                    "product_name": tile.select_one(".name").get_text(" ", strip=True),
                    "brand": tile.select_one(".brand").get_text(strip=True),
                    "category": tile.select_one(".category").get_text(strip=True),
                    "current_price": tile.select_one(".money").get_text(strip=True),
                    "old_price": tile.select_one(".was").get_text(strip=True) if tile.select_one(".was") else None,
                    "discount_percent": None,
                    "availability": tile.select_one(".fulfillment").get_text(strip=True),
                    "rating": tile.select_one(".stars")["data-rating"],
                    "review_count": tile.select_one(".reviews").get_text(strip=True),
                    "seller_name": tile.select_one(".seller").get_text(strip=True),
                    "product_url": tile.select_one("a")["href"],
                    "image_url": tile.select_one("img")["src"],
                }
            )
        return products
