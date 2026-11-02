"""Per-instance photo evidence; only public draft totals leave the app."""

import math
import re
from collections import defaultdict
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.drafts import normalize_draft, normalize_unit
from app.quantities import _restore_source_scale
from app.schemas import DraftItem, DraftResult, Storage

_PURCHASE_UNITS = {"pack", "bottle", "can", "jar", "bag", "box", "tray", "carton", "bunch", "loaf"}
_PURCHASE_ALIASES = {"net bag": "bag", "net": "bag", "packet": "pack", "bundle": "bunch"}
_OBJECT_UNITS = {"pcs", "head", "heads", "bulb", "bulbs", "root", "roots"}
_METRIC_UNITS = {"g", "kg", "ml", "l"}
_CONTENTS_LABEL = re.compile(
    r"(?:(?:net(?:\s*(?:weight|wt\.?|contents?|volume))?|contents?|weight|volume)"
    r"\s*[:=]?\s*)?"
    r"(?P<amount>[0-9]+(?:\.[0-9]+)?)\s*"
    r"(?P<unit>kilograms?|kg|grams?|g|millilit(?:er|re)s?|ml|lit(?:er|re)s?|l)\.?",
    re.IGNORECASE,
)


def uses_photo_instances(client: object) -> bool:
    """Server-owned capability; callers cannot select it in the request body."""
    return getattr(client, "photo_quantity_mode", "factors") == "instances"


def _reconcile_one_package_amount(amount: float, unit: str, label: str) -> float:
    """Repair a one-package sentinel from a whole, unambiguous contents label.

    This is a consistency check on copied text, not independent OCR. Full matching
    deliberately excludes prices, nutrition, serving sizes, multipacks, additional
    quantities and product descriptions. Other numeric amounts and units retain
    their existing handling; metric scale restoration happens separately.
    """
    if amount != 1 or unit not in _METRIC_UNITS:
        return amount
    match = _CONTENTS_LABEL.fullmatch(label.strip())
    if match is None or normalize_unit(match["unit"]) != unit:
        return amount
    contents = float(match["amount"])
    return contents if math.isfinite(contents) and contents > 0 else amount


class PhotoInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: str = Field(
        min_length=1,
        max_length=80,
        description="Short unique visible location within this food group, not a running number.",
    )
    basis: Literal["label", "object", "purchase_unit", "unknown"]
    label_text: str | None = Field(
        description="Short quantity text actually visible on this package; null otherwise."
    )
    amount: float | None = Field(
        gt=0,
        allow_inf_nan=False,
        description=(
            "Printed amount for ONE package; 1 for one loose object/purchase unit; null if unclear."
        ),
    )
    unit: str | None = Field(
        description=(
            "Original printed unit; pcs for a loose object; purchase unit if contents unreadable."
        )
    )

    @model_validator(mode="before")
    @classmethod
    def _uncertain_quantity_is_not_a_failed_food(cls, value):
        """Keep valid food evidence when a private quantity is uncertain.

        Invalid shapes still fail validation. Quantity contradictions become
        unknown instead of discarding all foods from an otherwise useful photo.
        """
        if not isinstance(value, dict):
            return value
        if (
            not cls.model_fields.keys() <= value.keys()
            or not isinstance(value.get("basis"), str)
            or value["basis"]
            not in {
                "label",
                "object",
                "purchase_unit",
                "unknown",
            }
        ):
            return value
        value = dict(value)
        amount, unit = value.get("amount"), value.get("unit")
        label = value.get("label_text")
        if unit is not None and not isinstance(unit, str):
            return value
        if label is not None and not isinstance(label, str):
            return value
        if amount is not None and not isinstance(amount, (int, float)):
            return value
        unit = normalize_unit(unit)
        unit = _PURCHASE_ALIASES.get(unit, unit)
        value["unit"] = unit
        basis = value.get("basis")
        if (
            basis == "unknown"
            or isinstance(amount, bool)
            or (amount is not None and (not math.isfinite(amount) or amount <= 0))
        ):
            value.update(basis="unknown", amount=None)
        elif basis in {"object", "purchase_unit"}:
            if amount == 1 and label is None and unit in _PURCHASE_UNITS:
                value["basis"] = "purchase_unit"
            elif basis == "object" and amount == 1 and label is None and unit in _OBJECT_UNITS:
                value["unit"] = "pcs"
            else:
                value.update(basis="unknown", amount=None)
        elif basis == "label" and (not (label or "").strip() or amount is None or unit is None):
            if label is None and amount == 1 and unit in _PURCHASE_UNITS:
                value["basis"] = "purchase_unit"
            else:
                value.update(basis="unknown", amount=None)
        return value

    @model_validator(mode="after")
    def _supported_evidence(self) -> Self:
        unit = normalize_unit(self.unit)
        if not self.position.strip():
            raise ValueError("A visible location is required")
        if self.basis == "label":
            if not (self.label_text or "").strip() or self.amount is None or unit is None:
                raise ValueError("Label evidence requires visible text, amount and unit")
            self.amount = _reconcile_one_package_amount(self.amount, unit, self.label_text)
            restored = _restore_source_scale(
                DraftItem(
                    display_name="Package",
                    raw_text=self.label_text,
                    count=self.amount,
                    unit=unit,
                    storage=None,
                    confidence=0,
                )
            )
            self.amount, self.unit = restored.count, restored.unit
        elif self.basis == "object":
            if self.amount != 1 or unit != "pcs" or self.label_text is not None:
                raise ValueError("Each unlabelled loose object is one piece, with no label")
        elif self.basis == "purchase_unit":
            if self.amount != 1 or unit not in _PURCHASE_UNITS or self.label_text is not None:
                raise ValueError("Each unmeasured package is one supported purchase unit")
        elif self.amount is not None:
            raise ValueError("Uncertain evidence must not assert an amount")
        return self


class PhotoFood(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1)
    storage: Storage | None
    confidence: float = Field(
        ge=0, le=1, description="Food identification, not quantity certainty."
    )
    instances: list[PhotoInstance] = Field(min_length=1)


class PhotoExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PhotoFood]


def resolve_photo_instances(result: PhotoExtractionResult) -> DraftResult:
    """Sum observed packages/objects, preserving units and uncertainty.

    The model supplies visual evidence; Python cannot verify an object's existence
    or read a hidden label. Duplicate locations or partly unknown group contents
    therefore yield an unknown total, never a misleading known partial sum.
    """
    groups = defaultdict(list)
    for food in result.items:
        groups[" ".join(food.display_name.casefold().split())].append(food)
    items = []
    for foods in groups.values():
        first = foods[0]
        instances = [instance for food in foods for instance in food.instances]
        units = {normalize_unit(i.unit) for i in instances} - {None}
        measured = units - _PURCHASE_UNITS
        preferred = (
            next(iter(measured))
            if len(measured) == 1
            else (next(iter(units)) if len(units) == 1 else None)
        )
        positions = [" ".join(i.position.casefold().split()) for i in instances]
        uncertain = (
            any(i.basis == "unknown" for i in instances)
            or len(positions) != len(set(positions))
            or bool(units & _PURCHASE_UNITS and measured)
        )
        common = {
            "raw_text": None,
            "display_name": first.display_name.strip(),
            "storage": first.storage if all(f.storage == first.storage for f in foods) else None,
            "confidence": min(f.confidence for f in foods),
        }
        if uncertain:
            items.append(DraftItem(**common, count=None, unit=preferred))
            continue
        totals = defaultdict(Decimal)
        for instance in instances:
            totals[normalize_unit(instance.unit)] += Decimal(str(instance.amount))
        # Different printed scales remain separate rows, rather than rescaling or
        # multiplying different package sizes as if they were identical.
        for unit, amount in totals.items():
            count = float(amount)
            items.append(
                DraftItem(**common, count=count if math.isfinite(count) else None, unit=unit)
            )
    return normalize_draft(DraftResult(items=items))
