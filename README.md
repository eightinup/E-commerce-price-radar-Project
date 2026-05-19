# PriceRadar - Competitor Price Intelligence Platform

PriceRadar is a production-style Python portfolio project for automated competitor price monitoring. It scrapes competitor product pages, stores historical price snapshots, detects price and stock changes, generates pricing insights, sends Telegram alerts, and presents everything in a Streamlit dashboard.

> "I build automated competitor price monitoring systems for e-commerce businesses. These systems track competitor prices, discounts, stock availability, product changes, and generate actionable pricing insights."

## Business Problem

E-commerce sellers need to react quickly when competitors change prices, launch discounts, or run out of stock. Manual monitoring is slow, inconsistent, and usually misses the historical context needed for pricing decisions.

PriceRadar answers practical commercial questions:

- Who is cheaper for the same product?
- Which competitors changed prices recently?
- Which products are out of stock?
- Where did discounts appear?
- How did prices move over time?
- Which products have pricing opportunities or customer-loss risk?

## Solution

PriceRadar provides an end-to-end competitive intelligence workflow:

- Playwright-based scraping architecture with retry logic, logging, raw HTML storage, and local sample HTML fallback.
- SQLAlchemy ORM database with competitors, products, price snapshots, scrape runs, alerts, and product matches.
- Data cleaning pipeline for prices, names, brands, discounts, availability, ratings, and duplicates.
- Fuzzy product matching to group equivalent products across stores.
- Change detection for price drops, price increases, discounts, stock changes, and new products.
- Pricing insights for cheapest competitor, average market price, price gaps, strong discounts, out-of-stock products, and pricing opportunities.
- Streamlit dashboard with Plotly charts and CSV/Excel export.
- Telegram Bot API integration that degrades gracefully when credentials are missing.
- Weekly CSV/Excel report generation.
- Scheduler jobs for scraping, matching, alerting, and reporting.
- Docker and docker-compose support.

## Tech Stack

- Python 3.11+
- Playwright
- BeautifulSoup and lxml
- pandas
- SQLAlchemy ORM
- SQLite for local development
- PostgreSQL-ready database URL configuration
- Streamlit
- Plotly
- APScheduler
- Telegram Bot API
- pytest
- python-dotenv
- Docker

## Architecture

```text
price-radar/
├── scrapers/        # BaseScraper plus demo competitor scrapers
├── database/        # SQLAlchemy models, session setup, repositories, seed data
├── pipelines/       # Cleaning, product matching, change detection, pricing insights
├── alerts/          # Telegram integration and alert formatting
├── dashboard/       # Streamlit application
├── reports/         # Weekly CSV/Excel report generation
├── scheduler/       # APScheduler jobs
├── tests/           # pytest coverage for core data logic
├── data/            # raw HTML, processed data, exports, SQLite database
├── logs/            # application logs
└── main.py          # CLI entrypoint
```

## Database Schema

PriceRadar uses normalized relational tables:

- `competitors`: competitor identity and source URL.
- `products`: product metadata, URL, seller, brand, category, and competitor relationship.
- `price_snapshots`: historical price, discount, availability, rating, review count, and scrape timestamp.
- `scrape_runs`: scrape status, timing, product count, and error details.
- `alerts`: detected business events and Telegram send state.
- `product_matches`: fuzzy grouping between competitor product variants and a master product name.

SQLite is the default for local demos. For PostgreSQL, set `DATABASE_URL` in `.env`.

## Dashboard

The Streamlit dashboard includes:

- Overview metrics for tracked products, competitors, snapshots, alerts, average discount, and out-of-stock count.
- Competitor comparison table with cheapest competitor, average market price, and price gap.
- Price history line charts with competitor comparison.
- Recent alerts grouped by type.
- Pricing opportunities and customer-loss risk.
- CSV and Excel exports.

## Screenshots

Add screenshots after running the app:

- `docs/screenshots/overview.png`
- `docs/screenshots/price-history.png`
- `docs/screenshots/pricing-opportunities.png`

## Installation

```bash
git clone <your-repo-url>
cd E-commerce-price-radar-Project
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install
```

## Environment Variables

Copy the example file and fill in optional Telegram credentials:

```bash
cp .env.example .env
```

```env
DATABASE_URL=sqlite:///data/price_radar.db
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SCRAPER_USER_AGENT=PriceRadarBot/1.0 (+https://example.com/price-radar-portfolio)
SCRAPER_TIMEOUT_MS=30000
SCRAPER_RETRIES=3
OWN_COMPETITOR_NAME=Demo Store
LOG_LEVEL=INFO
```

Missing Telegram credentials will not crash the app. Alerts are logged and remain unsent.

## How To Run

Seed demo data:

```bash
python main.py seed
```

Run sample HTML scraping pipeline:

```bash
python main.py scrape
```

Launch dashboard:

```bash
streamlit run dashboard/app.py
```

Or through the CLI:

```bash
python main.py dashboard
```

Generate weekly report:

```bash
python main.py report
```

Send test Telegram alert:

```bash
python main.py test-alert
```

Run scheduler:

```bash
python main.py schedule
```

Run tests:

```bash
pytest
```

## Docker

```bash
docker compose up --build
```

Then open:

```text
http://localhost:8501
```

To seed data inside the container:

```bash
docker compose run --rm price-radar python main.py seed
```

## Demo Data Strategy

Live e-commerce websites can block automated scraping or change markup without warning. PriceRadar includes generated sample HTML and deterministic seed data so the project remains demoable offline. The same scraper interface can be extended for real competitor stores by adding new scraper classes.

## Business Value

PriceRadar helps sellers:

- Protect margin by identifying products priced too low versus the market.
- Reduce customer-loss risk by detecting products priced too high.
- React to competitor discounts and stockouts quickly.
- Build historical pricing intelligence for category and assortment planning.
- Automate repetitive competitor monitoring work.

## Future Improvements

- Add proxy rotation and CAPTCHA-aware retry handling.
- Add marketplace-specific scrapers for Shopify, WooCommerce, Amazon-style catalogs, and regional stores.
- Add product matching review workflow for human approval.
- Add margin and inventory data for profit-aware repricing.
- Add Slack/email alerts.
- Add REST API with FastAPI.
- Add PostgreSQL migrations with Alembic.
- Add authentication and multi-tenant account separation.

## Freelancer Positioning

This project demonstrates the kind of system a freelance Python data extraction engineer can build for e-commerce clients: reliable scraping, normalized storage, historical monitoring, alerting, reporting, and executive-ready dashboards.
