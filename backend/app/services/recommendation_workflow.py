"""Cook/Shop orchestration ready for a transactional repository adapter.

The SQL adapter commits every save and stock event together or rolls them all back.
"""

import math
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app import clock
from app.auth import CurrentUser
from app.errors import ApiError, ErrorCode
from app.reco import (
    adjust,
    adjust_shop,
    filter_recipes,
    learn,
    new_session,
    new_shop_session,
    plan_shop,
    skip_current,
    suggest,
    taste_weights,
    to_basket,
    to_suggestion,
)
from app.reco.inventory import assess_ingredients
from app.reco.models import HardConstraints
from app.schemas.common import FreshnessStatus, ItemSource, RemainingState
from app.schemas.cook import (
    AppliedConstraints,
    ConsumptionOutcome,
    CookAdjust,
    CookConfirm,
    CookConfirmResult,
    CookFeedback,
    CookRecord,
    CookRecordStatus,
    CookSessionCreate,
    IngredientStatus,
    ProposedConsumption,
)
from app.schemas.inventory import InventoryItemCreate
from app.schemas.recipes import RecipeSummary
from app.schemas.shop import (
    BasketConfirm,
    BasketConfirmResult,
    BasketStatus,
    ShopAdjust,
    ShopSessionCreate,
)
from app.schemas.stock_events import StockEventType, StockRefType
from app.services.recommendation_repository import (
    BasketRow,
    Confirmation,
    CookRecordRow,
    CookSessionRow,
    RecommendationRepository,
    ShopSessionRow,
)
from app.services.stock_events import ChangeBatch, NewBatch

UnitOfWork = Callable[[], AbstractContextManager[RecommendationRepository]]


def _fail(code, message):
    raise ApiError(code, message)


def _owned(row, household_id):
    if row is None or row.household_id != household_id:
        _fail(ErrorCode.NOT_FOUND, "Not found")
    return row


def _active(row, now):
    if now >= row.expires_at:
        _fail(ErrorCode.NOT_FOUND, "Session expired")
    return row


def _unique(values):
    if len(values) != len(set(values)):
        _fail(ErrorCode.VALIDATION, "Duplicate confirmation lines")


class RecommendationWorkflow:
    def __init__(
        self, unit_of_work: UnitOfWork, *, now=clock.now, new_id: Callable[[], UUID] = uuid4
    ):
        self.unit_of_work, self.now, self.new_id = unit_of_work, now, new_id

    def _now(self) -> datetime:
        value = self.now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("workflow clock must be timezone-aware")
        return value

    @staticmethod
    def _weights(repo, household_id):
        state = repo.learning(household_id)
        if state.household_id != household_id:
            _fail(ErrorCode.NOT_FOUND, "Learning state not found")
        return taste_weights(state)

    def _suggest(self, repo, user, row, *, persist_no_result=False):
        # The unit of work has acquired the household lock. Use this time so a
        # confirmation committed while we waited is not mistaken for a future meal.
        now = self._now()
        household = user.household_id
        # Refresh on every ranking: another household member may have cooked,
        # undone a meal, or crossed the history window since this session began.
        row = replace(
            row,
            state=replace(
                row.state, recent_recipe_ids=repo.recent_recipe_ids(household, as_of=now)
            ),
        )
        catalogue = repo.catalogue(household)
        result = suggest(
            catalogue.recipes,
            repo.inventory(household),
            repo.preferences(household),
            row.state,
            catalogue.ingredients,
            as_of=now,
            taste_weights=self._weights(repo, household),
        )
        if result.selected is None:
            error = ApiError(
                ErrorCode.NO_RESULT,
                "Nothing fits all of that",
                {"relaxable": list(result.relaxable)},
            )
            if not persist_no_result:
                raise error
            # A valid restriction/skip remains applied even when nothing fits.
            # The caller raises NO_RESULT only after this transaction commits.
            repo.save_cook_session(household, row)
            repo.remember(household, cook_people=row.state.people)
            return error
        response = to_suggestion(result, row.id)
        # Previous moves the cursor; a new request appends, retaining the audit history.
        response.has_previous = bool(row.history)
        saved = replace(
            row,
            state=result.session,
            history=(*row.history, response),
            position=len(row.history),
        )
        repo.save_cook_session(household, saved)
        repo.remember(household, cook_people=saved.state.people)
        return response

    def start_cook(self, user: CurrentUser, body: CookSessionCreate):
        now = self._now()
        with self.unit_of_work() as repo:
            row = CookSessionRow(
                self.new_id(),
                user.household_id,
                now + timedelta(hours=12),
                new_session(repo.preferences(user.household_id), body.people),
                (),
                -1,
                user.user_id,
            )
            return self._suggest(repo, user, row)

    def _cook_session(self, repo, user, session_id, now, *, allow_selected=False):
        row = _active(
            _owned(repo.cook_session(user.household_id, session_id), user.household_id), now
        )
        if row.selected_record_id is not None and not allow_selected:
            _fail(ErrorCode.CONFLICT, "This session already has a selected meal")
        return row

    def adjust_cook(self, user: CurrentUser, session_id: UUID, body: CookAdjust):
        now = self._now()
        with self.unit_of_work() as repo:
            row = self._cook_session(repo, user, session_id, now)
            candidate = next(
                (
                    meal
                    for meal in repo.catalogue(user.household_id).recipes
                    if meal.id == row.state.current_recipe_id
                ),
                None,
            )
            if candidate is None:
                _fail(ErrorCode.NOT_FOUND, "Recipe not found")
            result = self._suggest(
                repo,
                user,
                replace(row, state=adjust(row.state, body, candidate)),
                persist_no_result=True,
            )
        if isinstance(result, ApiError):
            raise result
        return result

    def next_cook(self, user: CurrentUser, session_id: UUID):
        now = self._now()
        with self.unit_of_work() as repo:
            row = self._cook_session(repo, user, session_id, now)
            result = self._suggest(
                repo,
                user,
                replace(row, state=skip_current(row.state)),
                persist_no_result=True,
            )
        if isinstance(result, ApiError):
            raise result
        return result

    def previous_cook(self, user: CurrentUser, session_id: UUID):
        now = self._now()
        with self.unit_of_work() as repo:
            row = self._cook_session(repo, user, session_id, now)
            if row.position <= 0:
                _fail(ErrorCode.CONFLICT, "No previous suggestion")
            position = row.position - 1
            response = row.history[position].model_copy(
                deep=True,
                update={
                    "has_previous": position > 0,
                    "applied_constraints": AppliedConstraints(
                        tags=list(row.state.tags),
                        max_minutes=row.state.max_minutes,
                        max_difficulty=row.state.max_difficulty,
                    ),
                },
            )
            catalogue = repo.catalogue(user.household_id)
            candidate = next(
                (meal for meal in catalogue.recipes if meal.id == response.recipe.id), None
            )
            if candidate is None:
                _fail(ErrorCode.NOT_FOUND, "Recipe not found")
            hard = HardConstraints.from_preferences(
                repo.preferences(user.household_id), row.state.strict_max_minutes
            )
            if not filter_recipes([candidate], hard, catalogue.ingredients) or any(
                (meta := catalogue.ingredients.get(line.ingredient_id)) is None
                or bool(meta.allergens & hard.allergens)
                or not hard.diets <= meta.diet_flags
                for line in response.ingredients
            ):
                _fail(
                    ErrorCode.CONFLICT, "Previous suggestion no longer meets household constraints"
                )
            repo.save_cook_session(
                user.household_id,
                replace(
                    row,
                    position=position,
                    state=replace(
                        row.state,
                        people=response.people,
                        current_recipe_id=response.recipe.id,
                        anchor_recipe_id=None,
                    ),
                ),
            )
            repo.remember(user.household_id, cook_people=response.people)
            return response

    def select_cook(self, user: CurrentUser, session_id: UUID) -> CookRecord:
        now = self._now()
        with self.unit_of_work() as repo:
            household = user.household_id
            row = self._cook_session(repo, user, session_id, now, allow_selected=True)
            if row.selected_record_id is not None:
                return _owned(
                    repo.cook_record(household, row.selected_record_id), household
                ).response
            catalogue, prefs = repo.catalogue(household), repo.preferences(household)
            candidate = next(
                (meal for meal in catalogue.recipes if meal.id == row.state.current_recipe_id), None
            )
            if candidate is None:
                _fail(ErrorCode.NOT_FOUND, "Recipe not found")
            if not filter_recipes(
                [candidate],
                HardConstraints.from_preferences(prefs, row.state.strict_max_minutes),
                catalogue.ingredients,
            ):
                _fail(ErrorCode.CONFLICT, "Recipe no longer meets household constraints")
            # Browsing history does not undo accumulated restrictions. Recheck them.
            state = row.state
            if (
                (state.max_minutes is not None and candidate.total_minutes > state.max_minutes)
                or (
                    state.max_difficulty is not None and candidate.difficulty > state.max_difficulty
                )
                or not state.required_tags <= set(candidate.taste_tags)
            ):
                _fail(ErrorCode.CONFLICT, "Previous suggestion does not meet current adjustments")
            # Use the portions displayed in that history entry.
            people = row.history[row.position].people
            assessments = assess_ingredients(
                candidate, repo.inventory(household), catalogue.ingredients, people, as_of=now
            )
            proposals = []
            for ingredient in assessments:
                meta = catalogue.ingredients[ingredient.ingredient_id]
                if ingredient.essential and (
                    ingredient.status
                    in {IngredientStatus.UNKNOWN, IngredientStatus.CHECK, IngredientStatus.MISSING}
                    or (meta.countable and ingredient.status == IngredientStatus.LOW)
                ):
                    _fail(
                        ErrorCode.CONFLICT,
                        "Check or replenish essential ingredients before cooking",
                    )
                remaining = ingredient.quantity
                for batch in ingredient.usable_batches:
                    if meta.countable:
                        if remaining is None or remaining <= 0:
                            break
                        used = min(batch.count, remaining)
                        if used > 0:
                            proposals.append(
                                ProposedConsumption(
                                    item=batch.model_copy(deep=True),
                                    proposed_count=batch.count - used,
                                    proposed_outcome=None,
                                )
                            )
                        remaining -= used
                    else:
                        proposals.append(
                            ProposedConsumption(
                                item=batch.model_copy(deep=True),
                                proposed_count=None,
                                proposed_outcome=ConsumptionOutcome.RUNNING_LOW,
                            )
                        )
                        break
            response = CookRecord(
                id=self.new_id(),
                session_id=row.id,
                recipe=RecipeSummary.model_validate(candidate.model_dump()),
                people=people,
                status=CookRecordStatus.SELECTED,
                rating=None,
                proposed_consumption=proposals,
            )
            repo.save_cook_record(
                household,
                CookRecordRow(
                    household,
                    row.expires_at,
                    candidate.model_copy(deep=True),
                    response,
                    user.user_id,
                ),
            )
            repo.save_cook_session(household, replace(row, selected_record_id=response.id))
            return response

    @staticmethod
    def _replay(repo, user, key, operation, target_id, body):
        saved = repo.confirmation(user.household_id, key)
        if saved is None:
            return None
        if (saved.operation, saved.target_id, saved.request_json) != (
            operation,
            target_id,
            body.model_dump_json(),
        ):
            _fail(ErrorCode.CONFLICT, "Idempotency key was used for a different request")
        return saved.response

    @staticmethod
    def _save_confirmation(repo, user, key, operation, target_id, body, response):
        repo.save_confirmation(
            user.household_id,
            key,
            Confirmation(operation, target_id, body.model_dump_json(), response),
        )

    def confirm_cook(
        self, user: CurrentUser, record_id: UUID, body: CookConfirm, key: UUID
    ) -> CookConfirmResult:
        now = self._now()
        with self.unit_of_work() as repo:
            household = user.household_id
            replay = self._replay(repo, user, key, "cook", record_id, body)
            if replay is not None:
                return replay
            row = _active(_owned(repo.cook_record(household, record_id), household), now)
            if row.response.status != CookRecordStatus.SELECTED:
                _fail(ErrorCode.CONFLICT, "Meal has already been confirmed or abandoned")
            catalogue = repo.catalogue(household)
            if not filter_recipes(
                [row.recipe_snapshot],
                HardConstraints.from_preferences(repo.preferences(household)),
                catalogue.ingredients,
            ):
                _fail(ErrorCode.CONFLICT, "Recipe no longer meets household constraints")
            ids = [line.inventory_item_id for line in body.lines]
            _unique(ids)
            proposed = {line.item.id: line.item for line in row.response.proposed_consumption}
            if set(ids) != set(proposed):
                _fail(
                    ErrorCode.VALIDATION,
                    "Confirm exactly the proposed batches, or mark them not used",
                )
            inventory = {item.id: item for item in repo.inventory(household)}
            changes = []
            for line in body.lines:
                batch = inventory.get(line.inventory_item_id)
                if batch is None:
                    _fail(ErrorCode.NOT_FOUND, "Inventory batch not found")
                if batch.revision != line.revision:
                    _fail(ErrorCode.STALE_REVISION, "Stock changed; refresh before confirming")
                if line.outcome == ConsumptionOutcome.NOT_USED:
                    continue
                original = proposed[batch.id]
                if (
                    batch.ingredient_id != original.ingredient_id
                    or batch.countable != original.countable
                    or batch.unit != original.unit
                ):
                    _fail(
                        ErrorCode.CONFLICT,
                        "Batch identity or units changed; start a fresh selection",
                    )
                if batch.freshness_status in {FreshnessStatus.CHECK, FreshnessStatus.EXPIRED}:
                    _fail(ErrorCode.CONFLICT, "Check freshness before consuming this batch")
                if batch.countable:
                    if (
                        line.new_count is None
                        or not math.isfinite(line.new_count)
                        or batch.count is None
                        or not math.isfinite(batch.count)
                        or line.new_count > batch.count
                    ):
                        _fail(
                            ErrorCode.VALIDATION,
                            "Consumption needs a finite count no higher than current stock",
                        )
                    values = {
                        "count": line.new_count,
                        "remaining_state": RemainingState.OUT
                        if line.new_count == 0
                        else RemainingState.ENOUGH,
                    }
                else:
                    outcomes = {
                        ConsumptionOutcome.STILL_ENOUGH: RemainingState.ENOUGH,
                        ConsumptionOutcome.RUNNING_LOW: RemainingState.LOW,
                        ConsumptionOutcome.USED_UP: RemainingState.OUT,
                    }
                    if line.outcome not in outcomes:
                        _fail(
                            ErrorCode.VALIDATION, "State-tracked stock needs a consumption outcome"
                        )
                    values = {"remaining_state": outcomes[line.outcome]}
                changes.append(ChangeBatch(batch.id, line.revision, values))
            change = repo.apply_stock(
                user, StockEventType.CONSUME, changes, key, StockRefType.COOK_SESSION, record_id
            )
            confirmed = row.response.model_copy(
                update={"status": CookRecordStatus.CONFIRMED, "proposed_consumption": []}
            )
            repo.save_cook_record(household, replace(row, response=confirmed))
            state = learn(
                repo.learning(household),
                household_id=household,
                record_id=record_id,
                recipe=row.recipe_snapshot,
                status=CookRecordStatus.CONFIRMED,
            )
            repo.save_learning(household, state, user_id=user.user_id)
            response = CookConfirmResult(**change.model_dump(), cook_record_id=record_id)
            self._save_confirmation(repo, user, key, "cook", record_id, body, response)
            return response

    def feedback(self, user: CurrentUser, record_id: UUID, body: CookFeedback) -> CookRecord:
        with self.unit_of_work() as repo:
            household = user.household_id
            row = _owned(repo.cook_record(household, record_id), household)
            if row.response.status != CookRecordStatus.CONFIRMED:
                _fail(ErrorCode.CONFLICT, "Only a confirmed meal can be rated")
            state = learn(
                repo.learning(household),
                household_id=household,
                record_id=record_id,
                recipe=row.recipe_snapshot,
                status=row.response.status,
                rating=body.rating,
            )
            repo.save_learning(household, state, user_id=user.user_id)
            response = row.response.model_copy(update={"rating": body.rating})
            repo.save_cook_record(household, replace(row, response=response))
            return response

    def _basket(self, repo, user, row, now):
        household = user.household_id
        catalogue = repo.catalogue(household)
        plan = plan_shop(
            catalogue.recipes,
            repo.inventory(household),
            repo.preferences(household),
            row.state,
            catalogue.ingredients,
            catalogue.purchases,
            as_of=now,
            taste_weights=self._weights(repo, household),
        )
        if not plan.planned_meals:
            raise ApiError(ErrorCode.NO_RESULT, "No eligible recipes", {"relaxable": []})
        response = to_basket(plan, row.id, row.basket_id)
        # Insert the parent before its basket; both remain in the same transaction.
        repo.save_shop_session(household, row)
        repo.save_basket(
            household,
            BasketRow(
                household,
                row.expires_at,
                response,
                dict(catalogue.ingredients),
                dict(catalogue.purchases),
            ),
        )
        repo.remember(household, shop_people=row.state.people, shop_meals=row.state.meals)
        return response

    def start_shop(self, user: CurrentUser, body: ShopSessionCreate):
        now = self._now()
        with self.unit_of_work() as repo:
            row = ShopSessionRow(
                self.new_id(),
                user.household_id,
                now + timedelta(hours=12),
                new_shop_session(repo.preferences(user.household_id), body.people, body.meals),
                self.new_id(),
                user.user_id,
            )
            return self._basket(repo, user, row, now)

    def adjust_shop(self, user: CurrentUser, session_id: UUID, body: ShopAdjust):
        now = self._now()
        with self.unit_of_work() as repo:
            household = user.household_id
            row = _active(_owned(repo.shop_session(household, session_id), household), now)
            old = _owned(repo.basket(household, row.basket_id), household)
            if old.response.status != BasketStatus.SUGGESTED:
                _fail(ErrorCode.CONFLICT, "Basket is no longer editable")
            result = self._basket(
                repo,
                user,
                replace(row, state=adjust_shop(row.state, body), basket_id=self.new_id()),
                now,
            )
            repo.save_basket(
                household,
                replace(
                    old, response=old.response.model_copy(update={"status": BasketStatus.ABANDONED})
                ),
            )
            return result

    def confirm_shop(
        self, user: CurrentUser, basket_id: UUID, body: BasketConfirm, key: UUID
    ) -> BasketConfirmResult:
        now = self._now()
        with self.unit_of_work() as repo:
            household = user.household_id
            replay = self._replay(repo, user, key, "shop", basket_id, body)
            if replay is not None:
                return replay
            row = _active(_owned(repo.basket(household, basket_id), household), now)
            basket = row.response
            if basket.status != BasketStatus.SUGGESTED:
                _fail(ErrorCode.CONFLICT, "Basket is no longer confirmable")
            # Adjust locks session then basket and atomically abandons the old
            # basket. Confirm only locks the basket, avoiding inverse lock order.
            ids = [line.basket_item_id for line in body.lines]
            _unique(ids)
            items = {item.id: item for item in basket.items}
            if set(ids) != set(items):
                _fail(ErrorCode.VALIDATION, "Confirm every basket line as bought or not bought")
            changes = []
            actual_lines = []
            for line in body.lines:
                if not line.bought:
                    actual_lines.append(line.model_copy(deep=True, update={"packs": None}))
                    continue
                item = items[line.basket_item_id]
                meta, pack = row.ingredients[item.ingredient_id], row.purchases[item.ingredient_id]
                if not pack.buyable:
                    _fail(ErrorCode.VALIDATION, "Ingredient is not a purchasable item")
                count, unit, packs = None, None, None
                if meta.countable:
                    packs = line.packs if line.packs is not None else item.suggested_packs
                    # No count suggested or given: bought, amount unknown, as a receipt line
                    # without a quantity. The kitchen asks for the count when it matters.
                    if packs is not None:
                        if pack.purchase_unit_size is None or pack.purchase_unit_measure is None:
                            _fail(ErrorCode.VALIDATION, "Resolve purchase units before confirming")
                        if not 1 <= packs <= 50:
                            _fail(ErrorCode.VALIDATION, "Enter the actual pack count")
                        count, unit = packs * pack.purchase_unit_size, pack.purchase_unit_measure
                        if not math.isfinite(count):
                            _fail(ErrorCode.VALIDATION, "Purchase quantity must be finite")
                elif line.packs is not None:
                    _fail(ErrorCode.VALIDATION, "State-tracked purchases do not take numeric packs")
                actual_lines.append(line.model_copy(deep=True, update={"packs": packs}))
                changes.append(
                    NewBatch(
                        InventoryItemCreate(
                            ingredient_id=item.ingredient_id,
                            count=count,
                            unit=unit,
                            remaining_state=RemainingState.ENOUGH,
                            acquired_at=now.astimezone(clock.SINGAPORE).date(),
                        ),
                        ItemSource.SHOP_CONFIRM,
                    )
                )
            change = repo.apply_stock(
                user, StockEventType.PURCHASE, changes, key, StockRefType.BASKET, basket_id
            )
            repo.save_basket(
                household,
                replace(
                    row,
                    response=basket.model_copy(update={"status": BasketStatus.CONFIRMED}),
                    actual_lines=tuple(actual_lines),
                ),
            )
            response = BasketConfirmResult(**change.model_dump(), basket_id=basket_id)
            self._save_confirmation(repo, user, key, "shop", basket_id, body, response)
            return response
