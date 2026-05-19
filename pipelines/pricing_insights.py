from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Alert, Competitor, PriceSnapshot, Product, ProductMatch
from config.settings import settings


def _master_name_map(session: Session) -> dict[int, str]:
    matches = session.scalars(select(ProductMatch)).all()
    return {match.product_id: match.master_product_name for match in matches}


def load_latest_market_snapshot(session: Session) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    master_names = _master_name_map(session)
    products = session.scalars(select(Product).order_by(Product.product_name)).all()

    for product in products:
        latest = (
            session.query(PriceSnapshot)
            .filter(PriceSnapshot.product_id == product.id)
            .order_by(PriceSnapshot.scraped_at.desc(), PriceSnapshot.id.desc())
            .first()
        )
        if not latest:
            continue
        rows.append(
            {
                "product_id": product.id,
                "product_name": product.product_name,
                "master_product_name": master_names.get(product.id, product.product_name),
                "normalized_name": product.normalized_name,
                "brand": product.brand,
                "category": product.category,
                "competitor": product.competitor.name,
                "seller_name": product.seller_name,
                "product_url": product.product_url,
                "image_url": product.image_url,
                "current_price": latest.current_price,
                "old_price": latest.old_price,
                "discount_percent": latest.discount_percent or 0,
                "availability": latest.availability,
                "rating": latest.rating,
                "review_count": latest.review_count,
                "scraped_at": latest.scraped_at,
            }
        )
    return pd.DataFrame(rows)


def load_price_history(session: Session) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    master_names = _master_name_map(session)
    snapshots = (
        session.query(PriceSnapshot)
        .join(Product)
        .join(Competitor)
        .order_by(PriceSnapshot.scraped_at)
        .all()
    )
    for snapshot in snapshots:
        product = snapshot.product
        rows.append(
            {
                "product_id": product.id,
                "product_name": product.product_name,
                "master_product_name": master_names.get(product.id, product.product_name),
                "category": product.category,
                "brand": product.brand,
                "competitor": product.competitor.name,
                "current_price": snapshot.current_price,
                "old_price": snapshot.old_price,
                "discount_percent": snapshot.discount_percent or 0,
                "availability": snapshot.availability,
                "rating": snapshot.rating,
                "review_count": snapshot.review_count,
                "scraped_at": snapshot.scraped_at,
            }
        )
    return pd.DataFrame(rows)


def overview_metrics(session: Session) -> dict[str, Any]:
    latest = load_latest_market_snapshot(session)
    return {
        "total_products": int(session.query(Product).count()),
        "total_competitors": int(session.query(Competitor).count()),
        "total_price_snapshots": int(session.query(PriceSnapshot).count()),
        "active_alerts": int(session.query(Alert).filter(Alert.is_sent.is_(False)).count()),
        "average_discount": round(float(latest["discount_percent"].mean()), 2) if not latest.empty else 0.0,
        "out_of_stock_count": int((latest["availability"] == "out_of_stock").sum()) if not latest.empty else 0,
    }


def market_summary(latest: pd.DataFrame) -> pd.DataFrame:
    if latest.empty:
        return pd.DataFrame()

    priced = latest.dropna(subset=["current_price"]).copy()
    if priced.empty:
        return pd.DataFrame()

    grouped = priced.groupby("master_product_name")
    summary = grouped.agg(
        average_market_price=("current_price", "mean"),
        min_price=("current_price", "min"),
        max_price=("current_price", "max"),
        competitors=("competitor", "nunique"),
    ).reset_index()

    cheapest = priced.loc[grouped["current_price"].idxmin()][["master_product_name", "competitor", "current_price"]]
    cheapest = cheapest.rename(columns={"competitor": "cheapest_competitor", "current_price": "cheapest_price"})
    expensive = priced.loc[grouped["current_price"].idxmax()][["master_product_name", "competitor", "current_price"]]
    expensive = expensive.rename(columns={"competitor": "most_expensive_competitor", "current_price": "highest_price"})

    summary = summary.merge(cheapest, on="master_product_name", how="left")
    summary = summary.merge(expensive, on="master_product_name", how="left")
    summary["price_gap"] = (summary["max_price"] - summary["min_price"]).round(2)
    summary["average_market_price"] = summary["average_market_price"].round(2)
    return summary.sort_values("price_gap", ascending=False)


def pricing_opportunities(
    latest: pd.DataFrame,
    own_competitor_name: str = settings.own_competitor_name,
) -> pd.DataFrame:
    if latest.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    priced = latest.dropna(subset=["current_price"]).copy()
    for master_name, group in priced.groupby("master_product_name"):
        own_rows = group[group["competitor"] == own_competitor_name]
        competitor_rows = group[group["competitor"] != own_competitor_name]
        if own_rows.empty or competitor_rows.empty:
            continue

        own_price = float(own_rows.iloc[0]["current_price"])
        competitor_avg = float(competitor_rows["current_price"].mean())
        if own_price <= 0 or competitor_avg <= 0:
            continue

        gap_percent = round((competitor_avg - own_price) / own_price * 100, 2)
        if gap_percent > 10:
            opportunity_type = "possible price increase opportunity"
            risk_level = "medium"
        elif gap_percent < -10:
            opportunity_type = "risk of losing customers"
            risk_level = "high"
        else:
            continue

        rows.append(
            {
                "master_product_name": master_name,
                "category": own_rows.iloc[0].get("category"),
                "our_price": round(own_price, 2),
                "competitor_average_price": round(competitor_avg, 2),
                "price_gap_percent": gap_percent,
                "opportunity_type": opportunity_type,
                "risk_level": risk_level,
            }
        )

    return pd.DataFrame(rows).sort_values("price_gap_percent", ascending=False) if rows else pd.DataFrame()


def biggest_price_moves(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if history.empty:
        return pd.DataFrame(), pd.DataFrame()

    rows: list[dict[str, Any]] = []
    priced = history.dropna(subset=["current_price"]).sort_values("scraped_at")
    for (product_id, competitor), group in priced.groupby(["product_id", "competitor"]):
        if len(group) < 2:
            continue
        first = group.iloc[0]
        last = group.iloc[-1]
        old_price = float(first["current_price"])
        new_price = float(last["current_price"])
        if old_price <= 0:
            continue
        change_percent = round((new_price - old_price) / old_price * 100, 2)
        rows.append(
            {
                "product_id": product_id,
                "product_name": last["product_name"],
                "master_product_name": last["master_product_name"],
                "competitor": competitor,
                "old_price": round(old_price, 2),
                "new_price": round(new_price, 2),
                "change_percent": change_percent,
                "category": last.get("category"),
            }
        )

    moves = pd.DataFrame(rows)
    if moves.empty:
        return pd.DataFrame(), pd.DataFrame()
    drops = moves[moves["change_percent"] < 0].sort_values("change_percent").head(10)
    increases = moves[moves["change_percent"] > 0].sort_values("change_percent", ascending=False).head(10)
    return drops, increases


def out_of_stock_products(latest: pd.DataFrame) -> pd.DataFrame:
    if latest.empty:
        return pd.DataFrame()
    return latest[latest["availability"] == "out_of_stock"].copy()


def strong_discounts(latest: pd.DataFrame, minimum_discount: float = 15.0) -> pd.DataFrame:
    if latest.empty:
        return pd.DataFrame()
    return latest[latest["discount_percent"] >= minimum_discount].sort_values("discount_percent", ascending=False)
