"""Bounded meal planning and conservative shopping, with no persistence or prices."""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from math import ceil
from uuid import UUID, uuid5

from app.reco.config import DEFAULT_CONFIG, DEFAULT_SHOP_CONFIG, ScoringConfig, ShopConfig
from app.reco.cook import filter_recipes, score_recipe
from app.reco.inventory import assess_ingredients, display_amount
from app.reco.models import Candidate, CatalogIngredient, CookSession, HardConstraints
from app.reco.shop_models import Purchase, PurchaseSpec, ShoppingList, ShopPlan, ShopSession
from app.schemas.common import TasteTag
from app.schemas.cook import IngredientStatus
from app.schemas.identity import Preferences
from app.schemas.inventory import InventoryItem
from app.schemas.recipes import RecipeIngredient, RecipeSummary
from app.schemas.shop import Basket, BasketItem, BasketStatus, ShopAdjust, ShopTag


def new_shop_session(
    prefs: Preferences,
    people: int | None = None,
    meals: int | None = None,
    *,
    strict_max_minutes: int | None = None,
) -> ShopSession:
    return ShopSession(
        people=prefs.last_shop_people if people is None else people,
        meals=prefs.last_shop_meals if meals is None else meals,
        strict_max_minutes=strict_max_minutes,
    )


def adjust_shop(session: ShopSession, patch: ShopAdjust) -> ShopSession:
    tags = tuple(dict.fromkeys((*session.tags, *patch.tags)))
    # An explicit meal count wins; each deliberate cover-more tap otherwise adds one.
    meals = session.meals if patch.meals is None else patch.meals
    if patch.meals is None and ShopTag.COVER_MORE_MEALS in patch.tags:
        meals = min(7, meals + 1)
    return replace(
        session,
        people=session.people if patch.people is None else patch.people,
        meals=meals,
        tags=tags,
    )


def _aggregate_ingredients(meals: Sequence[Candidate], people: int):
    """Scale and combine requirements without inventing conversions between units."""
    grouped = defaultdict(list)
    for meal in meals:
        for line in meal.ingredients:
            grouped[line.ingredient_id].append((meal, line))
    lines, exact_needs = [], {}
    for ingredient_id, occurrences in sorted(grouped.items(), key=lambda item: str(item[0])):
        units = {line.unit for _, line in occurrences}
        numeric = len(units) == 1 and all(line.quantity is not None for _, line in occurrences)
        quantity = (
            sum(Fraction(str(line.quantity)) * people / meal.servings for meal, line in occurrences)
            if numeric
            else None
        )
        exact_needs[ingredient_id] = quantity
        lines.append(
            RecipeIngredient(
                ingredient_id=ingredient_id,
                name=occurrences[0][1].name,
                quantity=float(quantity) if quantity is not None else None,
                unit=occurrences[0][1].unit if numeric else None,
                coarse_amount=None
                if numeric
                else "; ".join(
                    display_amount(line, people / meal.servings, people, meal.servings)
                    for meal, line in occurrences
                ),
                essential=any(line.essential for _, line in occurrences),
                prep_note=None,
            )
        )
    return lines, exact_needs


def shopping_list(
    meals: Sequence[Candidate],
    inventory: Sequence[InventoryItem],
    catalogue: Mapping[UUID, CatalogIngredient],
    purchases: Mapping[UUID, PurchaseSpec],
    people: int,
    *,
    as_of: datetime,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> ShoppingList:
    """Aggregate the whole plan before subtracting stock, never once per meal."""
    if not meals:
        return ShoppingList((), 0)
    lines, exact_needs = _aggregate_ingredients(meals, people)
    if any(line.ingredient_id not in purchases for line in lines):
        raise ValueError("purchase metadata is required for every planned ingredient")
    aggregate = Candidate.model_validate(
        {**meals[0].model_dump(), "servings": people, "ingredients": lines}
    )
    # Shop requires recent confirmation for all stock it omits, including pantry items.
    shop_catalogue = {
        key: meta.model_copy(update={"perishable": True}) for key, meta in catalogue.items()
    }
    assessments = assess_ingredients(
        aggregate, inventory, shop_catalogue, people, as_of=as_of, config=config
    )
    result, at_home = [], 0
    for line, assessment in zip(lines, assessments, strict=True):
        ingredient_id = line.ingredient_id
        spec, meta = purchases[ingredient_id], catalogue[ingredient_id]
        if not spec.buyable:
            continue
        # Even a second uncertain batch stays visible when another batch is enough.
        one_ingredient = aggregate.model_copy(update={"ingredients": [line]})
        uncertain = any(
            assess_ingredients(
                one_ingredient, [batch], shop_catalogue, people, as_of=as_of, config=config
            )[0].status
            in {IngredientStatus.UNKNOWN, IngredientStatus.CHECK}
            for batch in inventory
            if batch.ingredient_id == ingredient_id
        )
        if assessment.usable_batches:
            at_home += 1
        if assessment.status in {IngredientStatus.HAVE, IngredientStatus.STAPLE} and not uncertain:
            continue
        packs, surplus = None, 0.0
        amount = assessment.amount
        if meta.countable:
            quantity = exact_needs[ingredient_id]
            compatible_pack = (
                quantity is not None
                and spec.purchase_unit_size is not None
                and spec.purchase_unit_measure == line.unit
            )
            if compatible_pack:
                known = sum(Fraction(str(batch.count)) for batch in assessment.usable_batches)
                deficit = max(Fraction(0), quantity - known)
                pack_size = Fraction(str(spec.purchase_unit_size))
                needed_packs = ceil(deficit / pack_size)
                surplus = float(needed_packs - deficit / pack_size)
                if needed_packs == 0:
                    amount = "Confirmed stock covers the plan; check the other stock"
                elif needed_packs > 50:
                    # Existing confirmation schema allows at most 50 packs per line.
                    uncertain = True
                    amount = (
                        f"{needed_packs} × {spec.purchase_unit}; split purchase before confirming"
                    )
                else:
                    packs = needed_packs
                    amount = (
                        f"{packs} × {spec.purchase_unit} "
                        f"({spec.purchase_unit_size:g} {spec.purchase_unit_measure} each)"
                    )
            else:
                uncertain = True
                amount = f"{amount}; check quantity and purchase units"
        else:
            amount = f"{amount} for the planned meals; buy as needed"
        if uncertain:
            amount = f"Check at home — {amount}"
        result.append(
            Purchase(
                ingredient_id, meta.canonical_name, spec.category, amount, packs, uncertain, surplus
            )
        )
    return ShoppingList(tuple(result), at_home)


def plan_shop(
    recipes: Sequence[Candidate],
    inventory: Sequence[InventoryItem],
    prefs: Preferences,
    session: ShopSession,
    catalogue: Mapping[UUID, CatalogIngredient],
    purchases: Mapping[UUID, PurchaseSpec],
    *,
    as_of: datetime,
    taste_weights: Mapping[str, float] | None = None,
    config: ScoringConfig = DEFAULT_CONFIG,
    shop_config: ShopConfig = DEFAULT_SHOP_CONFIG,
) -> ShopPlan:
    if len({recipe.id for recipe in recipes}) != len(recipes):
        raise ValueError("duplicate recipe IDs")
    safe = filter_recipes(
        recipes, HardConstraints.from_preferences(prefs, session.strict_max_minutes), catalogue
    )
    if not safe:
        return ShopPlan(session, (), (), {})
    missing = {
        line.ingredient_id
        for meal in safe
        for line in meal.ingredients
        if line.ingredient_id not in purchases
    }
    if missing:
        raise ValueError("purchase metadata is required for every eligible ingredient")

    # Non-buyable essentials cannot be repaired by the shopping list. Use the
    # same recent-confirmation policy as shopping, including for pantry stock.
    shop_catalogue = {
        key: meta.model_copy(update={"perishable": True}) for key, meta in catalogue.items()
    }

    def can_supply_nonbuyable_essentials(meals):
        required = [
            meal.model_copy(
                update={
                    "ingredients": [
                        line
                        for line in meal.ingredients
                        if line.essential
                        and not catalogue[line.ingredient_id].is_staple
                        and not purchases[line.ingredient_id].buyable
                    ]
                }
            )
            for meal in meals
        ]
        lines, _ = _aggregate_ingredients(required, session.people)
        if not lines:
            return True
        aggregate = meals[0].model_copy(update={"servings": session.people, "ingredients": lines})
        return all(
            line.status == IngredientStatus.HAVE
            for line in assess_ingredients(
                aggregate, inventory, shop_catalogue, session.people, as_of=as_of, config=config
            )
        )

    safe = [meal for meal in safe if can_supply_nonbuyable_essentials((meal,))]
    if not safe:
        return ShopPlan(session, (), (), {})
    scores = {}
    for meal in safe:
        # Buyable stock, urgency and uncertainty do not affect preference ranking.
        scored = score_recipe(
            meal,
            (),
            prefs,
            CookSession(people=session.people),
            catalogue,
            as_of=as_of,
            taste_weights=taste_weights,
            config=config,
        )
        score = scored.score.terms["preference"] + scored.score.terms["effort"]
        if ShopTag.MORE_VEGETABLES in session.tags:
            score += shop_config.vegetables * (TasteTag.VEGETABLE_RICH in meal.taste_tags)
        if ShopTag.LONGER_LASTING in session.tags:
            lives = [
                min(
                    purchases[line.ingredient_id].shelf_life_days or 0,
                    shop_config.shelf_life_horizon_days,
                )
                / shop_config.shelf_life_horizon_days
                for line in meal.ingredients
                if not catalogue[line.ingredient_id].is_staple
            ]
            score += shop_config.longer_lasting * sum(lives) / max(1, len(lives))
        scores[meal.id] = score
    # Keep the best variant in each family so the top K is not filled with one dish.
    families, candidates = set(), []
    for meal in sorted(safe, key=lambda item: (-scores[item.id], str(item.id))):
        family = meal.base_recipe_id or meal.id
        if family not in families:
            families.add(family)
            candidates.append(meal)
        if len(candidates) == shop_config.candidate_limit:
            break
    target = min(session.meals, len(candidates))

    def evaluate(indices):
        chosen = tuple(candidates[index] for index in indices)
        shopping = shopping_list(
            chosen, inventory, catalogue, purchases, session.people, as_of=as_of, config=config
        )
        occurrence = Counter(
            line.ingredient_id
            for meal in chosen
            for line in meal.ingredients
            if not catalogue[line.ingredient_id].is_staple
        )
        terms = {
            "preference_and_effort": sum(scores[meal.id] for meal in chosen),
            "shared_ingredients": shop_config.sharing
            * sum(count - 1 for count in occurrence.values()),
            "confirmed_at_home": shop_config.at_home * shopping.confirmed_at_home,
            "cuisine_variety": shop_config.variety
            * max(0, len({meal.cuisine for meal in chosen}) - 1),
            "pack_surplus": -shop_config.surplus
            * sum(item.surplus_packs for item in shopping.items),
        }
        return ShopPlan(session, chosen, shopping.items, terms)

    # Individual meals may fit stock while their combined essential need does
    # not. Retry a smaller target if the bounded search cannot fill the plan.
    for size in range(target, 0, -1):
        beam = [((), ShopPlan(session, (), (), {}))]
        for depth in range(1, size + 1):
            expanded = {}
            for indices, _ in beam:
                # Increasing indices deduplicate combinations. Leave room to finish.
                start = indices[-1] + 1 if indices else 0
                for index in range(start, len(candidates) - (size - depth)):
                    combination = (*indices, index)
                    if can_supply_nonbuyable_essentials(tuple(candidates[i] for i in combination)):
                        expanded[combination] = evaluate(combination)
            if not expanded:
                break
            beam = sorted(
                expanded.items(),
                key=lambda entry: (
                    -entry[1].score,
                    tuple(str(meal.id) for meal in entry[1].planned_meals),
                ),
            )[: shop_config.beam_width]
        else:
            return beam[0][1]
    return ShopPlan(session, (), (), {})


def to_basket(plan: ShopPlan, session_id: UUID, basket_id: UUID) -> Basket:
    if not plan.planned_meals:
        raise ValueError("no eligible recipes; service must map to NO_RESULT with empty relaxable")
    return Basket(
        id=basket_id,
        session_id=session_id,
        people=plan.session.people,
        meals=len(plan.planned_meals),
        status=BasketStatus.SUGGESTED,
        applied_tags=list(plan.session.tags),
        planned_meals=[
            RecipeSummary.model_validate(meal.model_dump()) for meal in plan.planned_meals
        ],
        items=[
            BasketItem(
                id=uuid5(basket_id, str(item.ingredient_id)),
                ingredient_id=item.ingredient_id,
                name=item.name,
                category=item.category,
                amount=item.amount,
                suggested_packs=item.suggested_packs,
                needs_check=item.needs_check,
            )
            for item in plan.items
        ],
    )
