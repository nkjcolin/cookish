"""Household-scoped recommendation persistence, bound to one SQL transaction.

The household lock serializes workflow mutations, including absent session/replay
rows. NO KEY UPDATE permits inventory inserts to reference the household while
the stock-event unique key still arbitrates races with manual inventory writes.
"""

from contextlib import contextmanager
from dataclasses import replace

from sqlalchemy import event, select, update

from app import clock
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.reco.learning import LearningState, taste_weights
from app.schemas.cook import CookRecordStatus
from app.schemas.shop import BasketStatus
from app.services import stock_events
from app.services.recommendation_inputs import SqlRecommendationInputs
from app.services.recommendation_repository import (
    BasketRow,
    Confirmation,
    CookRecordRow,
    CookSessionRow,
    ShopSessionRow,
)
from app.services.recommendation_snapshots import dump_snapshot, load_snapshot
from app.services.recommendation_workflow import RecommendationWorkflow


def _conflict(message="Saved recommendation is unavailable; start a new session"):
    raise ApiError(ErrorCode.CONFLICT, message)


class SqlRecommendationRepository:
    def __init__(self, session, user):
        self.session, self.user = session, user
        household = session.scalar(
            select(m.Household)
            .join(m.HouseholdMember, m.HouseholdMember.household_id == m.Household.id)
            .where(
                m.Household.id == user.household_id,
                m.HouseholdMember.user_id == user.user_id,
            )
            .with_for_update(of=m.Household, key_share=True)
        )
        if household is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Household not found")
        self.inputs = SqlRecommendationInputs(session)

    def _household(self, household_id):
        if household_id != self.user.household_id:
            raise ApiError(ErrorCode.NOT_FOUND, "Not found")

    def _row(self, model, household_id, identity):
        self._household(household_id)
        return self.session.scalar(
            select(model)
            .where(model.id == identity, model.household_id == household_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def _load(snapshot, kind, household_id=None):
        try:
            row = load_snapshot(snapshot, kind)
        except (ValueError, TypeError, KeyError) as error:
            raise ApiError(
                ErrorCode.CONFLICT, "Saved recommendation is unavailable; start a new session"
            ) from error
        if household_id is not None and row.household_id != household_id:
            _conflict()
        return row

    def preferences(self, household_id):
        self._household(household_id)
        return self.inputs.preferences(household_id)

    def inventory(self, household_id):
        self._household(household_id)
        return self.inputs.inventory(household_id)

    def catalogue(self, household_id):
        self._household(household_id)
        return self.inputs.catalogue(household_id)

    def remember(self, household_id, *, cook_people=None, shop_people=None, shop_meals=None):
        self._household(household_id)
        values = {
            field: value
            for field, value in (
                ("last_cook_people", cook_people),
                ("last_shop_people", shop_people),
                ("last_shop_meals", shop_meals),
            )
            if value is not None
        }
        if values:
            self.session.execute(
                update(m.Preferences)
                .where(m.Preferences.household_id == household_id)
                .values(**values, updated_at=clock.now())
            )

    def learning(self, household_id):
        self._household(household_id)
        stored = self.session.get(m.RecommendationLearning, household_id)
        if stored is None:
            preferences = self.session.get(m.Preferences, household_id)
            if preferences is not None and preferences.taste_weights:
                _conflict("Existing taste weights need migration before recommendations can learn")
            return LearningState(household_id)
        return self._load(stored.state, LearningState, household_id)

    def save_learning(self, household_id, state, *, user_id):
        self._household(household_id)
        if state.household_id != household_id or user_id != self.user.user_id:
            _conflict()
        previous = self.learning(household_id)
        if previous == state:
            return
        old = {meal.record_id: meal for meal in previous.meals}
        for meal in state.meals:
            before = old.get(meal.record_id)
            if before == meal:
                continue
            record = self._row(m.CookRecord, household_id, meal.record_id)
            if record is None or record.status != "confirmed" or record.recipe_id != meal.recipe_id:
                _conflict("Only a confirmed household meal can update preferences")
            signals = (["cooked"] if before is None else []) + (
                [meal.rating.value] if meal.rating is not None else []
            )
            for signal in signals:
                self.session.add(
                    m.RecipeFeedback(
                        household_id=household_id,
                        user_id=user_id,
                        recipe_id=meal.recipe_id,
                        session_id=record.session_id,
                        cook_record_id=meal.record_id,
                        signal=signal,
                        created_at=clock.now(),
                    )
                )
        stored = self.session.get(m.RecommendationLearning, household_id)
        if stored is None:
            stored = m.RecommendationLearning(household_id=household_id)
            self.session.add(stored)
        stored.state = dump_snapshot(state)
        stored.updated_by, stored.updated_at = user_id, clock.now()
        self.session.execute(
            update(m.Preferences)
            .where(m.Preferences.household_id == household_id)
            .values(taste_weights=taste_weights(state), updated_at=clock.now())
        )
        self.session.flush()

    def _session_row(self, household_id, session_id, mode):
        row = self._row(m.PlanSession, household_id, session_id)
        return row if row is not None and row.mode == mode else None

    def cook_session(self, household_id, session_id):
        stored = self._session_row(household_id, session_id, "cook")
        if stored is None:
            return None
        row = self._load(stored.recommendation_state, CookSessionRow, household_id)
        if (row.id, row.user_id, row.state.people, row.position) != (
            stored.id,
            stored.user_id,
            stored.people,
            stored.position,
        ):
            _conflict()
        return replace(row, expires_at=stored.expires_at)

    def save_cook_session(self, household_id, row):
        self._household(household_id)
        if row.household_id != household_id:
            _conflict()
        stored = self._row(m.PlanSession, household_id, row.id)
        skipped = frozenset()
        if stored is None:
            stored = m.PlanSession(
                id=row.id,
                household_id=household_id,
                user_id=row.user_id,
                mode="cook",
                status="active",
            )
            self.session.add(stored)
        else:
            if stored.mode != "cook" or stored.user_id != row.user_id:
                _conflict()
            previous = self._load(stored.recommendation_state, CookSessionRow, household_id)
            skipped = previous.state.skipped_recipe_ids
        stored.people, stored.expires_at, stored.position = (
            row.state.people,
            row.expires_at,
            row.position,
        )
        stored.constraints = {
            "max_minutes": row.state.max_minutes,
            "max_difficulty": row.state.max_difficulty,
            "strict_max_minutes": row.state.strict_max_minutes,
            "required_tags": sorted(tag.value for tag in row.state.required_tags),
            "boosted_tags": sorted(tag.value for tag in row.state.boosted_tags),
        }
        stored.adjustments = [tag.value for tag in row.state.tags]
        stored.shown_recipe_ids = list(row.state.shown_recipe_ids)
        stored.recommendation_state = dump_snapshot(row)
        self.session.flush()
        for recipe_id in row.state.skipped_recipe_ids - skipped:
            self.session.add(
                m.RecipeFeedback(
                    household_id=household_id,
                    user_id=self.user.user_id,
                    recipe_id=recipe_id,
                    session_id=row.id,
                    signal="skipped",
                    created_at=clock.now(),
                )
            )

    def cook_record(self, household_id, record_id):
        stored = self._row(m.CookRecord, household_id, record_id)
        if stored is None:
            return None
        snapshot = (
            stored.selection_snapshot
            if stored.status == "selected"
            else stored.confirmation_snapshot
        )
        row = self._load(snapshot, CookRecordRow, household_id)
        if (
            row.response.id,
            row.response.session_id,
            row.recipe_snapshot.id,
            row.response.recipe.id,
            row.response.people,
            row.response.status.value,
            row.user_id,
        ) != (
            stored.id,
            stored.session_id,
            stored.recipe_id,
            stored.recipe_id,
            stored.people,
            stored.status,
            stored.user_id,
        ):
            _conflict()
        parent = self._session_row(household_id, stored.session_id, "cook")
        if parent is None:
            _conflict()
        return replace(row, expires_at=parent.expires_at)

    def save_cook_record(self, household_id, row):
        self._household(household_id)
        if row.household_id != household_id:
            _conflict()
        response = row.response
        parent = self._session_row(household_id, response.session_id, "cook")
        if parent is None:
            _conflict()
        stored = self._row(m.CookRecord, household_id, response.id)
        if stored is None:
            if response.status != CookRecordStatus.SELECTED:
                _conflict()
            stored = m.CookRecord(
                id=response.id,
                session_id=response.session_id,
                recipe_id=row.recipe_snapshot.id,
                household_id=household_id,
                user_id=row.user_id,
                people=response.people,
                status=response.status.value,
                selection_snapshot=dump_snapshot(row),
            )
            self.session.add(stored)
        else:
            original = self._load(stored.selection_snapshot, CookRecordRow, household_id)
            if row.recipe_snapshot != original.recipe_snapshot or (
                response.session_id,
                response.recipe,
                response.people,
                row.user_id,
            ) != (
                original.response.session_id,
                original.response.recipe,
                original.response.people,
                original.user_id,
            ):
                _conflict()
            if response.status == CookRecordStatus.SELECTED:
                if row != original:
                    _conflict()
            else:
                stored.confirmation_snapshot = dump_snapshot(row)
                stored.status = response.status.value
                if response.status == CookRecordStatus.CONFIRMED:
                    parent.status = "done"
        self.session.flush()

    def shop_session(self, household_id, session_id):
        stored = self._session_row(household_id, session_id, "shop")
        if stored is None:
            return None
        row = self._load(stored.recommendation_state, ShopSessionRow, household_id)
        if (row.id, row.user_id, row.state.people) != (stored.id, stored.user_id, stored.people):
            _conflict()
        return replace(row, expires_at=stored.expires_at)

    def save_shop_session(self, household_id, row):
        self._household(household_id)
        if row.household_id != household_id:
            _conflict()
        stored = self._row(m.PlanSession, household_id, row.id)
        if stored is None:
            stored = m.PlanSession(
                id=row.id,
                household_id=household_id,
                user_id=row.user_id,
                mode="shop",
                status="active",
            )
            self.session.add(stored)
        elif stored.mode != "shop" or stored.user_id != row.user_id:
            _conflict()
        stored.people, stored.expires_at = row.state.people, row.expires_at
        stored.constraints = {
            "meals": row.state.meals,
            "strict_max_minutes": row.state.strict_max_minutes,
        }
        stored.adjustments = [tag.value for tag in row.state.tags]
        stored.recommendation_state = dump_snapshot(row)
        self.session.flush()

    def basket(self, household_id, basket_id):
        stored = self._row(m.Basket, household_id, basket_id)
        if stored is None:
            return None
        original = self._load(stored.planning_snapshot, BasketRow, household_id)
        if (
            original.response.id,
            original.response.session_id,
            original.response.people,
            original.response.meals,
        ) != (stored.id, stored.session_id, stored.people, stored.meals):
            _conflict()
        parent = self._session_row(household_id, stored.session_id, "shop")
        if parent is None:
            _conflict()
        from app.schemas.shop import BoughtLine

        actual = tuple(
            BoughtLine(basket_item_id=item.id, bought=item.actual_bought, packs=item.actual_packs)
            for item in self.session.scalars(
                select(m.BasketItem).where(m.BasketItem.basket_id == basket_id)
            )
            if item.actual_bought is not None
        )
        return replace(
            original,
            expires_at=parent.expires_at,
            response=original.response.model_copy(update={"status": BasketStatus(stored.status)}),
            actual_lines=actual,
        )

    def save_basket(self, household_id, row):
        self._household(household_id)
        if row.household_id != household_id:
            _conflict()
        response = row.response
        parent = self._session_row(household_id, response.session_id, "shop")
        if parent is None:
            _conflict()
        stored = self._row(m.Basket, household_id, response.id)
        if stored is None:
            if response.status != BasketStatus.SUGGESTED:
                _conflict()
            stored = m.Basket(
                id=response.id,
                session_id=response.session_id,
                household_id=household_id,
                people=response.people,
                meals=response.meals,
                status=response.status.value,
                planning_snapshot=dump_snapshot(row),
            )
            self.session.add(stored)
            self.session.flush()
            self.session.add_all(
                m.BasketMeal(basket_id=response.id, position=index, recipe_id=meal.id)
                for index, meal in enumerate(response.planned_meals)
            )
            self.session.add_all(
                m.BasketItem(
                    id=item.id,
                    basket_id=response.id,
                    ingredient_id=item.ingredient_id,
                    suggested_packs=item.suggested_packs,
                    needs_check=item.needs_check,
                    reason=item.amount,
                )
                for item in response.items
            )
        else:
            original = self._load(stored.planning_snapshot, BasketRow, household_id)
            if (
                row.ingredients != original.ingredients
                or row.purchases != original.purchases
                or response.model_copy(update={"status": original.response.status})
                != original.response
            ):
                _conflict()
            stored.status = response.status.value
            actual = {line.basket_item_id: line for line in row.actual_lines}
            for item in self.session.scalars(
                select(m.BasketItem).where(m.BasketItem.basket_id == response.id)
            ):
                if item.id in actual:
                    item.actual_bought, item.actual_packs = (
                        actual[item.id].bought,
                        actual[item.id].packs,
                    )
            if response.status == BasketStatus.CONFIRMED:
                parent.status = "done"
        self.session.flush()

    def confirmation(self, household_id, key):
        self._household(household_id)
        stored = self.session.get(m.RecommendationConfirmation, (household_id, key))
        if stored is not None:
            result = self._load(stored.response_snapshot, Confirmation)
            if (
                result.operation,
                result.target_id,
                result.request_json,
                result.response.event.id,
            ) != (stored.operation, stored.target_id, stored.request_json, stored.stock_event_id):
                _conflict()
            return result
        existing = self.session.scalar(
            select(m.StockEvent.id).where(
                m.StockEvent.household_id == household_id, m.StockEvent.idempotency_key == key
            )
        )
        if existing is not None:
            _conflict("Idempotency key already belongs to another stock action")
        return None

    def apply_stock(self, user, event_type, lines, key, ref_type, ref_id):
        self._household(user.household_id)
        if user.user_id != self.user.user_id:
            _conflict()
        inserted = set()

        def record_insert(session, instance):
            if isinstance(instance, m.StockEvent) and instance.idempotency_key == key:
                inserted.add(instance.id)

        event.listen(self.session, "pending_to_persistent", record_insert)
        try:
            change = stock_events.apply_stock_event(
                self.session, user, event_type, lines, key, ref_type, ref_id
            )
        finally:
            event.remove(self.session, "pending_to_persistent", record_insert)
        if change.event.id not in inserted or (
            change.event.type,
            change.event.ref_type,
            change.event.ref_id,
        ) != (event_type, ref_type, ref_id):
            _conflict("Idempotency key was claimed by another stock action")
        target = m.CookRecord if ref_type.value == "cook_session" else m.Basket
        stored = self._row(target, user.household_id, ref_id)
        if stored is None:
            _conflict()
        stored.stock_event_id = change.event.id
        self.session.flush()
        return change

    def save_confirmation(self, household_id, key, result):
        self._household(household_id)
        self.session.add(
            m.RecommendationConfirmation(
                household_id=household_id,
                idempotency_key=key,
                operation=result.operation,
                target_id=result.target_id,
                request_json=result.request_json,
                response_snapshot=dump_snapshot(result),
                stock_event_id=result.response.event.id,
                created_at=clock.now(),
            )
        )
        self.session.flush()


def recommendation_workflow(user):
    @contextmanager
    def unit_of_work():
        with transaction() as session:
            yield SqlRecommendationRepository(session, user)

    return RecommendationWorkflow(unit_of_work)
