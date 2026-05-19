from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from database.models import Alert, Competitor, PriceSnapshot, Product, ScrapeRun


class CompetitorRepository:
    @staticmethod
    def get_or_create(session: Session, name: str, website_url: str) -> Competitor:
        competitor = session.scalar(select(Competitor).where(Competitor.name == name))
        if competitor:
            if competitor.website_url != website_url:
                competitor.website_url = website_url
            return competitor

        competitor = Competitor(name=name, website_url=website_url)
        session.add(competitor)
        session.flush()
        return competitor


class ProductRepository:
    @staticmethod
    def upsert_product(session: Session, competitor: Competitor, product_data: dict[str, Any]) -> Product:
        product_url = str(product_data["product_url"])
        product = session.scalar(
            select(Product).where(
                Product.competitor_id == competitor.id,
                Product.product_url == product_url,
            )
        )

        fields = {
            "product_name": product_data["product_name"],
            "normalized_name": product_data["normalized_name"],
            "brand": product_data.get("brand"),
            "category": product_data.get("category"),
            "image_url": product_data.get("image_url"),
            "seller_name": product_data.get("seller_name"),
        }
        if product:
            for key, value in fields.items():
                setattr(product, key, value)
            product.updated_at = datetime.utcnow()
            return product

        product = Product(
            competitor_id=competitor.id,
            product_url=product_url,
            **fields,
        )
        session.add(product)
        session.flush()
        return product


class PriceSnapshotRepository:
    @staticmethod
    def latest_for_product(session: Session, product_id: int) -> PriceSnapshot | None:
        return session.scalar(
            select(PriceSnapshot)
            .where(PriceSnapshot.product_id == product_id)
            .order_by(desc(PriceSnapshot.scraped_at), desc(PriceSnapshot.id))
            .limit(1)
        )

    @staticmethod
    def add_snapshot(session: Session, product_id: int, product_data: dict[str, Any]) -> PriceSnapshot:
        snapshot = PriceSnapshot(
            product_id=product_id,
            current_price=product_data.get("current_price"),
            old_price=product_data.get("old_price"),
            discount_percent=product_data.get("discount_percent"),
            availability=product_data.get("availability") or "unknown",
            rating=product_data.get("rating"),
            review_count=product_data.get("review_count"),
            scraped_at=product_data.get("scraped_at") or datetime.utcnow(),
        )
        session.add(snapshot)
        session.flush()
        return snapshot


class ScrapeRunRepository:
    @staticmethod
    def start(session: Session, competitor: Competitor) -> ScrapeRun:
        run = ScrapeRun(competitor_id=competitor.id, status="running")
        session.add(run)
        session.flush()
        return run

    @staticmethod
    def finish(
        session: Session,
        run: ScrapeRun,
        status: str,
        products_found: int = 0,
        error_message: str | None = None,
    ) -> ScrapeRun:
        run.status = status
        run.products_found = products_found
        run.error_message = error_message
        run.finished_at = datetime.utcnow()
        session.flush()
        return run


class AlertRepository:
    @staticmethod
    def create_alert(session: Session, product_id: int, alert_type: str, message: str) -> Alert:
        alert = Alert(product_id=product_id, alert_type=alert_type, message=message)
        session.add(alert)
        session.flush()
        return alert

    @staticmethod
    def unsent(session: Session, limit: int = 50) -> list[Alert]:
        return list(
            session.scalars(
                select(Alert)
                .where(Alert.is_sent.is_(False))
                .order_by(desc(Alert.triggered_at))
                .limit(limit)
            )
        )

    @staticmethod
    def mark_sent(session: Session, alert: Alert) -> None:
        alert.is_sent = True
        session.flush()
