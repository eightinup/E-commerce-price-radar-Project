from __future__ import annotations

from database.models import Alert


ALERT_LABELS = {
    "new_product": "New Product",
    "price_dropped": "Price Drop",
    "price_increased": "Price Increase",
    "discount_appeared": "Discount Appeared",
    "out_of_stock": "Out of Stock",
    "back_in_stock": "Back In Stock",
    "availability_changed": "Availability Changed",
}


def format_alert_message(alert: Alert) -> str:
    label = ALERT_LABELS.get(alert.alert_type, alert.alert_type.replace("_", " ").title())
    product = alert.product.product_name if alert.product else "Unknown product"
    competitor = alert.product.competitor.name if alert.product and alert.product.competitor else "Unknown competitor"
    return (
        f"PriceRadar Alert: {label}\n"
        f"Product: {product}\n"
        f"Competitor: {competitor}\n"
        f"Details: {alert.message}\n"
        f"Triggered: {alert.triggered_at:%Y-%m-%d %H:%M}"
    )
