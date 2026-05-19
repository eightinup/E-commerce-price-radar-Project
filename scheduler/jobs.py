from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from alerts.telegram_alerts import send_unsent_alerts
from database.db import get_session, init_db
from database.repositories import (
    CompetitorRepository,
    PriceSnapshotRepository,
    ProductRepository,
    ScrapeRunRepository,
)
from pipelines.clean_products import clean_product_record, remove_duplicates
from pipelines.detect_changes import create_alerts_for_snapshot
from pipelines.match_products import create_product_matches
from reports.weekly_report import generate_weekly_report
from scrapers.competitor_one_scraper import CompetitorOneScraper
from scrapers.competitor_two_scraper import CompetitorTwoScraper
from scrapers.demo_store_scraper import DemoStoreScraper


logger = logging.getLogger(__name__)


SCRAPER_CLASSES = (DemoStoreScraper, CompetitorOneScraper, CompetitorTwoScraper)


def run_scraping_pipeline(send_alerts: bool = False) -> int:
    init_db()
    total_products = 0

    with get_session() as session:
        for scraper_class in SCRAPER_CLASSES:
            scraper = scraper_class()
            competitor = CompetitorRepository.get_or_create(
                session,
                name=scraper.competitor_name,
                website_url=scraper.website_url,
            )
            run = ScrapeRunRepository.start(session, competitor)

            try:
                raw_products = scraper.scrape()
                cleaned_products = remove_duplicates(clean_product_record(product) for product in raw_products)

                for product_data in cleaned_products:
                    product = ProductRepository.upsert_product(session, competitor, product_data)
                    previous_snapshot = PriceSnapshotRepository.latest_for_product(session, product.id)
                    current_snapshot = PriceSnapshotRepository.add_snapshot(session, product.id, product_data)
                    create_alerts_for_snapshot(session, product, current_snapshot, previous_snapshot)

                ScrapeRunRepository.finish(session, run, "success", products_found=len(cleaned_products))
                total_products += len(cleaned_products)
            except Exception as exc:
                logger.exception("Scrape failed for %s", scraper.competitor_name)
                ScrapeRunRepository.finish(session, run, "failed", products_found=0, error_message=str(exc))

        create_product_matches(session)
        if send_alerts:
            send_unsent_alerts(session)

    logger.info("Scraping pipeline completed with %s products", total_products)
    return total_products


def clean_data_job() -> None:
    init_db()
    with get_session() as session:
        create_product_matches(session)
    logger.info("Data cleaning and matching job completed")


def detect_changes_job() -> None:
    logger.info("Change detection runs during snapshot ingestion; no backfill needed.")


def send_alerts_job() -> int:
    init_db()
    with get_session() as session:
        sent = send_unsent_alerts(session)
    logger.info("Sent %s Telegram alerts", sent)
    return sent


def weekly_report_job() -> dict[str, object]:
    paths = generate_weekly_report()
    logger.info("Weekly report generated: %s", paths)
    return paths


def run_scheduler() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_scraping_pipeline, "interval", hours=6, kwargs={"send_alerts": True}, id="scrape_every_6h")
    scheduler.add_job(clean_data_job, "interval", hours=6, id="clean_every_6h")
    scheduler.add_job(send_alerts_job, "interval", minutes=30, id="send_alerts")
    scheduler.add_job(weekly_report_job, "cron", day_of_week="mon", hour=8, minute=0, id="weekly_report")
    logger.info("Scheduler started. Press Ctrl+C to stop.")
    scheduler.start()
