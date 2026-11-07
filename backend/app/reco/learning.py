"""Deterministic learning from confirmed meals, with replaceable evidence.

The service persists this evidence and serializes updates per household. Pure
retry handling here is not a substitute for a transaction/revision check.
"""

from dataclasses import dataclass, replace
from uuid import UUID

from app.reco.config import DEFAULT_LEARNING_CONFIG, LearningConfig
from app.reco.cook import recipe_features
from app.reco.models import Candidate
from app.schemas.cook import CookRecordStatus, Rating


@dataclass(frozen=True)
class MealEvidence:
    record_id: UUID
    recipe_id: UUID
    features: frozenset[str]
    rating: Rating | None


@dataclass(frozen=True)
class LearningState:
    household_id: UUID
    # Ordered by first confirmed cooking, not by the latest feedback request.
    meals: tuple[MealEvidence, ...] = ()
    config: LearningConfig = DEFAULT_LEARNING_CONFIG

    def __post_init__(self):
        if len({meal.record_id for meal in self.meals}) != len(self.meals):
            raise ValueError("duplicate cook record evidence")


def learn(
    state: LearningState,
    *,
    household_id: UUID,
    record_id: UUID,
    recipe: Candidate,
    status: CookRecordStatus,
    rating: Rating | None = None,
) -> LearningState:
    """None means a cooking confirmation; a rating replaces that meal's evidence.

    Replayed confirmations never erase a subsequent rating. The service must
    load the authenticated household's record and enforce its current status.
    """
    if household_id != state.household_id:
        raise ValueError("learning state belongs to a different household")
    status = CookRecordStatus(status)
    rating = Rating(rating) if rating is not None else None
    if status != CookRecordStatus.CONFIRMED:
        if rating is not None:
            raise ValueError("only a confirmed cooked meal can be rated")
        return state
    features = recipe_features(recipe)
    evidence = MealEvidence(record_id, recipe.id, features, rating)
    for index, previous in enumerate(state.meals):
        if previous.record_id != record_id:
            continue
        # Before protein features were introduced, persisted evidence contained
        # only cuisine/tags. Keep that frozen evidence on edits and retries;
        # never retroactively award protein weights to an already counted meal.
        # Evidence that already includes protein must still match exactly.
        legacy_features = frozenset(f for f in features if not f.startswith("protein:"))
        if previous.recipe_id != recipe.id or previous.features not in (
            features,
            legacy_features,
        ):
            raise ValueError("a cook record's recipe/features cannot change")
        if rating is None or rating == previous.rating:
            return state
        evidence = replace(previous, rating=rating)
        return replace(state, meals=(*state.meals[:index], evidence, *state.meals[index + 1 :]))
    return replace(state, meals=(*state.meals, evidence))


def taste_weights(state: LearningState) -> dict[str, float]:
    """Replay current evidence so changing a saturated rating is reversible.

    Do not subtract an old delta from an already clipped weight: information
    lost at the bound would make retries and edited ratings give wrong results.
    """
    weights: dict[str, float] = {}
    config = state.config
    for meal in state.meals:
        multiplier = {
            None: 0.25,
            Rating.LIKE: 1.0,
            Rating.MAYBE: 0.0,
            Rating.DISLIKE: -1.0,
        }[meal.rating]
        if multiplier == 0:
            continue
        for feature in sorted(meal.features):
            weights[feature] = min(
                config.upper,
                max(config.lower, weights.get(feature, 0.0) + multiplier * config.step),
            )
    return {feature: value for feature, value in sorted(weights.items()) if value != 0}
