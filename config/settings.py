from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
LOGS_DIR = PROJECT_ROOT / "logs"


for directory in (DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, EXPORTS_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    database_url: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    scraper_user_agent: str
    scraper_timeout_ms: int
    scraper_retries: int
    own_competitor_name: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        sqlite_path = DATA_DIR / "price_radar.db"
        return cls(
            database_url=os.getenv("DATABASE_URL", f"sqlite:///{sqlite_path.as_posix()}"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
            scraper_user_agent=os.getenv(
                "SCRAPER_USER_AGENT",
                "PriceRadarBot/1.0 (+https://example.com/price-radar-portfolio)",
            ),
            scraper_timeout_ms=int(os.getenv("SCRAPER_TIMEOUT_MS", "30000")),
            scraper_retries=int(os.getenv("SCRAPER_RETRIES", "3")),
            own_competitor_name=os.getenv("OWN_COMPETITOR_NAME", "Demo Store"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


settings = Settings.from_env()


def setup_logging() -> None:
    """Configure file and console logging once for the application."""

    log_file = LOGS_DIR / "app.log"
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
