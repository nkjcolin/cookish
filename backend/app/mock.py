"""Fixed sample data returned by the stub services.

Nothing here is stored: every call returns the same kitchen. It exists so the frontend
can be built before the real services are, and it disappears as stubs are replaced.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from app.schemas.catalogue import Ingredient
from app.schemas.common import (
    Cuisine,
    Equipment,
    FreshnessStatus,
    IngredientCategory,
    ItemSource,
    LabelDateKind,
    RemainingState,
    Storage,
    TasteTag,
)
from app.schemas.cook import (
    AppliedConstraints,
    ConsumptionOutcome,
    CookRecord,
    CookRecordStatus,
    CookTag,
    FreshnessCheck,
    FreshnessReason,
    IngredientStatus,
    ProposedConsumption,
    StockCheck,
    Suggestion,
    SuggestionIngredient,
)
from app.schemas.identity import Preferences
from app.schemas.inventory import Inventory, InventoryGroup, InventoryItem
from app.schemas.recipes import Recipe, RecipeIngredient, RecipeSummary
from app.schemas.shop import Basket, BasketItem, BasketStatus, ShopTag
from app.schemas.stock_events import (
    ItemSnapshot,
    StockEvent,
    StockEventLine,
    StockEventType,
    StockRefType,
)


def mock_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"cookish-mock/{name}")


USER_ID = mock_id("user")
HOUSEHOLD_ID = mock_id("household")
COOK_SESSION_ID = mock_id("cook-session")
COOK_RECORD_ID = mock_id("cook-record")
SHOP_SESSION_ID = mock_id("shop-session")
BASKET_ID = mock_id("basket")


def _ingredient(
    name: str,
    category: IngredientCategory,
    *,
    countable: bool = False,
    unit: str | None = None,
    storage: Storage = Storage.FRIDGE,
    staple: bool = False,
) -> Ingredient:
    return Ingredient(
        id=mock_id(f"ingredient/{name}"),
        canonical_name=name,
        category=category,
        countable=countable,
        default_unit=unit,
        default_storage=storage,
        is_staple=staple,
    )


INGREDIENTS: dict[str, Ingredient] = {
    i.canonical_name: i
    for i in [
        _ingredient("egg", IngredientCategory.EGG, countable=True, unit="pcs"),
        _ingredient("tomato", IngredientCategory.PRODUCE, countable=True, unit="pcs"),
        _ingredient("cabbage", IngredientCategory.PRODUCE),
        _ingredient("garlic", IngredientCategory.PRODUCE, storage=Storage.PANTRY),
        _ingredient("chicken thigh", IngredientCategory.MEAT),
        _ingredient("firm tofu", IngredientCategory.OTHER, countable=True, unit="pack"),
        _ingredient("rice", IngredientCategory.GRAIN, storage=Storage.PANTRY),
        _ingredient("soy sauce", IngredientCategory.CONDIMENT, storage=Storage.PANTRY, staple=True),
    ]
}


def now() -> datetime:
    return datetime.now(UTC)


def preferences() -> Preferences:
    return Preferences(
        allergens=[],
        diets=[],
        equipment=[Equipment.STOVE, Equipment.RICE_COOKER, Equipment.MICROWAVE],
        cuisines=[Cuisine.CHINESE, Cuisine.MALAY],
        disliked_ingredient_ids=[],
        max_cook_minutes=45,
        max_difficulty=2,
        household_size=2,
        last_cook_people=2,
        last_shop_people=2,
        last_shop_meals=3,
        updated_at=now(),
    )


def _item(
    key: str,
    ingredient: str,
    *,
    count: float | None = None,
    state: RemainingState = RemainingState.ENOUGH,
    bought_days_ago: int = 1,
    use_first_in_days: int | None = None,
    label: LabelDateKind | None = None,
    freshness: FreshnessStatus = FreshnessStatus.OK,
    source: ItemSource = ItemSource.MANUAL,
) -> InventoryItem:
    ing = INGREDIENTS[ingredient]
    today = date.today()
    use_first = None if use_first_in_days is None else today + timedelta(days=use_first_in_days)
    return InventoryItem(
        id=mock_id(f"item/{key}"),
        ingredient_id=ing.id,
        display_name=ing.canonical_name.capitalize(),
        category=ing.category,
        countable=ing.countable,
        count=count,
        unit=ing.default_unit if count is not None else None,
        remaining_state=state,
        storage=ing.default_storage,
        source=source,
        acquired_at=today - timedelta(days=bought_days_ago),
        label_date=use_first if label else None,
        label_date_kind=label,
        est_use_first_date=use_first,
        freshness_status=freshness,
        freshness_confirmed_at=None,
        last_confirmed_at=now() - timedelta(days=bought_days_ago),
        revision=1,
    )


def inventory_items() -> dict[str, InventoryItem]:
    items = [
        _item("egg-old", "egg", count=2, bought_days_ago=12, use_first_in_days=2,
              freshness=FreshnessStatus.USE_SOON, source=ItemSource.RECEIPT),
        _item("egg-new", "egg", count=6, use_first_in_days=14, source=ItemSource.RECEIPT),
        _item("tomato", "tomato", count=3, use_first_in_days=5),
        _item("cabbage", "cabbage", state=RemainingState.LOW, bought_days_ago=6,
              use_first_in_days=1, freshness=FreshnessStatus.USE_SOON),
        _item("garlic", "garlic", bought_days_ago=10, use_first_in_days=40),
        _item("chicken", "chicken thigh", bought_days_ago=3, use_first_in_days=-1,
              freshness=FreshnessStatus.CHECK, source=ItemSource.PHOTO),
        _item("tofu", "firm tofu", count=1, use_first_in_days=4,
              label=LabelDateKind.USE_BY, source=ItemSource.VOICE),
        _item("rice", "rice", bought_days_ago=30),
    ]  # fmt: skip
    return {str(i.id): i for i in items}


def item(key: str) -> InventoryItem:
    return inventory_items()[str(mock_id(f"item/{key}"))]


def inventory() -> Inventory:
    groups: dict[UUID | None, InventoryGroup] = {}
    for it in inventory_items().values():
        group = groups.setdefault(
            it.ingredient_id,
            InventoryGroup(
                ingredient_id=it.ingredient_id,
                name=it.display_name,
                category=it.category,
                countable=it.countable,
                batches=[],
            ),
        )
        group.batches.append(it)
    return Inventory(groups=list(groups.values()))


def stock_event(
    event_type: StockEventType,
    items: list[InventoryItem],
    *,
    ref_type: StockRefType = StockRefType.MANUAL,
    ref_id: UUID | None = None,
    created: bool = False,
    removed: bool = False,
) -> StockEvent:
    def snapshot(it: InventoryItem) -> ItemSnapshot:
        return ItemSnapshot(count=it.count, unit=it.unit, remaining_state=it.remaining_state)

    return StockEvent(
        id=mock_id(f"event/{event_type}"),
        type=event_type,
        ref_type=ref_type,
        ref_id=ref_id,
        user_id=USER_ID,
        created_at=now(),
        lines=[
            StockEventLine(
                inventory_item_id=it.id,
                display_name=it.display_name,
                before=None if created else snapshot(it),
                after=None if removed else snapshot(it),
            )
            for it in items
        ],
        reverts_event_id=mock_id("event/original") if event_type == "undo" else None,
        can_undo=event_type != StockEventType.UNDO,
    )


def _recipe(
    key: str,
    title: str,
    minutes: int,
    tags: list[TasteTag],
    ingredients: list[tuple[str, float | None, str | None, str | None, bool]],
    steps: list[str],
    *,
    starred: bool = False,
) -> Recipe:
    return Recipe(
        id=mock_id(f"recipe/{key}"),
        title=title,
        cuisine=Cuisine.CHINESE,
        total_minutes=minutes,
        difficulty=1,
        servings=2,
        taste_tags=tags,
        starred=starred,
        base_recipe_id=None,
        variant_label=None,
        active_minutes=minutes - 5,
        equipment=[Equipment.STOVE],
        ingredients=[
            RecipeIngredient(
                ingredient_id=INGREDIENTS[name].id,
                name=name,
                quantity=quantity,
                unit=unit,
                coarse_amount=coarse,
                essential=essential,
                prep_note=None,
            )
            for name, quantity, unit, coarse, essential in ingredients
        ],
        steps=steps,
    )


RECIPES: dict[str, Recipe] = {
    str(r.id): r
    for r in [
        _recipe(
            "tomato-egg",
            "Tomato and egg stir-fry",
            15,
            [TasteTag.LIGHT, TasteTag.HIGH_PROTEIN],
            [
                ("egg", 3, "pcs", None, True),
                ("tomato", 2, "pcs", None, True),
                ("garlic", None, None, "2 cloves", False),
                ("soy sauce", None, None, "a splash", False),
            ],
            [
                "Beat the eggs; cut the tomatoes into wedges.",
                "Scramble the eggs until just set, then set aside.",
                "Fry the garlic and tomatoes until soft, return the eggs and season.",
            ],
            starred=True,
        ),
        _recipe(
            "cabbage-tofu",
            "Braised cabbage with tofu",
            25,
            [TasteTag.LIGHT, TasteTag.LOW_OIL, TasteTag.VEGETABLE_RICH],
            [
                ("cabbage", None, None, "half a cabbage", True),
                ("firm tofu", 1, "pack", None, True),
                ("garlic", None, None, "3 cloves", False),
                ("soy sauce", None, None, "1 tablespoon", False),
            ],
            [
                "Cut the cabbage into wide strips and the tofu into cubes.",
                "Fry the garlic, add the cabbage and a little water, cover for 8 minutes.",
                "Add the tofu and soy sauce and simmer for 5 minutes.",
            ],
        ),
        _recipe(
            "soy-chicken",
            "Soy-braised chicken with rice",
            40,
            [TasteTag.RICH, TasteTag.HIGH_PROTEIN],
            [
                ("chicken thigh", None, None, "2 thighs", True),
                ("rice", None, None, "1 cup", True),
                ("garlic", None, None, "4 cloves", False),
                ("soy sauce", None, None, "3 tablespoons", False),
            ],
            [
                "Start the rice.",
                "Brown the chicken, add garlic, soy sauce and water to half cover.",
                "Simmer covered for 25 minutes, turning once.",
            ],
        ),
    ]
}


def recipe(key: str) -> Recipe:
    return RECIPES[str(mock_id(f"recipe/{key}"))]


def summary(key: str) -> RecipeSummary:
    return RecipeSummary.model_validate(recipe(key), from_attributes=True)


def suggestion(
    key: str = "tomato-egg",
    *,
    people: int = 2,
    has_previous: bool = False,
    tags: list[CookTag] | None = None,
    max_minutes: int | None = None,
    max_difficulty: int | None = None,
) -> Suggestion:
    """`tomato-egg` is ready to cook; `soy-chicken` shows both kinds of check."""
    status = {
        "egg": IngredientStatus.HAVE,
        "tomato": IngredientStatus.HAVE,
        "cabbage": IngredientStatus.LOW,
        "firm tofu": IngredientStatus.HAVE,
        "garlic": IngredientStatus.HAVE,
        "chicken thigh": IngredientStatus.CHECK,
        "rice": IngredientStatus.UNKNOWN,
        "soy sauce": IngredientStatus.STAPLE,
    }
    r = recipe(key)
    scale = people / r.servings

    def amount(ing: RecipeIngredient) -> str:
        if ing.quantity is None:
            return ing.coarse_amount or ""
        return f"{ing.quantity * scale:g} {ing.unit or ''}".strip()

    lines = [
        SuggestionIngredient(
            ingredient_id=ing.ingredient_id,
            name=ing.name,
            amount=amount(ing),
            essential=ing.essential,
            status=status[ing.name],
        )
        for ing in r.ingredients
    ]
    return Suggestion(
        session_id=COOK_SESSION_ID,
        recipe=summary(key),
        people=people,
        ingredients=lines,
        needs_check=[
            StockCheck(ingredient_id=line.ingredient_id, name=line.name)
            for line in lines
            if line.essential and line.status == IngredientStatus.UNKNOWN
        ],
        freshness_check=[
            FreshnessCheck(item=item("chicken"), reason=FreshnessReason.PAST_ESTIMATE)
            for line in lines
            if line.status == IngredientStatus.CHECK
        ],
        has_previous=has_previous,
        applied_constraints=AppliedConstraints(
            tags=tags or [], max_minutes=max_minutes, max_difficulty=max_difficulty
        ),
    )


def cook_record(status: CookRecordStatus = CookRecordStatus.SELECTED) -> CookRecord:
    return CookRecord(
        id=COOK_RECORD_ID,
        session_id=COOK_SESSION_ID,
        recipe=summary("tomato-egg"),
        people=2,
        status=status,
        rating=None,
        proposed_consumption=[
            ProposedConsumption(item=item("egg-old"), proposed_count=0, proposed_outcome=None),
            ProposedConsumption(item=item("egg-new"), proposed_count=5, proposed_outcome=None),
            ProposedConsumption(item=item("tomato"), proposed_count=1, proposed_outcome=None),
            ProposedConsumption(
                item=item("garlic"),
                proposed_count=None,
                proposed_outcome=ConsumptionOutcome.STILL_ENOUGH,
            ),
        ],
    )


def basket(
    *,
    people: int = 2,
    meals: int = 3,
    tags: list[ShopTag] | None = None,
    status: BasketStatus = BasketStatus.SUGGESTED,
) -> Basket:
    def line(name: str, amount: str, packs: int | None, check: bool = False) -> BasketItem:
        ing = INGREDIENTS[name]
        return BasketItem(
            id=mock_id(f"basket-item/{name}"),
            ingredient_id=ing.id,
            name=name,
            category=ing.category,
            amount=amount,
            suggested_packs=packs,
            needs_check=check,
        )

    return Basket(
        id=BASKET_ID,
        session_id=SHOP_SESSION_ID,
        people=people,
        meals=meals,
        status=status,
        applied_tags=tags or [],
        planned_meals=[summary(k) for k in ("tomato-egg", "cabbage-tofu", "soy-chicken")][:meals],
        items=[
            line("cabbage", "1 head", None),
            line("firm tofu", "1 pack", 1),
            line("chicken thigh", "1 tray", None),
            line("rice", "1 bag", None, check=True),
        ],
    )
