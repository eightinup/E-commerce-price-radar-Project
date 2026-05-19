from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import RAW_DATA_DIR, settings


class BaseScraper(ABC):
    """Base class for Playwright-powered scrapers with local fallback support."""

    competitor_name: str = "Unknown"
    website_url: str = "https://example.com"

    def __init__(
        self,
        start_url: str | None = None,
        user_agent: str = settings.scraper_user_agent,
        timeout_ms: int = settings.scraper_timeout_ms,
        max_retries: int = settings.scraper_retries,
        sample_html_path: Path | None = None,
    ) -> None:
        self.start_url = start_url or self.website_url
        self.user_agent = user_agent
        self.timeout_ms = timeout_ms
        self.max_retries = max(1, max_retries)
        self.sample_html_path = sample_html_path
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_page(self) -> str:
        """Fetch a rendered page with Playwright, falling back to demo HTML."""

        if self.start_url.startswith("sample://"):
            return self._read_sample_html()

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    context = browser.new_context(user_agent=self.user_agent)
                    page = context.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    page.goto(self.start_url, wait_until="networkidle")
                    html = page.content()
                    browser.close()
                    return html
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "Fetch attempt %s/%s failed for %s: %s",
                    attempt,
                    self.max_retries,
                    self.start_url,
                    exc,
                )
                time.sleep(min(attempt * 2, 10))

        self.logger.warning("Using sample HTML fallback for %s after fetch failure: %s", self.competitor_name, last_error)
        return self._read_sample_html()

    def _read_sample_html(self) -> str:
        if not self.sample_html_path or not self.sample_html_path.exists():
            raise FileNotFoundError(f"Sample HTML not found for {self.competitor_name}: {self.sample_html_path}")
        return self.sample_html_path.read_text(encoding="utf-8")

    def save_raw_html(self, html: str) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = self.competitor_name.lower().replace(" ", "_")
        output_path = RAW_DATA_DIR / f"{safe_name}_{timestamp}.html"
        output_path.write_text(html, encoding="utf-8")
        self.logger.info("Saved raw HTML to %s", output_path)
        return output_path

    @abstractmethod
    def parse_products(self, html: str) -> list[dict[str, Any]]:
        """Parse product cards from HTML into raw product records."""

    def scrape(self) -> list[dict[str, Any]]:
        started = datetime.utcnow()
        self.logger.info("Starting scrape for %s", self.competitor_name)
        html = self.fetch_page()
        self.save_raw_html(html)
        products = self.parse_products(html)
        for product in products:
            product.setdefault("competitor_name", self.competitor_name)
            product.setdefault("scraped_at", started)
        self.logger.info("Finished scrape for %s: %s products", self.competitor_name, len(products))
        return products
