from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import PriceSnapshot, Product
from database.repositories import AlertRepository


PRICE_DROP_THRESHOLD = -5.0
PRICE_INCREASE_THRESHOLD = 10.0


@dataclass(frozen=True)
class DetectedChange:
    alert_type: str
    message: str
    percent_change: float | None = None


def _price_change_percent(current_price: float | None, previous_price: float | None) -> float | None:
    if current_price is None or previous_price is None or previous_price <= 0:
        return None
    return round((current_price - previous_price) / previous_price * 100, 2)


def detect_snapshot_change(
    product_name: str,
    current_price: float | None,
    previous_price: float | None,
    current_availability: str | None,
    previous_availability: str | None,
    current_discount: float | None,
    previous_discount: float | None,
) -> list[DetectedChange]:
    changes: list[DetectedChange] = []

    if previous_price is None and previous_availability is None:
        changes.append(
            DetectedChange(
                alert_type="new_product",
                message=f"New product appeared: {product_name}",
            )
        )
        return changes

    price_change = _price_change_percent(current_price, previous_price)
    if price_change is not None:
        if price_change <= PRICE_DROP_THRESHOLD:
            changes.append(
                DetectedChange(
                    alert_type="price_dropped",
                    message=f"{product_name} price dropped by {abs(price_change):.2f}%",
                    percent_change=price_change,
                )
            )
        elif price_change >= PRICE_INCREASE_THRESHOLD:
            changes.append(
                DetectedChange(
                    alert_type="price_increased",
                    message=f"{product_name} price increased by {price_change:.2f}%",
                    percent_change=price_change,
                )
            )

    current_availability = current_availability or "unknown"
    previous_availability = previous_availability or "unknown"
    if current_availability != previous_availability:
        if current_availability == "out_of_stock":
            alert_type = "out_of_stock"
            message = f"{product_name} went out of stock"
        elif previous_availability == "out_of_stock":
            alert_type = "back_in_stock"
            message = f"{product_name} came back in stock"
        else:
            alert_type = "availability_changed"
            message = f"{product_name} availability changed from {previous_availability} to {current_availability}"
        changes.append(DetectedChange(alert_type=alert_type, message=message))

    current_discount_value = current_discount or 0
    previous_discount_value = previous_discount or 0
    if current_discount_value > 0 and previous_discount_value <= 0:
        changes.append(
            DetectedChange(
                alert_type="discount_appeared",
                message=f"{product_name} now has a {current_discount_value:.2f}% discount",
            )
        )

    return changes


def detect_changes_for_snapshots(
    product: Product,
    current_snapshot: PriceSnapshot,
    previous_snapshot: PriceSnapshot | None,
) -> list[DetectedChange]:
    return detect_snapshot_change(
        product_name=product.product_name,
        current_price=current_snapshot.current_price,
        previous_price=previous_snapshot.current_price if previous_snapshot else None,
        current_availability=current_snapshot.availability,
        previous_availability=previous_snapshot.availability if previous_snapshot else None,
        current_discount=current_snapshot.discount_percent,
        previous_discount=previous_snapshot.discount_percent if previous_snapshot else None,
    )


def create_alerts_for_snapshot(
    session: Session,
    product: Product,
    current_snapshot: PriceSnapshot,
    previous_snapshot: PriceSnapshot | None,
) -> int:
    changes = detect_changes_for_snapshots(product, current_snapshot, previous_snapshot)
    for change in changes:
        AlertRepository.create_alert(session, product.id, change.alert_type, change.message)
    return len(changes)
