"""Requested dishes and editable Shop keywords survive the complete planning flow."""

from copy import deepcopy
from dataclasses import replace
from itertools import count

import pytest

from app.auth import CurrentUser
from app.errors import ApiError, ErrorCode
from app.reco import adjust_shop, plan_shop
from app.reco.shop_models import ShopSession
from app.schemas.common import Allergen
from app.schemas.shop import ShopAdjust, ShopSessionCreate, ShopTag
from app.services.recommendation_repository import BasketRow
from app.services.recommendation_snapshots import dump_snapshot, load_snapshot
from app.services.recommendation_workflow import RecommendationWorkflow
from evaluation.catalogue_review import NOW as REVIEW_NOW
from evaluation.catalogue_review import load_catalogue, preferences
from tests.reco_fixtures import CATALOGUE, NOW, PURCHASES, batch, prefs, recipe, uid
from tests.recommendation_repository_fake import HOUSEHOLD, FakeDatabase, set_recipes


def test_real_requested_rice_salad_is_not_silently_replaced_by_other_meals():
    _, _, recipes, metadata, purchases = load_catalogue()
    salad = next(
        meal for meal in recipes if meal.title == "Cucumber, tomato and chickpea rice salad"
    )
    result = plan_shop(
        recipes,
        [],
        preferences(),
        ShopSession(pinned_recipe_ids=(salad.id,)),
        metadata,
        purchases,
        as_of=REVIEW_NOW,
    )
    assert result.planned_meals == ()
    assert result.unavailable_recipe_ids == (salad.id,)
    assert result.required_at_home == ("cooked rice",)


@pytest.mark.parametrize("missing", [False, True])
def test_requested_recipe_still_respects_hard_filters_and_catalogue_membership(missing):
    asked, alternative = recipe("asked"), recipe("alternative", ingredients=("tomato",))
    result = plan_shop(
        [alternative] if missing else [asked, alternative],
        [],
        prefs(allergens=[Allergen.EGG]),
        ShopSession(pinned_recipe_ids=(asked.id,)),
        CATALOGUE,
        PURCHASES,
        as_of=NOW,
    )
    assert not result.planned_meals
    assert result.unavailable_recipe_ids == (asked.id,)
    assert not result.required_at_home


def test_requested_meals_must_have_enough_nonbuyable_stock_for_the_combination():
    meals = [recipe("one"), recipe("two")]
    purchases = {
        **PURCHASES,
        uid("egg"): PURCHASES[uid("egg")].model_copy(update={"buyable": False}),
    }
    result = plan_shop(
        meals,
        [batch(count=3)],
        prefs(),
        ShopSession(meals=2, pinned_recipe_ids=tuple(meal.id for meal in meals)),
        CATALOGUE,
        purchases,
        as_of=NOW,
    )
    assert not result.planned_meals
    assert result.required_at_home == ("egg",)


def test_replacing_keywords_removes_old_tags_and_keeps_requested_recipes():
    session = ShopSession(tags=(ShopTag.MORE_VEGETABLES,), pinned_recipe_ids=(uid("asked"),))
    changed = adjust_shop(session, ShopAdjust(tags=[ShopTag.LONGER_LASTING], replace_tags=True))
    assert changed.tags == (ShopTag.LONGER_LASTING,)
    assert changed.pinned_recipe_ids == session.pinned_recipe_ids
    assert adjust_shop(changed, ShopAdjust(tags=[], replace_tags=True)).tags == ()
    assert adjust_shop(session, ShopAdjust(tags=[ShopTag.LONGER_LASTING])).tags == (
        ShopTag.MORE_VEGETABLES,
        ShopTag.LONGER_LASTING,
    )


def test_replacing_existing_cover_more_keyword_does_not_add_an_unrequested_meal():
    session = ShopSession(meals=4, tags=(ShopTag.COVER_MORE_MEALS,))
    assert (
        adjust_shop(session, ShopAdjust(tags=[ShopTag.COVER_MORE_MEALS], replace_tags=True)).meals
        == 4
    )
    assert adjust_shop(session, ShopAdjust(tags=[ShopTag.COVER_MORE_MEALS])).meals == 5
    assert (
        adjust_shop(
            ShopSession(), ShopAdjust(tags=[ShopTag.COVER_MORE_MEALS], replace_tags=True)
        ).meals
        == 4
    )


def workflow():
    database = FakeDatabase()
    ids = count()
    service = RecommendationWorkflow(
        database.transaction, now=lambda: NOW, new_id=lambda: uid(f"shop-adjust/{next(ids)}")
    )
    user = CurrentUser(uid("shop-user"), HOUSEHOLD, "shop@example.test")
    return database, service, user


def test_blocked_requested_dish_returns_actionable_error_without_saving_replacement():
    db, service, user = workflow()
    db.state["inventory"][HOUSEHOLD] = []
    catalogue = db.state["catalogue"]
    db.state["catalogue"] = replace(
        catalogue,
        purchases={
            **catalogue.purchases,
            uid("egg"): catalogue.purchases[uid("egg")].model_copy(update={"buyable": False}),
        },
    )
    before = deepcopy(db.state)
    with pytest.raises(ApiError) as error:
        service.start_shop(user, ShopSessionCreate(recipe_ids=[uid("one")]))
    assert error.value.code == ErrorCode.NO_RESULT
    assert "prepare or confirm usable egg" in error.value.message
    assert error.value.details["required_at_home"] == ["egg"]
    assert db.state == before


def test_keyword_removal_changes_persisted_plan_and_keeps_requested_dish():
    db, service, user = workflow()
    set_recipes(db, recipe("asked", ingredients=("tomato",)), recipe("other"))
    first = service.start_shop(user, ShopSessionCreate(recipe_ids=[uid("asked")]))
    added = service.adjust_shop(user, first.session_id, ShopAdjust(tags=[ShopTag.MORE_VEGETABLES]))
    removed = service.adjust_shop(user, first.session_id, ShopAdjust(tags=[], replace_tags=True))
    assert added.applied_tags == [ShopTag.MORE_VEGETABLES]
    assert removed.applied_tags == []
    assert removed.requested_recipe_ids == [uid("asked")]
    assert removed.planned_meals[0].id == uid("asked")


def test_legacy_basket_snapshot_without_requested_pins_still_loads():
    db, service, user = workflow()
    db.state["inventory"][HOUSEHOLD] = []
    basket = service.start_shop(user, ShopSessionCreate())
    row = db.state["baskets"][HOUSEHOLD, basket.id]
    payload = dump_snapshot(row)
    del payload["payload"]["response"]["requested_recipe_ids"]
    assert load_snapshot(payload, BasketRow) == row
    assert "requested_recipe_ids" not in payload["payload"]["response"]
