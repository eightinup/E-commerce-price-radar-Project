from pipelines.clean_products import (
    calculate_discount,
    clean_availability,
    clean_price,
    normalize_product_name,
)


def test_clean_price_handles_common_currency_formats() -> None:
    assert clean_price("$1,299.99") == 1299.99
    assert clean_price("1 299,50 USD") == 1299.50
    assert clean_price("EUR 2.199,00") == 2199.00
    assert clean_price("out of stock") is None


def test_normalize_product_name_keeps_model_storage_tokens() -> None:
    assert normalize_product_name("Apple iPhone 15 Pro 256 GB - Natural Titanium") == (
        "apple iphone 15 pro 256gb natural titanium"
    )


def test_calculate_discount() -> None:
    assert calculate_discount(899.0, 999.0) == 10.01
    assert calculate_discount(999.0, 899.0) == 0.0
    assert calculate_discount(None, 999.0) is None


def test_clean_availability() -> None:
    assert clean_availability("Only 3 left - low stock") == "limited_stock"
    assert clean_availability("Sold out") == "out_of_stock"
    assert clean_availability("Ships today") == "in_stock"
