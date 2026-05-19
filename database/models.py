from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True, index=True)
    website_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    products = relationship("Product", back_populates="competitor", cascade="all, delete-orphan")
    scrape_runs = relationship("ScrapeRun", back_populates="competitor", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("competitor_id", "product_url", name="uq_product_competitor_url"),
        Index("ix_products_normalized_competitor", "normalized_name", "competitor_id"),
    )

    id = Column(Integer, primary_key=True)
    product_name = Column(String(300), nullable=False)
    normalized_name = Column(String(300), nullable=False, index=True)
    brand = Column(String(120), nullable=True, index=True)
    category = Column(String(120), nullable=True, index=True)
    product_url = Column(String(700), nullable=False)
    image_url = Column(String(700), nullable=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False, index=True)
    seller_name = Column(String(160), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    competitor = relationship("Competitor", back_populates="products")
    price_snapshots = relationship(
        "PriceSnapshot",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="PriceSnapshot.scraped_at",
    )
    alerts = relationship("Alert", back_populates="product", cascade="all, delete-orphan")
    matches = relationship("ProductMatch", back_populates="product", cascade="all, delete-orphan")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (Index("ix_snapshots_product_scraped", "product_id", "scraped_at"),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    current_price = Column(Float, nullable=True)
    old_price = Column(Float, nullable=True)
    discount_percent = Column(Float, nullable=True)
    availability = Column(String(60), nullable=False, default="unknown", index=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    product = relationship("Product", back_populates="price_snapshots")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="running", index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    products_found = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    competitor = relationship("Competitor", back_populates="scrape_runs")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_product_type_time", "product_id", "alert_type", "triggered_at"),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    alert_type = Column(String(80), nullable=False, index=True)
    message = Column(Text, nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_sent = Column(Boolean, default=False, nullable=False, index=True)

    product = relationship("Product", back_populates="alerts")


class ProductMatch(Base):
    __tablename__ = "product_matches"
    __table_args__ = (UniqueConstraint("master_product_name", "product_id", name="uq_match_master_product"),)

    id = Column(Integer, primary_key=True)
    master_product_name = Column(String(300), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    match_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="matches")
