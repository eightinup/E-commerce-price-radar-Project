from __future__ import annotations

import logging

import requests
from sqlalchemy.orm import Session

from alerts.alert_rules import format_alert_message
from config.settings import settings
from database.repositories import AlertRepository


logger = logging.getLogger(__name__)


class TelegramAlertClient:
    def __init__(
        self,
        bot_token: str | None = settings.telegram_bot_token,
        chat_id: str | None = settings.telegram_chat_id,
        timeout_seconds: int = 10,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, message: str) -> bool:
        if not self.is_configured:
            logger.warning("Telegram credentials are missing. Alert was logged but not sent.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            response = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": message, "disable_web_page_preview": True},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.exception("Failed to send Telegram alert: %s", exc)
            return False


def send_unsent_alerts(session: Session, limit: int = 25) -> int:
    client = TelegramAlertClient()
    sent = 0
    for alert in AlertRepository.unsent(session, limit=limit):
        message = format_alert_message(alert)
        if client.send_message(message):
            AlertRepository.mark_sent(session, alert)
            sent += 1
    return sent
