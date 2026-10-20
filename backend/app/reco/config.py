"""Initial, hand-set recommendation and learning parameters; not fitted results."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringConfig:
    coverage: float = 3.0
    expiry: float = 1.0
    preference: float = 1.0
    effort: float = 0.5
    repetition: float = 1.0
    uncertainty: float = 1.0
    similarity: float = 0.5
    cuisine_bonus: float = 0.5
    star_bonus: float = 1.0
    disliked_ingredient_penalty: float = 1.0
    boosted_tag_bonus: float = 2.0
    low_coverage: float = 0.5
    urgency_window_days: int = 4
    stale_confirmation_days: int = 14
    default_minutes: int = 60
    default_difficulty: int = 3


DEFAULT_CONFIG = ScoringConfig()


@dataclass(frozen=True)
class ShopConfig:
    candidate_limit: int = 20
    beam_width: int = 10
    sharing: float = 0.5
    at_home: float = 1.0
    variety: float = 0.5
    surplus: float = 0.5
    vegetables: float = 2.0
    longer_lasting: float = 1.0
    shelf_life_horizon_days: int = 30

    def __post_init__(self):
        for value in (self.candidate_limit, self.beam_width, self.shelf_life_horizon_days):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("search limits and shelf-life horizon must be positive integers")
        for value in (
            self.sharing,
            self.at_home,
            self.variety,
            self.surplus,
            self.vegetables,
            self.longer_lasting,
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Shop weights must be finite and nonnegative")


@dataclass(frozen=True)
class LearningConfig:
    step: float = 0.25
    lower: float = -2.0
    upper: float = 2.0

    def __post_init__(self):
        if not all(math.isfinite(value) for value in (self.step, self.lower, self.upper)):
            raise ValueError("learning parameters must be finite")
        if self.step <= 0 or not self.lower < 0 < self.upper:
            raise ValueError("step must be positive and learning bounds must contain zero")


DEFAULT_SHOP_CONFIG = ShopConfig()
DEFAULT_LEARNING_CONFIG = LearningConfig()
