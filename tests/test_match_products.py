from pipelines.match_products import calculate_match_score


def test_fuzzy_matching_groups_iphone_variants() -> None:
    left = "iPhone 15 Pro 256GB Natural Titanium"
    right = "Apple iPhone 15 Pro 256 GB Titanium"
    assert calculate_match_score(left, right) >= 82


def test_fuzzy_matching_separates_different_products() -> None:
    left = "Sony WH-1000XM5 Wireless Headphones"
    right = "Dell XPS 13 Plus Laptop"
    assert calculate_match_score(left, right) < 60
