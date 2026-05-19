from pipelines.detect_changes import detect_snapshot_change


def test_detects_price_drop_above_threshold() -> None:
    changes = detect_snapshot_change(
        "Sony WH-1000XM5",
        current_price=299.0,
        previous_price=349.0,
        current_availability="in_stock",
        previous_availability="in_stock",
        current_discount=0,
        previous_discount=0,
    )
    assert any(change.alert_type == "price_dropped" for change in changes)


def test_detects_price_increase_above_threshold() -> None:
    changes = detect_snapshot_change(
        "Dell XPS 13 Plus",
        current_price=1399.0,
        previous_price=1199.0,
        current_availability="in_stock",
        previous_availability="in_stock",
        current_discount=0,
        previous_discount=0,
    )
    assert any(change.alert_type == "price_increased" for change in changes)


def test_detects_availability_and_discount_changes() -> None:
    changes = detect_snapshot_change(
        "Garmin Forerunner 965",
        current_price=499.0,
        previous_price=599.0,
        current_availability="out_of_stock",
        previous_availability="in_stock",
        current_discount=12,
        previous_discount=0,
    )
    alert_types = {change.alert_type for change in changes}
    assert "out_of_stock" in alert_types
    assert "discount_appeared" in alert_types
