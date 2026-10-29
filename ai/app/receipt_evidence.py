"""Reconcile receipt amounts with explicit numbers in the model's copied item block.

This is not independent OCR. Never infer missing pack sizes, densities or yields.
Rebuild a supported total instead of multiplying the model's existing total again.
"""

import math
import re
from dataclasses import dataclass
from decimal import Decimal

from app.drafts import normalize_unit
from app.schemas import DraftItem

_NUMBER = r"\d+(?:\.\d+)?"
_CONTENTS = re.compile(
    rf"(?<![\d.,$])(?P<amount>{_NUMBER})\s*"
    r"(?P<unit>kilograms?|kg|grams?|g|millilit(?:er|re)s?|ml|lit(?:er|re)s?|l|"
    r"pieces?|pcs?|s)\b",
    re.IGNORECASE,
)
_CHAIN = re.compile(rf"(?P<factors>(?:{_NUMBER}\s*[x×*]\s*)+)$", re.IGNORECASE)
_PURCHASE = re.compile(
    r"\b(?:qty|quantity)\s*[:=]?\s*(\d+)\b|"
    r"(?m:^\s*(\d+)\s*[x×@*]\s*\$?\d+(?:\.\d+)?(?:\s*/\s*unit)?"
    r"(?:\s+\$?\d+\.\d{2})?\s*$)|"
    r"(?m:^\s*(\d+)\s*$)|"
    r"\b(\d+)\s*(?:packs?|cartons?|bottles?|cans?|jars?|bags?|boxes?|trays?)\b|"
    r"[x×]\s*(\d+)\s*$",
    re.IGNORECASE,
)
_LEADING_COUNT = re.compile(r"^\s*([1-9]\d?)\s+(?=[A-Za-z])")
_SCALES = {
    "g": ("mass", 1),
    "kg": ("mass", 1000),
    "ml": ("volume", 1),
    "l": ("volume", 1000),
    "pcs": ("count", 1),
}


@dataclass(frozen=True)
class Contents:
    amount: Decimal
    unit: str
    factors: tuple[Decimal, ...]
    total: bool
    drained: bool

    @property
    def value(self) -> Decimal:
        result = self.amount
        for factor in self.factors:
            result *= factor
        return result


def _select(values: list[Contents], preferred: str | None) -> Contents | None:
    """Equivalent repeated labels are evidence once; conflicting sizes are unknown."""
    if not values:
        return None
    identities = {(_SCALES[v.unit][0], v.value * _SCALES[v.unit][1]) for v in values}
    if len(identities) != 1:
        return None
    return next((v for v in values if v.unit == preferred), values[0])


def reconcile_receipt_amount(item: DraftItem) -> DraftItem:
    """Return a fresh item; leave the source text and the caller's object untouched."""
    if not item.raw_text:
        return item
    raw = item.raw_text.replace("\\n", "\n")
    preferred = normalize_unit(item.unit)
    values = []
    masked = list(raw)
    for match in _CONTENTS.finditer(raw):
        unit = normalize_unit(match["unit"])
        if unit == "s":
            unit = "pcs"
        if unit not in _SCALES:
            continue
        # A number-unit token explicitly labelled as a price is not contents.
        line_start = raw.rfind("\n", 0, match.start()) + 1
        prefix = raw[line_start : match.start()]
        if re.search(r"(?:unit\s+price|price\s*[:=]?|SGD|\$)\s*\$?\s*$", prefix, re.I):
            continue
        if re.search(r"(?:/|\bper)\s*$", prefix, re.I) and re.search(
            r"\$|\b(?:price|SGD)\b", prefix, re.I
        ):
            continue
        chain = _CHAIN.search(prefix)
        factors = tuple(Decimal(n) for n in re.findall(_NUMBER, chain["factors"])) if chain else ()
        value = Contents(
            Decimal(match["amount"]),
            unit,
            factors,
            bool(
                re.search(
                    r"\btotal(?:\s+(?:net|weight|contents|amount))*\s*[:=]?\s*$", prefix, re.I
                )
            ),
            bool(re.search(r"\bdrained(?:\s+weight)?\s*[:=]?\s*$", prefix, re.I)),
        )
        values.append(value)
        # Remove size numbers/chains before looking for independent purchase counts.
        start = line_start + chain.start() if chain else match.start()
        masked[start : match.end()] = " " * (match.end() - start)
    if not values:
        return item

    totals = [v for v in values if v.total]
    drained = [v for v in values if v.drained]
    # Prefer a printed purchase total, then a printed drained amount. Otherwise
    # retain an explicitly supported model dimension (e.g. pieces on an egg pack).
    candidates = totals or drained or values
    if not totals and not drained:
        dimension = _SCALES.get(preferred, (None,))[0]
        supported = [v for v in values if _SCALES[v.unit][0] == dimension]
        candidates = supported or [v for v in values if v.unit != "pcs"] or values
    selected = _select(candidates, preferred)
    unit = (
        selected.unit
        if selected
        else (candidates[0].unit if len({v.unit for v in candidates}) == 1 else preferred)
    )
    unknown = item.model_copy(update={"count": None, "unit": unit})
    if selected is None or selected.amount <= 0 or any(v <= 0 for v in selected.factors):
        return unknown
    if selected.total:
        amount = float(selected.value)
        return (
            item.model_copy(update={"count": amount, "unit": selected.unit})
            if math.isfinite(amount)
            else unknown
        )

    remainder = "".join(masked)
    if re.search(r"\b(?:qty|quantity)\s*[:=]?\s*\d+\.\d+", remainder, re.I):
        return unknown
    counts = [
        Decimal(next(group for group in match.groups() if group is not None))
        for match in _PURCHASE.finditer(remainder)
    ]
    # A short leading integer can be a quantity, but longer product codes cannot.
    first_line = remainder.splitlines()[0] if remainder.splitlines() else ""
    leading = _LEADING_COUNT.match(first_line)
    if leading and not re.match(r"\s*(?:qty|quantity)\b", first_line, re.I):
        if not counts and not re.search(r"\bunit\s+price\b", raw, re.I):
            # Without quantity context a leading number can belong to the name.
            return unknown
        counts.append(Decimal(leading[1]))
    if any(count <= 0 for count in counts) or len(set(counts)) > 1:
        return unknown
    if selected.factors and counts:
        # Cannot know whether a second count repeats a chain's outer purchase
        # factor or describes another packaging level. Do not silently double it.
        return unknown
    # Unlabelled trailing integers could be quantities or product codes. Avoid
    # silently defaulting to one package when this layout has unresolved evidence.
    if not counts and re.search(r"[A-Za-z].*\s\d+\s*$", remainder.splitlines()[0]):
        return unknown
    purchased = counts[0] if counts else Decimal(1)
    amount = selected.value * purchased
    value = float(amount)
    return (
        item.model_copy(update={"count": value, "unit": selected.unit})
        if math.isfinite(value)
        else unknown
    )
