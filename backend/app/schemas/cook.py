"""Cook: one suggestion at a time, then confirm what was used, then rate the dish."""

from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import RequestModel, ResponseModel
from app.schemas.identity import Difficulty, People
from app.schemas.inventory import Count, InventoryItem
from app.schemas.recipes import RecipeSummary
from app.schemas.stock_events import InventoryChange


class CookTag(StrEnum):
    QUICKER = "quicker"
    EASIER = "easier"
    LESS_OIL = "less_oil"
    MORE_PROTEIN = "more_protein"
    MORE_VEGETABLES = "more_vegetables"


class IngredientStatus(StrEnum):
    HAVE = "have"
    LOW = "low"
    MISSING = "missing"
    UNKNOWN = "unknown"
    CHECK = "check"
    STAPLE = "staple"


class FreshnessReason(StrEnum):
    PAST_USE_BY = "past_use_by"
    PAST_BEST_BEFORE = "past_best_before"
    PAST_ESTIMATE = "past_estimate"
    NO_DATE = "no_date"


class Rating(StrEnum):
    LIKE = "like"
    MAYBE = "maybe"
    DISLIKE = "dislike"


class CookRecordStatus(StrEnum):
    SELECTED = "selected"
    CONFIRMED = "confirmed"
    ABANDONED = "abandoned"


class ConsumptionOutcome(StrEnum):
    STILL_ENOUGH = "still_enough"
    RUNNING_LOW = "running_low"
    USED_UP = "used_up"
    NOT_USED = "not_used"


class CookSessionConstraints(RequestModel):
    """Absolute soft limits for a restart, not a list of commands to run again."""

    tags: list[CookTag] = Field(
        default_factory=list,
        description="Already applied tags. Quicker/easier label the supplied absolute limits;"
        " they do not reduce those limits again.",
    )
    max_minutes: Annotated[int, Field(ge=0, le=240)] | None = Field(
        default=None, description="Absolute time limit; null removes the soft time limit."
    )
    max_difficulty: Annotated[int, Field(ge=0, le=3)] | None = Field(
        default=None, description="Absolute difficulty limit; null removes the soft limit."
    )


class CookSessionCreate(RequestModel):
    people: People | None = Field(default=None, description="Defaults to the last choice.")
    previous_session_id: UUID | None = Field(
        default=None,
        description="Carry skipped recipes and any strict time bound from this household's"
        " previous session. Does not restore history or a selected meal.",
    )
    skip_previous_recipe: bool = Field(
        default_factory=lambda: False,
        description="When recovering a Not tonight request, also skip the previous session's"
        " current recipe. Requires previous_session_id.",
    )
    constraints: CookSessionConstraints | None = Field(
        default=None,
        description="Restore explicit soft constraints in one ranking. Omit to start from"
        " household preferences. Household safety constraints are always applied.",
    )

    @model_validator(mode="after")
    def _skip_has_previous_session(self) -> Self:
        if self.skip_previous_recipe and self.previous_session_id is None:
            raise ValueError("skip_previous_recipe requires previous_session_id")
        return self


class CookAdjust(RequestModel):
    """Adjustments accumulate over the session; send only what the user just changed."""

    tags: list[CookTag] = Field(default_factory=list)
    people: People | None = None
    max_minutes: Annotated[int, Field(ge=5, le=240)] | None = None
    max_difficulty: Difficulty | None = None

    @model_validator(mode="after")
    def _changes_something(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("an adjustment must change at least one field")
        return self


class AppliedConstraints(ResponseModel):
    tags: list[CookTag]
    max_minutes: int | None
    max_difficulty: int | None


class SuggestionIngredient(ResponseModel):
    ingredient_id: UUID
    name: str
    amount: str = Field(description="Display text, already scaled to `people`.")
    essential: bool
    status: IngredientStatus
    countable: bool | None = Field(
        default=None,
        description="Whether stock is counted. Null only for older saved suggestions.",
    )


class StockCheck(ResponseModel):
    """An essential ingredient whose stock is unknown: ask "do you still have this?".

    `item` is the batch to use first; the answer updates it through
    PATCH /inventory/items/{id}, setting `remaining_state`.
    """

    item: InventoryItem


class FreshnessCheck(ResponseModel):
    """A batch to inspect before cooking. Answer through PATCH /inventory/items/{id}."""

    item: InventoryItem
    reason: FreshnessReason


class Suggestion(ResponseModel):
    session_id: UUID
    recipe: RecipeSummary
    people: int
    ingredients: list[SuggestionIngredient]
    needs_check: list[StockCheck]
    freshness_check: list[FreshnessCheck]
    has_previous: bool
    applied_constraints: AppliedConstraints
    available_nudges: list[CookTag] = Field(
        default_factory=list,
        description="Nudges that currently return a different recipe meeting the requested change."
        " Recomputed from the catalogue, stock and accumulated session constraints.",
    )


class ProposedConsumption(ResponseModel):
    """What the service thinks was used from one batch; the user corrects it."""

    item: InventoryItem
    proposed_count: float | None = Field(description="For countable items: count afterwards.")
    proposed_outcome: ConsumptionOutcome | None = Field(description="For state-tracked items.")


class CookRecord(ResponseModel):
    id: UUID
    session_id: UUID
    recipe: RecipeSummary
    people: int
    status: CookRecordStatus
    rating: Rating | None
    proposed_consumption: list[ProposedConsumption]


class ConsumptionLine(RequestModel):
    inventory_item_id: UUID
    revision: int
    new_count: Count | None = None
    outcome: ConsumptionOutcome | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.new_count is None) == (self.outcome is None):
            raise ValueError("send exactly one of new_count or outcome")
        return self


class CookConfirm(RequestModel):
    lines: list[ConsumptionLine]


class CookConfirmResult(InventoryChange):
    cook_record_id: UUID


class CookFeedback(RequestModel):
    rating: Rating


class NoResultDetails(ResponseModel):
    """`details` of a NO_RESULT error from Cook or Shop. Hard constraints never appear."""

    relaxable: list[str] = Field(description='Soft conditions, e.g. "max_minutes", "tags".')


class UseFirstItem(ResponseModel):
    item: InventoryItem
    days_left: int | None


class UseFirstList(ResponseModel):
    items: list[UseFirstItem]
