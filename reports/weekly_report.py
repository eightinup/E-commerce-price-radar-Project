from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from config.settings import EXPORTS_DIR
from database.db import get_session, init_db
from pipelines.pricing_insights import (
    biggest_price_moves,
    load_latest_market_snapshot,
    load_price_history,
    out_of_stock_products,
    pricing_opportunities,
    strong_discounts,
)


def _safe_export(df: pd.DataFrame, path: Path) -> None:
    if df.empty:
        pd.DataFrame({"message": ["No data available"]}).to_csv(path, index=False)
    else:
        df.to_csv(path, index=False)


def generate_weekly_report(output_dir: Path = EXPORTS_DIR) -> dict[str, Path]:
    init_db()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    with get_session() as session:
        latest = load_latest_market_snapshot(session)
        history = load_price_history(session)
        drops, increases = biggest_price_moves(history)
        oos = out_of_stock_products(latest)
        discounts = strong_discounts(latest)
        opportunities = pricing_opportunities(latest)
        competitor_summary = (
            latest.groupby("competitor")
            .agg(
                products_tracked=("product_id", "count"),
                average_price=("current_price", "mean"),
                average_discount=("discount_percent", "mean"),
                out_of_stock=("availability", lambda value: int((value == "out_of_stock").sum())),
            )
            .round(2)
            .reset_index()
            if not latest.empty
            else pd.DataFrame()
        )

    csv_path = output_dir / f"weekly_price_radar_report_{stamp}.csv"
    excel_path = output_dir / f"weekly_price_radar_report_{stamp}.xlsx"
    _safe_export(opportunities, csv_path)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        sheets = {
            "Top Price Drops": drops,
            "Top Price Increases": increases,
            "Out Of Stock": oos,
            "Strong Discounts": discounts,
            "Pricing Opportunities": opportunities,
            "Competitor Summary": competitor_summary,
        }
        for sheet_name, df in sheets.items():
            export_df = df if not df.empty else pd.DataFrame({"message": ["No data available"]})
            export_df.to_excel(writer, sheet_name=sheet_name, index=False)

    return {"csv": csv_path, "excel": excel_path}
