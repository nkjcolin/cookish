"""Role 5 persistence port, to be implemented against Role 2's models.

One repository is bound to ONE transaction. Mutable reads must lock the row;
learning reads must serialize household updates. Every query is tenant scoped.
No production in-memory repository or competing database schema is defined.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.auth import CurrentUser
from app.reco.learning import LearningState
from app.reco.models import Candidate, CatalogIngredient, CookSession
from app.reco.shop_models import PurchaseSpec, ShopSession
from app.schemas.cook import CookConfirmResult, CookRecord, Suggestion
from app.schemas.identity import Preferences
from app.schemas.inventory import InventoryItem
from app.schemas.shop import Basket, BasketConfirmResult, BoughtLine
from app.schemas.stock_events import InventoryChange, StockEventType, StockRefType
from app.services.stock_events import StockLine


@dataclass(frozen=True)
class RecipeCatalogue:
    recipes: tuple[Candidate, ...]
    ingredients: dict[UUID, CatalogIngredient]
    purchases: dict[UUID, PurchaseSpec]


@dataclass(frozen=True)
class CookSessionRow:
    id: UUID
    household_id: UUID
    expires_at: datetime
    state: CookSession
    history: tuple[Suggestion, ...]
    position: int
    user_id: UUID
    selected_record_id: UUID | None = None


@dataclass(frozen=True)
class CookRecordRow:
    household_id: UUID
    expires_at: datetime
    recipe_snapshot: Candidate
    response: CookRecord
    user_id: UUID


@dataclass(frozen=True)
class ShopSessionRow:
    id: UUID
    household_id: UUID
    expires_at: datetime
    state: ShopSession
    basket_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class BasketRow:
    household_id: UUID
    expires_at: datetime
    response: Basket
    # Confirmation uses the exact purchase conversion shown at planning time.
    ingredients: dict[UUID, CatalogIngredient]
    purchases: dict[UUID, PurchaseSpec]
    actual_lines: tuple[BoughtLine, ...] = ()


@dataclass(frozen=True)
class Confirmation:
    operation: str
    target_id: UUID
    request_json: str
    response: CookConfirmResult | BasketConfirmResult


class RecommendationRepository(Protocol):
    def preferences(self, household_id: UUID) -> Preferences: ...
    def inventory(self, household_id: UUID) -> list[InventoryItem]: ...
    def catalogue(self, household_id: UUID) -> RecipeCatalogue: ...
    def learning(self, household_id: UUID) -> LearningState: ...
    def save_learning(self, household_id: UUID, state: LearningState, *, user_id: UUID) -> None: ...
    def remember(
        self,
        household_id: UUID,
        *,
        cook_people: int | None = None,
        shop_people: int | None = None,
        shop_meals: int | None = None,
    ) -> None: ...

    def cook_session(self, household_id: UUID, session_id: UUID) -> CookSessionRow | None: ...
    def save_cook_session(self, household_id: UUID, row: CookSessionRow) -> None: ...
    def cook_record(self, household_id: UUID, record_id: UUID) -> CookRecordRow | None: ...
    def save_cook_record(self, household_id: UUID, row: CookRecordRow) -> None: ...
    def shop_session(self, household_id: UUID, session_id: UUID) -> ShopSessionRow | None: ...
    def save_shop_session(self, household_id: UUID, row: ShopSessionRow) -> None: ...
    def basket(self, household_id: UUID, basket_id: UUID) -> BasketRow | None: ...
    def save_basket(self, household_id: UUID, row: BasketRow) -> None: ...

    # Must reserve/lock the (household, key) before any write, including when
    # absent. Check stock_events too: this key namespace is shared with inventory.
    def confirmation(self, household_id: UUID, key: UUID) -> Confirmation | None: ...
    def save_confirmation(self, household_id: UUID, key: UUID, result: Confirmation) -> None: ...

    # The adapter delegates to Role 2 apply_stock_event using the SAME transaction.
    def apply_stock(
        self,
        user: CurrentUser,
        event_type: StockEventType,
        lines: list[StockLine],
        key: UUID,
        ref_type: StockRefType,
        ref_id: UUID,
    ) -> InventoryChange: ...
