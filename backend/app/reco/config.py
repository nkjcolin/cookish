"""Initial, hand-set Cook scoring parameters; not fitted evaluation results."""

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
