"""Transactional PostgreSQL implementation of the Role 5 persistence port.

All Role 5 mutations lock the household first. Stock writes still go through
Role 2 in this same transaction, including its unique shared idempotency key.
"""

from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import select

from app import clock
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.reco.learning import LearningState, taste_weights
from app.schemas.cook import CookConfirmResult, CookRecord
from app.schemas.shop import BasketConfirmResult, BoughtLine
from app.services import recommendation_snapshots as snapshots
from app.services.recommendation_inputs import SqlRecommendationInputs
from app.services.recommendation_repository import (
    BasketRow,
    Confirmation,
    CookRecordRow,
    CookSessionRow,
    ShopSessionRow,
)
from app.services.stock_events import apply_stock_event


def conflict(message):
    raise ApiError(ErrorCode.CONFLICT, message)


class SqlRecommendationRepository(SqlRecommendationInputs):
    def __init__(self, session):
        super().__init__(session)
        self.household_id = None
        self.created_events = {}

    def lock(self, household_id):
        if self.household_id is not None:
            if self.household_id != household_id:
                raise ApiError(ErrorCode.NOT_FOUND, "Household not found")
            return
        found = self.session.scalar(
            # NO KEY UPDATE serializes Role 5 writers while allowing the FK
            # KEY SHARE locks taken by concurrent manual stock-event inserts.
            # FOR UPDATE here can deadlock with a shared idempotency-key race.
            select(m.Household.id)
            .where(m.Household.id == household_id)
            .with_for_update(key_share=True)
        )
        if found is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Household not found")
        self.household_id = household_id

    def _owned(self, model, household_id, target_id):
        self.lock(household_id)
        return self.session.scalar(
            select(model)
            .where(model.id == target_id, model.household_id == household_id)
            .with_for_update()
        )

    def preferences(self, household_id):
        self.lock(household_id)
        return super().preferences(household_id)

    def remember(self, household_id, *, cook_people=None, shop_people=None, shop_meals=None):
        self.preferences(household_id)
        row = self.session.get(m.Preferences, household_id)
        for field, value in (
            ("last_cook_people", cook_people),
            ("last_shop_people", shop_people),
            ("last_shop_meals", shop_meals),
        ):
            if value is not None:
                setattr(row, field, value)

    def _session(self, household_id, session_id, mode):
        row = self._owned(m.PlanSession, household_id, session_id)
        return row if row is not None and row.mode == mode else None

    def cook_session(self, household_id, session_id):
        row = self._session(household_id, session_id, "cook")
        if row is None:
            return None
        state = snapshots.restore("cook_session", snapshots.CookState, row.recommendation_state)
        if state.position != row.position or state.state.people != row.people:
            conflict("Saved Cook session is inconsistent")
        if any(entry.session_id != row.id for entry in state.history):
            conflict("Saved history belongs to another session")
        if not 0 <= state.position < len(state.history):
            conflict("Saved history position is invalid")
        return CookSessionRow(
            row.id,
            household_id,
            row.expires_at,
            state.state,
            state.history,
            state.position,
            row.user_id,
            state.selected_record_id,
        )

    def save_cook_session(self, household_id, row):
        stored = self._save_session(household_id, row, "cook")
        stored.position = row.position
        stored.shown_recipe_ids = list(row.state.shown_recipe_ids)
        stored.constraints = {
            "max_minutes": row.state.max_minutes,
            "max_difficulty": row.state.max_difficulty,
        }
        stored.adjustments = [tag.value for tag in row.state.tags]
        stored.recommendation_state = snapshots.dump(
            "cook_session",
            snapshots.CookState,
            snapshots.CookState(
                state=row.state,
                history=row.history,
                position=row.position,
                selected_record_id=row.selected_record_id,
            ),
        )
        self.session.flush()

    def shop_session(self, household_id, session_id):
        row = self._session(household_id, session_id, "shop")
        if row is None:
            return None
        saved = snapshots.restore("shop_session", snapshots.ShopState, row.recommendation_state)
        if saved.state.people != row.people:
            conflict("Saved Shop session is inconsistent")
        return ShopSessionRow(
            row.id, household_id, row.expires_at, saved.state, saved.basket_id, row.user_id
        )

    def save_shop_session(self, household_id, row):
        stored = self._save_session(household_id, row, "shop")
        stored.adjustments = [tag.value for tag in row.state.tags]
        stored.recommendation_state = snapshots.dump(
            "shop_session",
            snapshots.ShopState,
            snapshots.ShopState(state=row.state, basket_id=row.basket_id),
        )
        self.session.flush()

    def _save_session(self, household_id, row, mode):
        self.lock(household_id)
        if row.household_id != household_id:
            raise ApiError(ErrorCode.NOT_FOUND, "Session not found")
        stored = self._owned(m.PlanSession, household_id, row.id)
        if stored is None:
            stored = m.PlanSession(
                id=row.id,
                household_id=household_id,
                user_id=row.user_id,
                mode=mode,
                expires_at=row.expires_at,
                status="active",
            )
            self.session.add(stored)
        elif stored.mode != mode or stored.user_id != row.user_id:
            conflict("Session identity cannot change")
        stored.people = row.state.people
        return stored

    def cook_record(self, household_id, record_id):
        row = self._owned(m.CookRecord, household_id, record_id)
        if row is None:
            return None
        selected = snapshots.restore("selection", snapshots.Selection, row.selection_snapshot)
        response = (
            selected.response
            if row.confirmation_snapshot is None
            else snapshots.restore("cooked_record", CookRecord, row.confirmation_snapshot)
        )
        if (response.id, response.session_id, response.recipe.id, response.status) != (
            row.id,
            row.session_id,
            row.recipe_id,
            row.status,
        ):
            conflict("Saved cooking record is inconsistent")
        session = self._session(household_id, row.session_id, "cook")
        if session is None:
            conflict("Cooking session is missing")
        return CookRecordRow(
            household_id, session.expires_at, selected.recipe, response, row.user_id
        )

    def save_cook_record(self, household_id, row):
        response = row.response
        session = self._session(household_id, response.session_id, "cook")
        if row.household_id != household_id or session is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Session not found")
        stored = self._owned(m.CookRecord, household_id, response.id)
        if stored is None:
            if response.status != "selected":
                conflict("A cooking record must start with selection")
            stored = m.CookRecord(
                id=response.id,
                household_id=household_id,
                session_id=response.session_id,
                recipe_id=response.recipe.id,
                user_id=row.user_id,
                people=response.people,
            )
            stored.selection_snapshot = snapshots.dump(
                "selection",
                snapshots.Selection,
                snapshots.Selection(recipe=row.recipe_snapshot, response=response),
            )
            self.session.add(stored)
        elif (stored.session_id, stored.recipe_id, stored.user_id) != (
            response.session_id,
            response.recipe.id,
            row.user_id,
        ):
            conflict("Cooking record identity cannot change")
        stored.status = response.status.value
        if response.status == "confirmed":
            stored.confirmation_snapshot = snapshots.dump("cooked_record", CookRecord, response)
            session.status = "done"
        self.session.flush()

    def basket(self, household_id, basket_id):
        row = self._owned(m.Basket, household_id, basket_id)
        if row is None:
            return None
        saved = snapshots.restore("planning", snapshots.Planning, row.planning_snapshot)
        if (saved.response.id, saved.response.session_id) != (row.id, row.session_id):
            conflict("Saved basket is inconsistent")
        session = self._session(household_id, row.session_id, "shop")
        if session is None:
            conflict("Shopping session is missing")
        actual = tuple(
            BoughtLine(basket_item_id=line.id, bought=line.actual_bought, packs=line.actual_packs)
            for line in self.session.scalars(
                select(m.BasketItem)
                .where(m.BasketItem.basket_id == row.id)
                .order_by(m.BasketItem.id)
            )
            if line.actual_bought is not None
        )
        response = saved.response.model_copy(update={"status": row.status})
        return BasketRow(
            household_id, session.expires_at, response, saved.ingredients, saved.purchases, actual
        )

    def save_basket(self, household_id, row):
        response = row.response
        session = self._session(household_id, response.session_id, "shop")
        if row.household_id != household_id or session is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Session not found")
        stored = self._owned(m.Basket, household_id, response.id)
        if stored is None:
            if response.status != "suggested":
                conflict("A basket must start with planning")
            stored = m.Basket(
                id=response.id,
                session_id=response.session_id,
                household_id=household_id,
                people=response.people,
                meals=response.meals,
                status="suggested",
                planning_snapshot=snapshots.dump(
                    "planning",
                    snapshots.Planning,
                    snapshots.Planning(
                        response=response, ingredients=row.ingredients, purchases=row.purchases
                    ),
                ),
            )
            self.session.add(stored)
            self.session.flush()
            self.session.add_all(
                m.BasketMeal(basket_id=response.id, position=index, recipe_id=meal.id)
                for index, meal in enumerate(response.planned_meals)
            )
            self.session.add_all(
                m.BasketItem(
                    id=line.id,
                    basket_id=response.id,
                    ingredient_id=line.ingredient_id,
                    suggested_packs=line.suggested_packs,
                    needs_check=line.needs_check,
                    reason=line.amount,
                )
                for line in response.items
            )
            self.session.flush()
        stored.status = response.status
        if response.status == "confirmed":
            session.status = "done"
        for actual in row.actual_lines:
            line = self.session.scalar(
                select(m.BasketItem).where(
                    m.BasketItem.id == actual.basket_item_id, m.BasketItem.basket_id == response.id
                )
            )
            if line is None:
                conflict("Purchased line is not in the saved basket")
            line.actual_bought, line.actual_packs = actual.bought, actual.packs
        self.session.flush()

    def learning(self, household_id):
        self.preferences(household_id)
        row = self.session.get(m.RecommendationLearning, household_id)
        if row is None:
            if self.session.get(m.Preferences, household_id).taste_weights:
                conflict("Existing learned weights have no evidence; migration review is needed")
            return LearningState(household_id)
        saved = snapshots.restore("learning", snapshots.Evidence, row.state)
        return LearningState(household_id, saved.meals, saved.config)

    def save_learning(self, household_id, state, *, user_id):
        previous = self.learning(household_id)
        if state.household_id != household_id:
            raise ApiError(ErrorCode.NOT_FOUND, "Learning state not found")
        if state == previous:
            return
        old = {meal.record_id: meal for meal in previous.meals}
        for meal in state.meals:
            if old.get(meal.record_id) == meal:
                continue
            record = self._owned(m.CookRecord, household_id, meal.record_id)
            if record is None or record.status != "confirmed" or record.recipe_id != meal.recipe_id:
                conflict("Only confirmed meals may train preferences")
            self.session.add(
                m.RecipeFeedback(
                    household_id=household_id,
                    user_id=user_id,
                    recipe_id=meal.recipe_id,
                    session_id=record.session_id,
                    cook_record_id=record.id,
                    signal="cooked" if meal.rating is None else meal.rating.value,
                )
            )
        row = self.session.get(m.RecommendationLearning, household_id)
        if row is None:
            row = m.RecommendationLearning(household_id=household_id)
            self.session.add(row)
        row.state = snapshots.dump(
            "learning",
            snapshots.Evidence,
            snapshots.Evidence(meals=state.meals, config=state.config),
        )
        row.updated_by, row.updated_at = user_id, clock.now()
        self.session.get(m.Preferences, household_id).taste_weights = taste_weights(state)
        self.session.flush()

    def confirmation(self, household_id, key):
        self.lock(household_id)
        row = self.session.get(m.RecommendationConfirmation, (household_id, key))
        if row is not None:
            schema = CookConfirmResult if row.operation == "cook" else BasketConfirmResult
            response = snapshots.restore(
                row.operation + "_confirmation", schema, row.response_snapshot
            )
            target = response.cook_record_id if row.operation == "cook" else response.basket_id
            if target != row.target_id or response.event.id != row.stock_event_id:
                conflict("Saved confirmation is inconsistent")
            return Confirmation(row.operation, row.target_id, row.request_json, response)
        if self._event(household_id, key) is not None:
            conflict("Idempotency key already belongs to another stock operation")
        return None

    def _event(self, household_id, key):
        return self.session.scalar(
            select(m.StockEvent).where(
                m.StockEvent.household_id == household_id, m.StockEvent.idempotency_key == key
            )
        )

    def apply_stock(self, user, event_type, lines, key, ref_type, ref_id):
        self.lock(user.household_id)
        if self._event(user.household_id, key) is not None:
            conflict("Idempotency key already belongs to a stock operation")
        change = apply_stock_event(self.session, user, event_type, lines, key, ref_type, ref_id)
        self.created_events[key] = change.event.id
        return change

    def save_confirmation(self, household_id, key, result):
        self.lock(household_id)
        if self.created_events.get(key) != result.response.event.id:
            conflict("Confirmation must own its stock event in this transaction")
        schema = CookConfirmResult if result.operation == "cook" else BasketConfirmResult
        self.session.add(
            m.RecommendationConfirmation(
                household_id=household_id,
                idempotency_key=key,
                operation=result.operation,
                target_id=result.target_id,
                request_json=result.request_json,
                stock_event_id=result.response.event.id,
                response_snapshot=snapshots.dump(
                    result.operation + "_confirmation", schema, result.response
                ),
            )
        )
        model = m.CookRecord if result.operation == "cook" else m.Basket
        target = self._owned(model, household_id, result.target_id)
        if target is None:
            conflict("Confirmation target is missing")
        target.stock_event_id = result.response.event.id
        self.session.flush()

    def set_star(self, user, recipe_id, starred):
        self.lock(user.household_id)
        candidate = next(
            (r for r in self.catalogue(user.household_id).recipes if r.id == recipe_id), None
        )
        if candidate is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Recipe not found")
        if candidate.starred == starred:
            return
        latest = self.session.scalar(
            select(m.RecipeFeedback.created_at)
            .where(
                m.RecipeFeedback.household_id == user.household_id,
                m.RecipeFeedback.recipe_id == recipe_id,
                m.RecipeFeedback.signal.in_(("starred", "unstarred")),
            )
            .order_by(m.RecipeFeedback.created_at.desc())
            .limit(1)
        )
        timestamp = clock.now()
        if latest is not None:
            timestamp = max(timestamp, latest + timedelta(microseconds=1))
        self.session.add(
            m.RecipeFeedback(
                household_id=user.household_id,
                user_id=user.user_id,
                recipe_id=recipe_id,
                signal="starred" if starred else "unstarred",
                created_at=timestamp,
            )
        )
        self.session.flush()


@contextmanager
def recommendation_uow():
    with transaction() as session:
        yield SqlRecommendationRepository(session)
