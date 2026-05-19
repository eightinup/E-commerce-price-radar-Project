from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import Product, ProductMatch
from pipelines.clean_products import normalize_product_name

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - fallback is tested when rapidfuzz is absent.
    fuzz = None


@dataclass
class MatchGroup:
    master_product_name: str
    normalized_master: str
    product_ids: list[int] = field(default_factory=list)
    names: list[str] = field(default_factory=list)


def _token_stats(left: str, right: str) -> tuple[float, float, int]:
    left_tokens = set(normalize_product_name(left).split())
    right_tokens = set(normalize_product_name(right).split())
    if not left_tokens or not right_tokens:
        return 0.0, 0.0, 0
    common_count = len(left_tokens & right_tokens)
    overlap = common_count / len(left_tokens | right_tokens) * 100
    containment = common_count / min(len(left_tokens), len(right_tokens)) * 100
    return overlap, containment, common_count


def calculate_match_score(left: str, right: str) -> float:
    left_norm = normalize_product_name(left)
    right_norm = normalize_product_name(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 100.0

    overlap_score, containment_score, common_count = _token_stats(left_norm, right_norm)
    if fuzz:
        token_score = float(fuzz.token_set_ratio(left_norm, right_norm))
        partial_score = float(fuzz.partial_ratio(left_norm, right_norm))
        rapid_score = (token_score * 0.75) + (partial_score * 0.25)
        containment_weighted = (overlap_score * 0.35) + (containment_score * 0.65)
        score = max(rapid_score, containment_weighted)
        if containment_score >= 80 and common_count >= 4:
            score += 7
        return round(min(score, 100.0), 2)

    sequence_score = SequenceMatcher(None, left_norm, right_norm).ratio() * 100
    token_score = (overlap_score * 0.35) + (containment_score * 0.65)
    score = max(sequence_score, token_score)

    # Product titles often differ by brand/color adjectives while sharing model,
    # storage, and generation tokens. Reward that strong shared core.
    if containment_score >= 80 and common_count >= 4:
        score += 7

    return round(min(score, 100.0), 2)


def build_match_groups(products: Iterable[Product], threshold: float = 82.0) -> list[MatchGroup]:
    product_list = list(products)
    if not product_list:
        return []

    parent = list(range(len(product_list)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index, left_product in enumerate(product_list):
        for right_index in range(left_index + 1, len(product_list)):
            right_product = product_list[right_index]
            if calculate_match_score(left_product.product_name, right_product.product_name) >= threshold:
                union(left_index, right_index)

    grouped: dict[int, list[Product]] = {}
    for index, product in enumerate(product_list):
        grouped.setdefault(find(index), []).append(product)

    groups: list[MatchGroup] = []
    for grouped_products in grouped.values():
        master = max(grouped_products, key=lambda item: len(item.product_name))
        groups.append(
            MatchGroup(
                master_product_name=master.product_name,
                normalized_master=normalize_product_name(master.product_name),
                product_ids=[product.id for product in grouped_products],
                names=[product.product_name for product in grouped_products],
            )
        )
    return groups


def create_product_matches(session: Session, threshold: float = 82.0) -> int:
    products = list(session.scalars(select(Product).order_by(Product.normalized_name)))
    groups = build_match_groups(products, threshold=threshold)

    session.execute(delete(ProductMatch))
    created = 0
    for group in groups:
        for product_id in group.product_ids:
            product = session.get(Product, product_id)
            if not product:
                continue
            score = calculate_match_score(product.product_name, group.master_product_name)
            session.add(
                ProductMatch(
                    master_product_name=group.master_product_name,
                    product_id=product.id,
                    match_score=score,
                )
            )
            created += 1
    session.flush()
    return created
