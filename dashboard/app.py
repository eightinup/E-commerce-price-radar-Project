from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import desc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db import get_session, init_db
from database.models import Alert
from pipelines.pricing_insights import (
    biggest_price_moves,
    load_latest_market_snapshot,
    load_price_history,
    market_summary,
    overview_metrics,
    pricing_opportunities,
)


st.set_page_config(page_title="PriceRadar", page_icon="PR", layout="wide")


st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .small-muted {color: #64748b; font-size: 0.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60)
def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], pd.DataFrame]:
    init_db()
    with get_session() as session:
        latest = load_latest_market_snapshot(session)
        history = load_price_history(session)
        metrics = overview_metrics(session)
        alert_rows = []
        alerts = session.query(Alert).order_by(desc(Alert.triggered_at)).limit(100).all()
        for alert in alerts:
            alert_rows.append(
                {
                    "triggered_at": alert.triggered_at,
                    "alert_type": alert.alert_type.replace("_", " ").title(),
                    "product": alert.product.product_name,
                    "competitor": alert.product.competitor.name,
                    "message": alert.message,
                    "is_sent": alert.is_sent,
                }
            )
        alerts_df = pd.DataFrame(alert_rows)
    return latest, history, metrics, alerts_df


def filtered_latest(latest: pd.DataFrame) -> pd.DataFrame:
    if latest.empty:
        return latest

    categories = ["All"] + sorted(latest["category"].dropna().unique().tolist())
    competitors = ["All"] + sorted(latest["competitor"].dropna().unique().tolist())
    category = st.sidebar.selectbox("Category", categories)
    competitor = st.sidebar.selectbox("Competitor", competitors)

    filtered = latest.copy()
    if category != "All":
        filtered = filtered[filtered["category"] == category]
    if competitor != "All":
        filtered = filtered[filtered["competitor"] == competitor]
    return filtered


def dataframe_downloads(df: pd.DataFrame, name: str) -> None:
    if df.empty:
        return

    csv = df.to_csv(index=False).encode("utf-8")
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="export")

    left, right = st.columns(2)
    left.download_button("Download CSV", csv, file_name=f"{name}.csv", mime="text/csv", use_container_width=True)
    right.download_button(
        "Download Excel",
        excel_buffer.getvalue(),
        file_name=f"{name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


latest_df, history_df, metrics, alerts_df = load_dashboard_data()

st.sidebar.title("PriceRadar")
page = st.sidebar.radio(
    "Workspace",
    ["Overview", "Competitor Comparison", "Price History", "Alerts", "Pricing Opportunities", "Export"],
)

st.title("PriceRadar")
st.caption("Competitor price intelligence for e-commerce teams")

if latest_df.empty:
    st.warning("No data found. Run `python main.py seed` from the project folder.")
    st.stop()

latest_filtered = filtered_latest(latest_df)

if page == "Overview":
    columns = st.columns(6)
    columns[0].metric("Products", f"{metrics['total_products']:,}")
    columns[1].metric("Competitors", f"{metrics['total_competitors']:,}")
    columns[2].metric("Snapshots", f"{metrics['total_price_snapshots']:,}")
    columns[3].metric("Active Alerts", f"{metrics['active_alerts']:,}")
    columns[4].metric("Avg Discount", f"{metrics['average_discount']}%")
    columns[5].metric("Out of Stock", f"{metrics['out_of_stock_count']:,}")

    left, right = st.columns([1.15, 0.85])
    with left:
        summary = market_summary(latest_filtered)
        st.subheader("Market Price Gaps")
        if not summary.empty:
            fig = px.bar(
                summary.head(10),
                x="price_gap",
                y="master_product_name",
                color="cheapest_competitor",
                orientation="h",
                labels={"price_gap": "Price gap", "master_product_name": "Product"},
            )
            fig.update_layout(height=430, yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No comparable prices for the current filters.")

    with right:
        st.subheader("Competitor Inventory")
        inventory = (
            latest_filtered.groupby(["competitor", "availability"])
            .size()
            .reset_index(name="products")
            .sort_values("products", ascending=False)
        )
        fig = px.bar(inventory, x="competitor", y="products", color="availability", barmode="stack")
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Latest Product Snapshot")
    st.dataframe(
        latest_filtered[
            [
                "master_product_name",
                "competitor",
                "category",
                "current_price",
                "old_price",
                "discount_percent",
                "availability",
                "rating",
                "review_count",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

elif page == "Competitor Comparison":
    st.subheader("Competitor Comparison")
    summary = market_summary(latest_filtered)
    if not summary.empty:
        st.dataframe(summary, use_container_width=True, hide_index=True)
        fig = px.scatter(
            latest_filtered.dropna(subset=["current_price"]),
            x="master_product_name",
            y="current_price",
            color="competitor",
            size="discount_percent",
            hover_data=["availability", "rating"],
        )
        fig.update_layout(height=520, xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No competitor comparison data for the selected filters.")

elif page == "Price History":
    st.subheader("Price History")
    product_options = sorted(history_df["master_product_name"].dropna().unique().tolist())
    selected_product = st.selectbox("Product", product_options)
    product_history = history_df[history_df["master_product_name"] == selected_product].copy()
    fig = px.line(
        product_history,
        x="scraped_at",
        y="current_price",
        color="competitor",
        markers=True,
        labels={"scraped_at": "Date", "current_price": "Price"},
    )
    fig.update_layout(height=520)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(product_history.sort_values("scraped_at", ascending=False), use_container_width=True, hide_index=True)

elif page == "Alerts":
    st.subheader("Recent Alerts")
    if alerts_df.empty:
        st.info("No alerts yet.")
    else:
        alert_counts = alerts_df.groupby("alert_type").size().reset_index(name="count")
        fig = px.bar(alert_counts, x="alert_type", y="count", color="alert_type")
        fig.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(alerts_df, use_container_width=True, hide_index=True)

elif page == "Pricing Opportunities":
    st.subheader("Pricing Opportunities")
    opportunities = pricing_opportunities(latest_filtered)
    if opportunities.empty:
        st.info("No pricing opportunities for the current filters.")
    else:
        fig = px.bar(
            opportunities,
            x="price_gap_percent",
            y="master_product_name",
            color="opportunity_type",
            orientation="h",
            labels={"price_gap_percent": "Gap vs competitor average (%)", "master_product_name": "Product"},
        )
        fig.update_layout(height=460, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(opportunities, use_container_width=True, hide_index=True)
        dataframe_downloads(opportunities, "pricing_opportunities")

elif page == "Export":
    st.subheader("Export")
    export_choice = st.selectbox("Dataset", ["Latest Snapshot", "Price History", "Market Summary", "Alerts"])
    if export_choice == "Latest Snapshot":
        export_df = latest_filtered
    elif export_choice == "Price History":
        export_df = history_df
    elif export_choice == "Market Summary":
        export_df = market_summary(latest_filtered)
    else:
        export_df = alerts_df

    st.dataframe(export_df, use_container_width=True, hide_index=True)
    dataframe_downloads(export_df, export_choice.lower().replace(" ", "_"))
