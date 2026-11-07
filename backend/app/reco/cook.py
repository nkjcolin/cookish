"""Pure Cook filtering, scoring, selection and accumulating adjustments.

No I/O, global sessions, random tie-breaking, clock reads or database access.
Callers load a household-scoped snapshot and persist the returned session.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from app.clock import SINGAPORE
from app.reco.config import DEFAULT_CONFIG, ScoringConfig
from app.reco.inventory import assess_ingredients
from app.reco.models import (
    Candidate,
    CatalogIngredient,
    CookSession,
    HardConstraints,
    Recommendation,
    ScoreBreakdown,
    ScoredRecipe,
)
from app.reco.protein import protein_features
from app.schemas.common import TasteTag
from app.schemas.cook import (
    AppliedConstraints,
    CookAdjust,
    CookSessionConstraints,
    CookTag,
    IngredientStatus,
    StockCheck,
    Suggestion,
    SuggestionIngredient,
)
from app.schemas.identity import Preferences
from app.schemas.inventory import InventoryItem
from app.schemas.recipes import RecipeSummary


def new_session(
    prefs: Preferences,
    people: int | None = None,
    *,
    strict_max_minutes: int | None = None,
    constraints: CookSessionConstraints | None = None,
) -> CookSession:
    session = CookSession(
        people=prefs.last_cook_people if people is None else people,
        max_minutes=prefs.max_cook_minutes,
        max_difficulty=prefs.max_difficulty,
        strict_max_minutes=strict_max_minutes,
    )
    if constraints is None:
        return session
    tags = tuple(dict.fromkeys(constraints.tags))
    required = set()
    if CookTag.LESS_OIL in tags:
        required.add(TasteTag.LOW_OIL)
    if CookTag.MORE_VEGETABLES in tags:
        required.add(TasteTag.VEGETABLE_RICH)
    return replace(
        session,
        max_minutes=constraints.max_minutes,
        max_difficulty=constraints.max_difficulty,
        tags=tags,
        required_tags=frozenset(required),
        boosted_tags=(
            frozenset({TasteTag.HIGH_PROTEIN}) if CookTag.MORE_PROTEIN in tags else frozenset()
        ),
    )


def filter_recipes(
    recipes: Sequence[Candidate],
    hard_constraints: HardConstraints,
    catalogue: Mapping[UUID, CatalogIngredient],
) -> list[Candidate]:
    """Fail closed for missing metadata, including optional ingredients."""
    result = []
    for recipe in recipes:
        if not recipe.reviewed or not set(recipe.equipment) <= hard_constraints.equipment:
            continue
        if (
            hard_constraints.strict_max_minutes is not None
            and recipe.total_minutes > hard_constraints.strict_max_minutes
        ):
            continue
        metadata = [catalogue.get(line.ingredient_id) for line in recipe.ingredients]
        if any(
            meta is None
            or meta.id != line.ingredient_id
            or bool(meta.allergens & hard_constraints.allergens)
            or not hard_constraints.diets <= meta.diet_flags
            for line, meta in zip(recipe.ingredients, metadata, strict=True)
        ):
            continue
        result.append(recipe)
    return result


def recipe_features(recipe: Candidate) -> frozenset[str]:
    return frozenset(
        [f"tag:{tag.value}" for tag in recipe.taste_tags] + [f"cuisine:{recipe.cuisine.value}"]
    ) | protein_features(recipe)


def _similarity(left: Candidate, right: Candidate) -> float:
    def features(recipe):
        return {f"ingredient:{item.ingredient_id}" for item in recipe.ingredients} | {
            f"tag:{tag}" for tag in recipe.taste_tags
        }

    a, b = features(left), features(right)
    return len(a & b) / len(a | b)


def score_recipe(
    recipe: Candidate,
    inventory: Sequence[InventoryItem],
    prefs: Preferences,
    session: CookSession,
    catalogue: Mapping[UUID, CatalogIngredient],
    *,
    as_of: datetime,
    taste_weights: Mapping[str, float] | None = None,
    anchor: Candidate | None = None,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> ScoredRecipe:
    """Score a candidate; call filter_recipes before treating it as eligible."""
    learned = taste_weights or {}
    if any(not math.isfinite(value) for value in learned.values()):
        raise ValueError("taste weights must be finite")
    ingredients = assess_ingredients(
        recipe, inventory, catalogue, session.people, as_of=as_of, config=config
    )
    non_staples = [item for item in ingredients if not item.is_staple]
    denominator = max(1, len(non_staples))
    coverage = (
        sum(
            1.0
            if item.status == IngredientStatus.HAVE
            else config.low_coverage
            if item.status == IngredientStatus.LOW
            else 0.0
            for item in non_staples
        )
        / denominator
    )
    today = as_of.astimezone(SINGAPORE).date()
    urgency = 0.0
    for item in non_staples:
        batch_urgencies = []
        for batch in item.usable_batches:
            if batch.est_use_first_date is not None:
                days = (batch.est_use_first_date - today).days
                if days >= 0:
                    batch_urgencies.append(max(0.0, 1 - days / config.urgency_window_days))
        urgency += max(batch_urgencies, default=0.0)
    urgency /= denominator
    preference = sum(learned.get(feature, 0.0) for feature in sorted(recipe_features(recipe)))
    preference += config.cuisine_bonus * (recipe.cuisine in prefs.cuisines)
    preference += config.star_bonus * recipe.starred
    preference += config.boosted_tag_bonus * len(session.boosted_tags & set(recipe.taste_tags))
    preference -= config.disliked_ingredient_penalty * len(
        {item.ingredient_id for item in recipe.ingredients} & set(prefs.disliked_ingredient_ids)
    )
    effort = 0.5 * recipe.total_minutes / max(
        1, prefs.max_cook_minutes or config.default_minutes
    ) + 0.5 * recipe.difficulty / max(1, prefs.max_difficulty or config.default_difficulty)
    repetition = float(
        (recipe.id in session.shown_recipe_ids) + (recipe.id in session.recent_recipe_ids)
    )
    uncertainty = float(
        sum(
            item.essential and item.status in {IngredientStatus.UNKNOWN, IngredientStatus.CHECK}
            for item in ingredients
        )
    )
    similarity = _similarity(recipe, anchor) if anchor is not None else 0.0
    preferred_variant = (
        anchor is not None
        and recipe.id != anchor.id
        and (recipe.base_recipe_id or recipe.id) == (anchor.base_recipe_id or anchor.id)
        and session.boosted_tags <= set(recipe.taste_tags)
    )
    terms = {
        "coverage": config.coverage * coverage,
        "expiry_urgency": config.expiry * urgency,
        "preference": config.preference * preference,
        "effort": -config.effort * effort,
        "repetition": -config.repetition * repetition,
        "unknown_essentials": -config.uncertainty * uncertainty,
        "similarity": config.similarity * similarity,
    }
    return ScoredRecipe(
        recipe,
        ingredients,
        ScoreBreakdown(
            coverage, urgency, preference, effort, repetition, uncertainty, similarity, terms
        ),
        preferred_variant,
    )


def _fits(recipe: Candidate, session: CookSession, relaxed: tuple[str, ...] = ()) -> bool:
    return (
        recipe.id not in session.skipped_recipe_ids
        and (
            "max_minutes" in relaxed
            or session.max_minutes is None
            or recipe.total_minutes <= session.max_minutes
        )
        and (session.max_difficulty is None or recipe.difficulty <= session.max_difficulty)
        and ("tags" in relaxed or session.required_tags <= set(recipe.taste_tags))
    )


def suggest(
    recipes: Sequence[Candidate],
    inventory: Sequence[InventoryItem],
    prefs: Preferences,
    session: CookSession,
    catalogue: Mapping[UUID, CatalogIngredient],
    *,
    as_of: datetime,
    taste_weights: Mapping[str, float] | None = None,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> Recommendation:
    if len({recipe.id for recipe in recipes}) != len(recipes):
        raise ValueError("duplicate recipe IDs")
    hard = HardConstraints.from_preferences(prefs, session.strict_max_minutes)
    safe = filter_recipes(recipes, hard, catalogue)
    eligible = [recipe for recipe in safe if _fits(recipe, session)]
    if not eligible:
        # Suggest only removals that actually produce a result after the hard gate.
        for relaxed in (("max_minutes",), ("tags",), ("max_minutes", "tags")):
            if any(_fits(recipe, session, relaxed) for recipe in safe):
                return Recommendation(None, session, relaxable=relaxed)
        return Recommendation(None, session)
    anchor = next((r for r in recipes if r.id == session.anchor_recipe_id), None)
    scored = [
        score_recipe(
            recipe,
            inventory,
            prefs,
            session,
            catalogue,
            as_of=as_of,
            taste_weights=taste_weights,
            anchor=anchor,
            config=config,
        )
        for recipe in eligible
    ]
    stocked = [
        candidate
        for candidate in scored
        if not any(
            item.essential and item.status == IngredientStatus.MISSING
            for item in candidate.ingredients
        )
    ]
    candidates = stocked or scored
    selected = min(
        candidates,
        key=lambda candidate: (
            not candidate.preferred_variant,
            -candidate.score.total,
            str(candidate.recipe.id),
        ),
    )
    # Anchor preference applies to this reranking only, not every later "Not this".
    next_session = replace(
        session,
        shown_recipe_ids=(*session.shown_recipe_ids, selected.recipe.id),
        current_recipe_id=selected.recipe.id,
        anchor_recipe_id=None,
    )
    return Recommendation(selected, next_session, missing_essential_fallback=not stocked)


def _tighten(existing: int | None, requested: int) -> int:
    return requested if existing is None else min(existing, requested)


def adjust(session: CookSession, patch: CookAdjust | CookTag, current: Candidate) -> CookSession:
    """Apply a patch without altering hard constraints, history or input objects."""
    if session.current_recipe_id != current.id:
        raise ValueError("adjustment must refer to the session's current recipe")
    if isinstance(patch, CookTag):
        patch = CookAdjust(tags=[patch])
    minutes, difficulty = session.max_minutes, session.max_difficulty
    required, boosted = set(session.required_tags), set(session.boosted_tags)
    tags = list(session.tags)
    if patch.max_minutes is not None:
        minutes = _tighten(minutes, patch.max_minutes)
    if patch.max_difficulty is not None:
        difficulty = _tighten(difficulty, patch.max_difficulty)
    # Repeated tags within one request apply once. Repeated requests require the
    # service's idempotency policy; a new deliberate tap can tighten time again.
    for tag in dict.fromkeys(patch.tags):
        if tag not in tags:
            tags.append(tag)
        if tag == CookTag.QUICKER:
            minutes = _tighten(minutes, max(0, current.total_minutes - 10))
        elif tag == CookTag.EASIER:
            difficulty = _tighten(difficulty, max(0, current.difficulty - 1))
        elif tag == CookTag.LESS_OIL:
            required.add(TasteTag.LOW_OIL)
        elif tag == CookTag.MORE_VEGETABLES:
            required.add(TasteTag.VEGETABLE_RICH)
        elif tag == CookTag.MORE_PROTEIN:
            boosted.add(TasteTag.HIGH_PROTEIN)
    return replace(
        session,
        people=session.people if patch.people is None else patch.people,
        max_minutes=minutes,
        max_difficulty=difficulty,
        tags=tuple(tags),
        required_tags=frozenset(required),
        boosted_tags=frozenset(boosted),
        anchor_recipe_id=(
            current.id
            if patch.tags or patch.max_minutes is not None or patch.max_difficulty is not None
            else None
        ),
    )


def fulfils_nudge(
    tag: CookTag, session: CookSession, current: Candidate, selected: Candidate | None
) -> bool:
    """Whether the actual winner meaningfully delivers a new requested adjustment."""
    if selected is None or selected.id == current.id:
        return False
    if tag == CookTag.QUICKER:
        return selected.total_minutes <= current.total_minutes - 10
    if tag == CookTag.EASIER:
        return selected.difficulty <= current.difficulty - 1
    target = {
        CookTag.LESS_OIL: TasteTag.LOW_OIL,
        CookTag.MORE_PROTEIN: TasteTag.HIGH_PROTEIN,
        CookTag.MORE_VEGETABLES: TasteTag.VEGETABLE_RICH,
    }[tag]
    if (
        tag in session.tags
        or target in current.taste_tags
        or target in session.required_tags
        or target in session.boosted_tags
    ):
        return False
    return target in selected.taste_tags


def available_nudges(
    recipes: Sequence[Candidate],
    inventory: Sequence[InventoryItem],
    prefs: Preferences,
    session: CookSession,
    catalogue: Mapping[UUID, CatalogIngredient],
    *,
    as_of: datetime,
    taste_weights: Mapping[str, float] | None = None,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> tuple[CookTag, ...]:
    """Dry-run each nudge against the exact ranking snapshot without saving anything.

    Availability describes the actual selector, including stock fallback and
    history penalties. More protein remains a boost, not an extra hard filter.
    """
    current = next((recipe for recipe in recipes if recipe.id == session.current_recipe_id), None)
    if current is None:
        return ()
    available = []
    for tag in CookTag:
        result = suggest(
            recipes,
            inventory,
            prefs,
            adjust(session, tag, current),
            catalogue,
            as_of=as_of,
            taste_weights=taste_weights,
            config=config,
        )
        winner = result.selected.recipe if result.selected else None
        if fulfils_nudge(tag, session, current, winner):
            available.append(tag)
    return tuple(available)


def skip_current(session: CookSession) -> CookSession:
    if session.current_recipe_id is None:
        raise ValueError("session has no current recipe to skip")
    return replace(
        session,
        skipped_recipe_ids=session.skipped_recipe_ids | {session.current_recipe_id},
        anchor_recipe_id=None,
    )


def to_suggestion(result: Recommendation, session_id: UUID) -> Suggestion:
    """Build the existing API shape; the service maps no-result to ApiError."""
    if result.selected is None:
        raise ValueError("no result; the service must return NO_RESULT with relaxable")
    selected, session = result.selected, result.session
    return Suggestion(
        session_id=session_id,
        recipe=RecipeSummary.model_validate(selected.recipe.model_dump()),
        people=session.people,
        ingredients=[
            SuggestionIngredient(
                ingredient_id=item.ingredient_id,
                name=item.name,
                amount=item.amount,
                essential=item.essential,
                status=item.status,
                countable=item.known_quantity is not None,
            )
            for item in selected.ingredients
        ],
        needs_check=[
            StockCheck(item=batch) for item in selected.ingredients for batch in item.needs_check
        ],
        freshness_check=[check for item in selected.ingredients for check in item.freshness_check],
        has_previous=len(session.shown_recipe_ids) > 1,
        applied_constraints=AppliedConstraints(
            tags=list(session.tags),
            max_minutes=session.max_minutes,
            max_difficulty=session.max_difficulty,
        ),
    )
