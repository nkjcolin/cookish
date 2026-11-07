"""Seeds a demo household for local development. Role 2 owns this file.

    uv run python -m seed.demo          # from backend/

Locally there is no sign-in: app/auth.py treats every request as one fixed development user.
This creates that user, a household with the kitchen the frontend was built against (the one
in app/mock.py), and its preferences, so the screens look the same when stubs are replaced
by real services.

It only creates what is missing and never overwrites, so edits made while testing survive a
restart. `docker compose down -v` gives a fresh demo kitchen.

It runs from the development Dockerfile only. The deployed stack signs people in with Cognito,
and nobody there has the development user's id, so a demo household would be unreachable.

Dates are set so the batches get the same freshness as the mock kitchen once freshness is
computed on read: eggs and half a cabbage use soon, chicken is past its estimate, tofu has a use-by
label, and the rice stock is unknown.
"""

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.auth import DEV_CLAIMS
from app.clock import now, today
from app.db.models import Household, HouseholdMember, Ingredient, InventoryItem, Preferences, User
from app.db.session import transaction
from seed.seed import INGREDIENTS_CSV, SHELF_LIFE_BY_STORAGE, SeedError, read_ingredients

DEMO_HOUSEHOLD_ID = uuid5(NAMESPACE_URL, "cookish-demo/household")


@dataclass(frozen=True)
class DemoItem:
    key: str
    ingredient: str  # canonical_name in ingredients.csv
    display_name: str
    count: float | None = None  # only for ingredients tracked by count
    state: str = "enough"
    use_first_in_days: int | None = None  # aim for this use-first date, using the shelf life
    label_use_by_in_days: int | None = None  # a use-by date printed on the package
    bought_days_ago: int = 1  # used when there is no use-first date to aim for
    confirmed_days_ago: int = 1
    source: str = "manual"


ITEMS = [
    DemoItem("egg-old", "egg", "Egg", count=2, use_first_in_days=2, source="receipt"),
    DemoItem("egg-new", "egg", "Egg", count=6, use_first_in_days=14, source="receipt"),
    DemoItem("tomato", "tomato", "Tomato", count=3, use_first_in_days=5),
    DemoItem("cabbage", "cabbage", "Cabbage", count=0.5, use_first_in_days=1),
    DemoItem("garlic", "garlic", "Garlic", use_first_in_days=25),
    DemoItem("chicken", "chicken thigh", "Chicken thigh", use_first_in_days=-1, source="photo"),
    DemoItem("tofu", "firm tofu", "Firm tofu", label_use_by_in_days=4, source="voice"),
    DemoItem(
        "rice",
        "uncooked rice",
        "Rice",
        state="unknown",
        bought_days_ago=30,
        confirmed_days_ago=30,
    ),
]

PREFERENCES = {
    "allergens": [],
    "diets": [],
    "equipment": ["stove", "rice_cooker", "microwave"],
    "cuisines": ["chinese", "malay"],
    "disliked_ingredient_ids": [],
    "max_cook_minutes": 45,
    "max_difficulty": 2,
    "household_size": 2,
    "last_cook_people": 2,
    "last_shop_people": 2,
    "last_shop_meals": 3,
}


def build_items(
    catalogue: dict[str, dict[str, Any]], today_: date, now_: datetime
) -> list[dict[str, Any]]:
    """The demo kitchen as inventory_items rows. `catalogue` maps canonical_name to its CSV row."""
    rows = []
    for item in ITEMS:
        ing = catalogue[item.ingredient]
        storage = ing["default_storage"]
        shelf_life = ing[SHELF_LIFE_BY_STORAGE[storage]]

        label_date = None
        if item.label_use_by_in_days is not None:
            label_date = today_ + timedelta(days=item.label_use_by_in_days)
            acquired = today_ - timedelta(days=item.bought_days_ago)
        elif item.use_first_in_days is not None and shelf_life is not None:
            # Work back from the use-first date we want, so the batch ages the way the mock does.
            acquired = today_ + timedelta(days=item.use_first_in_days - shelf_life)
        else:
            acquired = today_ - timedelta(days=item.bought_days_ago)

        rows.append(
            {
                "id": uuid5(NAMESPACE_URL, f"cookish-demo/item/{item.key}"),
                "household_id": DEMO_HOUSEHOLD_ID,
                "ingredient_id": ing["id"],
                "display_name": item.display_name,
                "count": None if item.count is None else Decimal(str(item.count)),
                "unit": ing["default_unit"] if item.count is not None else None,
                "remaining_state": item.state,
                "storage": storage,
                "source": item.source,
                "acquired_at": acquired,
                "label_date": label_date,
                "label_date_kind": "use_by" if label_date else None,
                "last_confirmed_at": now_ - timedelta(days=item.confirmed_days_ago),
                "revision": 1,
            }
        )
    return rows


def seed_demo() -> dict[str, int]:
    ingredients, problems = read_ingredients(INGREDIENTS_CSV)
    if problems:
        raise SeedError(problems)
    catalogue = {row["canonical_name"]: row for row in ingredients}
    missing = sorted({item.ingredient for item in ITEMS} - catalogue.keys())
    if missing:
        raise SeedError([f"the demo kitchen uses {missing}, which are not in ingredients.csv"])

    items = build_items(catalogue, today(), now())
    user_id = UUID(DEV_CLAIMS["sub"])

    with transaction() as s:
        wanted = {row["ingredient_id"] for row in items}
        in_database = set(s.scalars(select(Ingredient.id).where(Ingredient.id.in_(wanted))))
        if in_database != wanted:
            raise SeedError(["the catalogue is not loaded yet: run `python -m seed.seed` first"])

        existing = s.scalar(
            select(HouseholdMember.household_id).where(HouseholdMember.user_id == user_id).limit(1)
        )
        if existing is not None and existing != DEMO_HOUSEHOLD_ID:
            return {"skipped": 1, "items": 0}  # the dev user already has a household; leave it

        s.execute(
            insert(User)
            .values(id=user_id, email=DEV_CLAIMS["email"], display_name="Dev")
            .on_conflict_do_nothing(index_elements=["id"])
        )
        s.execute(
            insert(Household)
            .values(id=DEMO_HOUSEHOLD_ID, name="Dev's kitchen")
            .on_conflict_do_nothing(index_elements=["id"])
        )
        s.execute(
            insert(HouseholdMember)
            .values(household_id=DEMO_HOUSEHOLD_ID, user_id=user_id, role="owner")
            .on_conflict_do_nothing(index_elements=["household_id", "user_id"])
        )
        s.execute(
            insert(Preferences)
            .values(household_id=DEMO_HOUSEHOLD_ID, **PREFERENCES)
            .on_conflict_do_nothing(index_elements=["household_id"])
        )
        created = s.execute(
            insert(InventoryItem)
            .values(items)
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(InventoryItem.id)
        ).all()
    return {"skipped": 0, "items": len(created)}


def main() -> int:
    try:
        result = seed_demo()
    except SeedError as error:
        print("Demo seeding stopped:", file=sys.stderr)
        for problem in error.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if result["skipped"]:
        print("Demo household skipped: the development user already has a household.")
    else:
        print(f"Demo household ready ({result['items']} new kitchen items).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
