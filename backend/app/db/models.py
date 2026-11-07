"""Every table in the database (SPEC A6). Role 2 owns this file.

One class is one table and one attribute is one column. Alembic reads this file to work out
what the migrations must create.

Role 5 writes the queries on its own tables (PlanSession, CookRecord, RecipeFeedback, Basket,
BasketMeal, BasketItem), but they are defined here so that there is one migration history.

Rules from the SPEC:
- NULL always means "unknown". Never turn NULL into 0.
- Closed vocabularies (states, sources, ...) are plain text with a CHECK constraint, which is
  easier to migrate than a native Postgres enum. The allowed values come from
  app/schemas/common.py, so the API and the database cannot drift apart.
"""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.schemas.common import (
    Cuisine,
    IngredientCategory,
    ItemSource,
    LabelDateKind,
    RemainingState,
    Storage,
)
from app.schemas.stock_events import StockEventType, StockRefType

# Predictable names for constraints and indexes, so migrations are stable and readable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def one_of(column: str, allowed: Iterable[str]) -> CheckConstraint:
    """CHECK that a text column only holds one of the allowed values (NULL is allowed)."""
    values = ", ".join(f"'{v}'" for v in allowed)
    return CheckConstraint(f"{column} IN ({values})", name=f"{column}_valid")


def _pk() -> Mapped[UUID]:
    return mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _text_array() -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))


# --------------------------------------------------------------------------- identity


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)  # the Cognito "sub"
    email: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class Household(Base):
    __tablename__ = "households"

    id: Mapped[UUID] = _pk()
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (one_of("role", ("owner", "member")),)

    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(Text, server_default="member")


class Preferences(Base):
    """One row per household. Allergens, diets and equipment are hard constraints."""

    __tablename__ = "preferences"
    __table_args__ = (
        CheckConstraint("household_size BETWEEN 1 AND 12", name="household_size_range"),
        CheckConstraint("max_difficulty BETWEEN 1 AND 3", name="max_difficulty_range"),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), primary_key=True)
    allergens: Mapped[list[str]] = _text_array()
    diets: Mapped[list[str]] = _text_array()
    equipment: Mapped[list[str]] = _text_array()
    cuisines: Mapped[list[str]] = _text_array()
    disliked_ingredient_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid), server_default=text("'{}'::uuid[]")
    )
    max_cook_minutes: Mapped[int | None] = mapped_column(Integer)
    max_difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    household_size: Mapped[int] = mapped_column(SmallInteger, server_default="2")
    last_cook_people: Mapped[int] = mapped_column(SmallInteger, server_default="2")
    last_shop_people: Mapped[int] = mapped_column(SmallInteger, server_default="2")
    last_shop_meals: Mapped[int] = mapped_column(SmallInteger, server_default="3")
    taste_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )  # Role 5 learns these; not exposed through the API
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------- catalogue


class Ingredient(Base):
    """Global and read-only at runtime. IDs come from seed/ingredients.csv, never generated."""

    __tablename__ = "ingredients"
    __table_args__ = (
        one_of("category", IngredientCategory),
        one_of("default_storage", Storage),
        Index("ix_ingredients_aliases", "aliases", postgresql_using="gin"),
    )

    id: Mapped[UUID] = _pk()
    canonical_name: Mapped[str] = mapped_column(Text, unique=True)
    aliases: Mapped[list[str]] = _text_array()
    category: Mapped[str] = mapped_column(Text)
    countable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    default_unit: Mapped[str | None] = mapped_column(Text)
    allergen_tags: Mapped[list[str]] = _text_array()
    diet_flags: Mapped[list[str]] = _text_array()
    shelf_life_days_pantry: Mapped[int | None] = mapped_column(Integer)
    shelf_life_days_fridge: Mapped[int | None] = mapped_column(Integer)
    shelf_life_days_freezer: Mapped[int | None] = mapped_column(Integer)
    default_storage: Mapped[str] = mapped_column(Text)
    is_staple: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    purchase_unit: Mapped[str | None] = mapped_column(Text)  # e.g. "pack"
    purchase_unit_size: Mapped[Decimal | None] = mapped_column(Numeric)
    purchase_unit_measure: Mapped[str | None] = mapped_column(Text)  # g, ml or pcs


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (
        one_of("cuisine", Cuisine),
        CheckConstraint("difficulty BETWEEN 1 AND 3", name="difficulty_range"),
    )

    id: Mapped[UUID] = _pk()
    title: Mapped[str] = mapped_column(Text)
    base_recipe_id: Mapped[UUID | None] = mapped_column(ForeignKey("recipes.id"))
    variant_label: Mapped[str | None] = mapped_column(Text)
    cuisine: Mapped[str] = mapped_column(Text)
    total_minutes: Mapped[int] = mapped_column(Integer)
    active_minutes: Mapped[int | None] = mapped_column(Integer)
    difficulty: Mapped[int] = mapped_column(SmallInteger)
    servings: Mapped[int] = mapped_column(SmallInteger)
    equipment: Mapped[list[str]] = _text_array()
    taste_tags: Mapped[list[str]] = _text_array()
    # Both are computed by seed.py from the ingredients (diet_flags: intersection, allergens:
    # union); recipe files do not contain them. `allergens` is not in SPEC A6 but is needed.
    diet_flags: Mapped[list[str]] = _text_array()
    allergens: Mapped[list[str]] = _text_array()
    steps: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    source: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    reviewed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"), primary_key=True)
    ingredient_id: Mapped[UUID] = mapped_column(
        ForeignKey("ingredients.id"), primary_key=True, index=True
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(Text)
    coarse_amount: Mapped[str | None] = mapped_column(Text)  # e.g. "half a cabbage"
    essential: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    prep_note: Mapped[str | None] = mapped_column(Text)


# --------------------------------------------------------------------------- inventory


class InventoryItem(Base):
    """One row is one batch of one ingredient. Rows are never merged automatically.

    Countable ingredients carry a `count`; the others carry only a `remaining_state`.
    NULL in `count`, `unit` or a date means unknown, never zero.
    """

    __tablename__ = "inventory_items"
    __table_args__ = (
        one_of("remaining_state", RemainingState),
        one_of("storage", Storage),
        one_of("source", ItemSource),
        one_of("label_date_kind", LabelDateKind),
        CheckConstraint('"count" >= 0', name="count_not_negative"),
        CheckConstraint(
            "label_date IS NULL OR label_date_kind IS NOT NULL", name="label_date_needs_kind"
        ),
        Index(
            "ix_inventory_items_household_active",
            "household_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = _pk()
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"))
    # ingredient_id is NULL for a free-text item
    ingredient_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingredients.id"))
    display_name: Mapped[str] = mapped_column(Text)
    count: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(Text)
    remaining_state: Mapped[str] = mapped_column(Text)
    storage: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    acquired_at: Mapped[date] = mapped_column(Date)
    label_date: Mapped[date | None] = mapped_column(Date)  # printed on the package
    label_date_kind: Mapped[str | None] = mapped_column(Text)
    est_use_first_date: Mapped[date | None] = mapped_column(Date)  # our estimate, a different thing
    freshness_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revision: Mapped[int] = mapped_column(Integer, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class StockEvent(Base):
    """Every inventory change. Nothing is overwritten without an event, which makes undo work."""

    __tablename__ = "stock_events"
    __table_args__ = (
        one_of("type", StockEventType),
        one_of("ref_type", StockRefType),
        # Repeating a key must change nothing: the database itself rejects the second insert.
        UniqueConstraint("household_id", "idempotency_key", name="uq_stock_events_idempotency"),
    )

    id: Mapped[UUID] = _pk()
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid)
    ref_type: Mapped[str] = mapped_column(Text, server_default="manual")
    ref_id: Mapped[UUID | None] = mapped_column(Uuid)  # points at a cook record or basket
    reverts_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_events.id"))
    reverted_by_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_events.id"))
    created_at: Mapped[datetime] = _created_at()


Index("ix_stock_events_household_created", StockEvent.household_id, StockEvent.created_at.desc())


class StockEventLine(Base):
    """One touched batch in one event, with full snapshots so that undo can restore it."""

    __tablename__ = "stock_event_lines"

    id: Mapped[UUID] = _pk()
    event_id: Mapped[UUID] = mapped_column(ForeignKey("stock_events.id"), index=True)
    inventory_item_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    # Must hold every field in CHANGEABLE_FIELDS (count, unit, remaining_state, storage,
    # label dates, display_name, freshness_confirmed_at), not only what the API shows.
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # NULL: the event created it
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # NULL: the event removed it


# --------------------------------------------------------------------------- Role 5's tables


class PlanSession(Base):
    """A Cook or Shop session. Named PlanSession to avoid a clash with SQLAlchemy's Session."""

    __tablename__ = "sessions"
    __table_args__ = (
        one_of("mode", ("cook", "shop")),
        one_of("status", ("active", "done", "abandoned")),
    )

    id: Mapped[UUID] = _pk()
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(Text)
    people: Mapped[int] = mapped_column(SmallInteger)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # NULL marks a legacy session, whose historical responses cannot be reconstructed.
    recommendation_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    adjustments: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    shown_recipe_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid), server_default=text("'{}'::uuid[]")
    )
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CookRecord(Base):
    __tablename__ = "cook_records"
    __table_args__ = (one_of("status", ("selected", "confirmed", "abandoned")),)

    id: Mapped[UUID] = _pk()
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id"))
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    people: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text, server_default="selected")
    selection_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confirmation_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    stock_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_events.id"))
    created_at: Mapped[datetime] = _created_at()


class RecipeFeedback(Base):
    """like, maybe and dislike are recorded only after cooking, against a cook record."""

    __tablename__ = "recipe_feedback"
    __table_args__ = (
        one_of(
            "signal",
            ("like", "maybe", "dislike", "cooked", "skipped", "starred", "unstarred"),
        ),
    )

    id: Mapped[UUID] = _pk()
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("sessions.id"))
    cook_record_id: Mapped[UUID | None] = mapped_column(ForeignKey("cook_records.id"))
    signal: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class Basket(Base):
    __tablename__ = "baskets"
    __table_args__ = (one_of("status", ("suggested", "confirmed", "abandoned")),)

    id: Mapped[UUID] = _pk()
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id"))
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"))
    people: Mapped[int] = mapped_column(SmallInteger)
    meals: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text, server_default="suggested")
    planning_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    stock_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_events.id"))
    created_at: Mapped[datetime] = _created_at()


class BasketMeal(Base):
    __tablename__ = "basket_meals"

    basket_id: Mapped[UUID] = mapped_column(ForeignKey("baskets.id"), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))


class BasketItem(Base):
    """Suggested and actual quantities are separate, so they can be compared later."""

    __tablename__ = "basket_items"

    id: Mapped[UUID] = _pk()
    basket_id: Mapped[UUID] = mapped_column(ForeignKey("baskets.id"), index=True)
    ingredient_id: Mapped[UUID] = mapped_column(ForeignKey("ingredients.id"))
    needed_qty: Mapped[Decimal | None] = mapped_column(Numeric)
    needed_unit: Mapped[str | None] = mapped_column(Text)
    suggested_packs: Mapped[int | None] = mapped_column(SmallInteger)
    needs_check: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    reason: Mapped[str | None] = mapped_column(Text)
    actual_bought: Mapped[bool | None] = mapped_column(Boolean)
    actual_packs: Mapped[int | None] = mapped_column(SmallInteger)


class RecommendationLearning(Base):
    """Ordered, replaceable meal evidence used to derive household taste weights."""

    __tablename__ = "recommendation_learning"

    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), primary_key=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecommendationConfirmation(Base):
    """Exact request/response replay, in the inventory event's idempotency namespace."""

    __tablename__ = "recommendation_confirmations"
    __table_args__ = (one_of("operation", ("cook", "shop")),)

    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), primary_key=True)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    operation: Mapped[str] = mapped_column(Text)
    target_id: Mapped[UUID] = mapped_column(Uuid)
    request_json: Mapped[str] = mapped_column(Text)
    response_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    stock_event_id: Mapped[UUID] = mapped_column(ForeignKey("stock_events.id"))
    created_at: Mapped[datetime] = _created_at()
