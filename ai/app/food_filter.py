"""Local receipt-category rules, loaded once; never caches customer descriptions."""

import json
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.schemas import DraftItem, DraftResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
RULES_PATH = Path(__file__).parent / "data/product_categories.json"
_BOUNDARIES = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")
_SEPARATORS = re.compile(r"[_\W]+", re.UNICODE)


def normalize_description(text: str | None) -> str:
    """A private matching view; callers retain the original receipt evidence."""
    value = unicodedata.normalize("NFKC", text or "").casefold().replace("\\n", "\n")
    return " ".join(_SEPARATORS.sub(" ", _BOUNDARIES.sub(" ", value)).split())


class FoodCategory(StrEnum):
    FOOD = "food"
    NON_FOOD = "non_food"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class CategoryDecision:
    category: FoodCategory
    rule_id: str | None = None


@dataclass(frozen=True)
class CategoryRule:
    identity: str
    scope: str
    patterns: tuple[re.Pattern, ...]
    unless: tuple[re.Pattern, ...] = ()

    def matches(self, text: str) -> bool:
        return all(p.search(text) for p in self.patterns) and not any(
            p.search(text) for p in self.unless
        )


def _rule(entry: dict, default_scope: str = "raw") -> CategoryRule:
    identity = entry["id"]
    scope = entry.get("scope", default_scope)
    expressions = entry["all_of"]
    if not isinstance(identity, str) or not identity or scope not in {"raw", "both"}:
        raise ValueError("Invalid product category rule identity/scope")
    if not expressions or not all(isinstance(p, str) and p for p in expressions):
        raise ValueError("A category rule requires nonempty patterns")
    return CategoryRule(
        identity,
        scope,
        tuple(re.compile(p) for p in expressions),
        tuple(re.compile(p) for p in entry.get("unless", [])),
    )


def _load_rules(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["schema_version"] != 1:
        raise ValueError("Unsupported product category rules version")
    negative = tuple(_rule(entry) for entry in data["non_food_rules"])
    positive = tuple(_rule(entry) for entry in data["food_exceptions"])
    grooming = _rule(data["generic_grooming_rule"], "both")
    identities = [r.identity for r in (*negative, *positive, grooming)]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate product category rule identity")
    metadata = frozenset(normalize_description(name) for name in data["metadata_names"])
    return negative, positive, grooming, metadata


# Static deployment data and compiled expressions only. No raw-text memoization,
# product-network lookup, database connection or model call on the request path.
_NEGATIVE, _POSITIVE, _GROOMING, _METADATA = _load_rules(RULES_PATH)


def classify_receipt_item(item: DraftItem) -> CategoryDecision:
    raw = normalize_description(item.raw_text)
    name = normalize_description(item.display_name)
    # Strong source evidence wins over a food name invented by the model.
    for rule in _NEGATIVE:
        if rule.matches(raw):
            return CategoryDecision(FoodCategory.NON_FOOD, rule.identity)
    for rule in _POSITIVE:
        if rule.matches(raw):
            return CategoryDecision(FoodCategory.FOOD, rule.identity)
    if _GROOMING.matches(raw):
        return CategoryDecision(FoodCategory.NON_FOOD, _GROOMING.identity)
    for rule in _NEGATIVE:
        if rule.scope == "both" and rule.matches(name):
            return CategoryDecision(FoodCategory.NON_FOOD, rule.identity)
    if name in _METADATA:
        return CategoryDecision(FoodCategory.NON_FOOD, "receipt_metadata")
    if _GROOMING.matches(name):
        return CategoryDecision(FoodCategory.NON_FOOD, _GROOMING.identity)
    return CategoryDecision(FoodCategory.UNCLASSIFIED)


def filter_receipt_foods(draft: DraftResult) -> DraftResult:
    """Reject confirmed non-food; an unmatched rule is not an ingredient whitelist."""
    kept = []
    rejected = Counter()
    for item in draft.items:
        decision = classify_receipt_item(item)
        if decision.category is FoodCategory.NON_FOOD:
            rejected[decision.rule_id] += 1
        else:
            kept.append(item)
    if rejected:
        logger.info(
            json.dumps(
                {
                    "event": "receipt_food_filter",
                    "removed_items": sum(rejected.values()),
                    "rule_counts": dict(rejected),
                }
            )
        )
    return DraftResult(items=kept)
