"""Role 5 recipe reads and household stars using the existing Role 2 models."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.auth import CurrentUser
from app.db import models as m
from app.errors import ApiError, ErrorCode
from app.schemas.recipes import Recipe, StarResult
from app.services.recommendation_inputs import ingredient_metadata, recipe_candidate


def _reviewed_recipe(session: Session, recipe_id: UUID) -> m.Recipe:
    row = session.scalar(
        select(m.Recipe).where(m.Recipe.id == recipe_id, m.Recipe.reviewed.is_(True))
    )
    if row is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Recipe not found")
    return row


def _latest_star(session: Session, household_id: UUID, recipe_id: UUID):
    # Match the catalogue input reader's ordering, including legacy timestamp ties.
    return session.scalar(
        select(m.RecipeFeedback)
        .where(
            m.RecipeFeedback.household_id == household_id,
            m.RecipeFeedback.recipe_id == recipe_id,
            m.RecipeFeedback.signal.in_(("starred", "unstarred")),
        )
        .order_by(m.RecipeFeedback.created_at.desc(), m.RecipeFeedback.id.desc())
        .limit(1)
    )


def read_recipe(session: Session, household_id: UUID, recipe_id: UUID) -> Recipe:
    row = _reviewed_recipe(session, recipe_id)
    ingredients = session.execute(
        select(m.RecipeIngredient, m.Ingredient)
        .join(m.Ingredient, m.Ingredient.id == m.RecipeIngredient.ingredient_id)
        .where(m.RecipeIngredient.recipe_id == recipe_id)
        .order_by(m.RecipeIngredient.ingredient_id)
    ).all()
    latest = _latest_star(session, household_id, recipe_id)
    candidate = recipe_candidate(
        row,
        [line for line, _ in ingredients],
        {ingredient.id: ingredient_metadata(ingredient) for _, ingredient in ingredients},
        latest is not None and latest.signal == "starred",
    )
    return Recipe.model_validate(candidate.model_dump())


def save_star(session: Session, user: CurrentUser, recipe_id: UUID, starred: bool) -> StarResult:
    # A household row exists even before its first star. Serialize changes there,
    # using NO KEY UPDATE so ordinary FK checks can still take KEY SHARE locks.
    household = session.scalar(
        select(m.Household.id)
        .where(m.Household.id == user.household_id)
        .with_for_update(key_share=True)
    )
    if household is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Household not found")
    _reviewed_recipe(session, recipe_id)
    latest = _latest_star(session, user.household_id, recipe_id)
    current = latest is not None and latest.signal == "starred"
    if current != starred:
        # Transaction start times and equal/future legacy timestamps must not
        # make a later committed action sort behind the action it replaces.
        created_at = clock.now()
        if latest is not None:
            created_at = max(created_at, latest.created_at + timedelta(microseconds=1))
        session.add(
            m.RecipeFeedback(
                household_id=user.household_id,
                user_id=user.user_id,
                recipe_id=recipe_id,
                signal="starred" if starred else "unstarred",
                created_at=created_at,
            )
        )
    return StarResult(recipe_id=recipe_id, starred=starred)
