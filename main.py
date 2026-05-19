from __future__ import annotations

import argparse
import logging
import subprocess
import sys

from alerts.telegram_alerts import TelegramAlertClient
from config.settings import PROJECT_ROOT, setup_logging
from database.db import init_db
from database.seed import seed_sample_data
from reports.weekly_report import generate_weekly_report
from scheduler.jobs import run_scheduler, run_scraping_pipeline


logger = logging.getLogger(__name__)


def launch_dashboard() -> int:
    dashboard_path = PROJECT_ROOT / "dashboard" / "app.py"
    command = [sys.executable, "-m", "streamlit", "run", str(dashboard_path)]
    return subprocess.call(command, cwd=PROJECT_ROOT)


def send_test_alert() -> int:
    client = TelegramAlertClient()
    ok = client.send_message("PriceRadar test alert: Telegram integration is configured correctly.")
    if ok:
        print("Test Telegram alert sent.")
        return 0
    print("Telegram alert was not sent. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.")
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PriceRadar competitor price intelligence platform")
    parser.add_argument(
        "command",
        choices=["scrape", "seed", "dashboard", "report", "test-alert", "schedule"],
        help="Command to run",
    )
    parser.add_argument("--send-alerts", action="store_true", help="Send Telegram alerts after scraping")
    return parser.parse_args()


def main() -> int:
    setup_logging()
    args = parse_args()
    init_db()

    if args.command == "scrape":
        total = run_scraping_pipeline(send_alerts=args.send_alerts)
        print(f"Scraping completed. Products processed: {total}")
        return 0
    if args.command == "seed":
        result = seed_sample_data(reset=True)
        print(
            "Seed completed: "
            f"{result['products']} products, {result['snapshots']} snapshots, "
            f"{result['alerts']} alerts, {result['matches']} matches."
        )
        return 0
    if args.command == "dashboard":
        return launch_dashboard()
    if args.command == "report":
        paths = generate_weekly_report()
        print(f"Report generated:\nCSV: {paths['csv']}\nExcel: {paths['excel']}")
        return 0
    if args.command == "test-alert":
        return send_test_alert()
    if args.command == "schedule":
        run_scheduler()
        return 0

    logger.error("Unknown command: %s", args.command)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
