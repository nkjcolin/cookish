"""Transactional test double only. This is NOT a database or concurrency test."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace

from app.errors import ApiError, ErrorCode
from app.reco.learning import LearningState
from app.schemas.common import FreshnessStatus
from app.schemas.inventory import InventoryItem
from app.schemas.stock_events import InventoryChange, ItemSnapshot, StockEvent, StockEventLine
from app.services.recommendation_repository import RecipeCatalogue
from app.services.stock_events import ChangeBatch
from tests.reco_fixtures import CATALOGUE, NOW, PURCHASES, batch, prefs, recipe, uid

HOUSEHOLD = uid("workflow-household")
OTHER = uid("workflow-other-household")


class FakeDatabase:
    def __init__(self):
        self.state = {
            "prefs": {household: prefs() for household in (HOUSEHOLD, OTHER)},
            "inventory": {household: [batch(count=10)] for household in (HOUSEHOLD, OTHER)},
            "catalogue": RecipeCatalogue(
                (recipe("one", starred=True), recipe("two"), recipe("three")),
                deepcopy(CATALOGUE),
                deepcopy(PURCHASES),
            ),
            "learning": {household: LearningState(household) for household in (HOUSEHOLD, OTHER)},
            "cook_sessions": {},
            "cook_records": {},
            "shop_sessions": {},
            "baskets": {},
            "confirmations": {},
            "events": {},
        }
        self.fail_on = None
        self.stock_attempts = 0

    @contextmanager
    def transaction(self):
        pending = deepcopy(self.state)
        yield FakeRepository(self, pending)
        self.state = deepcopy(pending)


class FakeRepository:
    def __init__(self, database, state):
        self.database, self.state = database, state

    def preferences(self, household_id):
        return self.state["prefs"][household_id]

    def inventory(self, household_id):
        return self.state["inventory"][household_id]

    def catalogue(self, household_id):
        assert household_id in self.state["prefs"]
        return self.state["catalogue"]

    def learning(self, household_id):
        return self.state["learning"][household_id]

    def save_learning(self, household_id, state, *, user_id):
        if self.database.fail_on == "save_learning":
            raise RuntimeError("simulated persistence failure")
        assert state.household_id == household_id
        self.state["learning"][household_id] = state

    def remember(self, household_id, *, cook_people=None, shop_people=None, shop_meals=None):
        changes = {
            key: value
            for key, value in {
                "last_cook_people": cook_people,
                "last_shop_people": shop_people,
                "last_shop_meals": shop_meals,
            }.items()
            if value is not None
        }
        self.state["prefs"][household_id] = self.preferences(household_id).model_copy(
            update=changes
        )

    def cook_session(self, household_id, session_id):
        return self.state["cook_sessions"].get((household_id, session_id))

    def save_cook_session(self, household_id, row):
        assert row.household_id == household_id
        self.state["cook_sessions"][household_id, row.id] = row

    def cook_record(self, household_id, record_id):
        return self.state["cook_records"].get((household_id, record_id))

    def save_cook_record(self, household_id, row):
        assert row.household_id == household_id
        self.state["cook_records"][household_id, row.response.id] = row

    def shop_session(self, household_id, session_id):
        return self.state["shop_sessions"].get((household_id, session_id))

    def save_shop_session(self, household_id, row):
        assert row.household_id == household_id
        self.state["shop_sessions"][household_id, row.id] = row

    def basket(self, household_id, basket_id):
        return self.state["baskets"].get((household_id, basket_id))

    def save_basket(self, household_id, row):
        assert row.household_id == household_id
        self.state["baskets"][household_id, row.response.id] = row

    def confirmation(self, household_id, key):
        return self.state["confirmations"].get((household_id, key))

    def save_confirmation(self, household_id, key, result):
        if self.database.fail_on == "save_confirmation":
            raise RuntimeError("simulated response persistence failure")
        assert (household_id, key) not in self.state["confirmations"]
        self.state["confirmations"][household_id, key] = result

    def apply_stock(self, user, event_type, lines, key, ref_type, ref_id):
        self.database.stock_attempts += 1
        household = user.household_id
        assert (household, key) not in self.state["events"]
        batches = {item.id: item for item in self.inventory(household)}
        touched, event_lines = [], []
        for index, line in enumerate(lines):
            if isinstance(line, ChangeBatch):
                previous = batches.get(line.item_id)
                if previous is None:
                    raise ApiError(ErrorCode.NOT_FOUND, "Batch not found")
                if previous.revision != line.revision:
                    raise ApiError(ErrorCode.STALE_REVISION, "Stale batch")
                before = ItemSnapshot.model_validate(previous.model_dump())
                current = previous.model_copy(
                    update={**line.changes, "revision": previous.revision + 1}
                )
            else:
                before = None
                # The fixture only approximates catalogue defaults; not Role 2's implementation.
                meta = self.catalogue(household).ingredients[line.item.ingredient_id]
                current = InventoryItem(
                    **{
                        **batch().model_dump(),
                        "id": uid(f"purchase/{household}/{key}/{index}"),
                        "ingredient_id": meta.id,
                        "display_name": meta.canonical_name,
                        "countable": meta.countable,
                        "count": line.item.count,
                        "unit": line.item.unit,
                        "remaining_state": line.item.remaining_state,
                        "source": line.source,
                        "acquired_at": line.item.acquired_at,
                        "freshness_status": FreshnessStatus.OK,
                    }
                )
            batches[current.id] = current
            touched.append(current)
            event_lines.append(
                StockEventLine(
                    inventory_item_id=current.id,
                    display_name=current.display_name,
                    before=before,
                    after=ItemSnapshot.model_validate(current.model_dump()),
                )
            )
        event = StockEvent(
            id=uid(f"event/{household}/{key}"),
            type=event_type,
            ref_type=ref_type,
            ref_id=ref_id,
            user_id=user.user_id,
            created_at=NOW,
            lines=event_lines,
            reverts_event_id=None,
            can_undo=True,
        )
        change = InventoryChange(event=event, items=touched)
        self.state["inventory"][household] = list(batches.values())
        self.state["events"][household, key] = change
        return change


def set_recipes(database, *meals):
    database.state["catalogue"] = replace(database.state["catalogue"], recipes=meals)
