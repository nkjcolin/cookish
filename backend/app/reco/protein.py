"""Explicit protein-source features for the reviewed ingredient catalogue.

The UUIDs and names below come from seed/ingredients.csv. This is a small,
reviewable culinary mapping, not a nutrient calculation. Only essential recipe
lines contribute: optional additions and condiments cannot label a meal's main
protein. A mixed dish can carry more than one category, once per category.

Unknown IDs are left unclassified. Names, titles, aliases and dietary flags are
never used to guess a category. Adding an ingredient requires reviewing this map.
"""

from types import MappingProxyType
from uuid import UUID

from app.reco.models import Candidate

# ingredient UUID -> (canonical name for review, feature category)
PROTEIN_INGREDIENTS = MappingProxyType(
    {
        UUID("4d2b490d-740c-44da-859a-e78d578c7691"): ("chicken thigh", "poultry"),
        UUID("4ec6f234-be95-4bf6-a25c-53d8bf6dc9f3"): ("egg", "egg"),
        UUID("3524a936-adb8-4288-9416-a710e209a9a9"): ("firm tofu", "soy"),
        UUID("ca4c852e-630d-4677-b976-4a9f46fcf594"): ("tempeh", "soy"),
        UUID("103e91ce-f810-493f-b9db-4a4d8e3d3bff"): ("canned chickpea", "legume"),
        UUID("6ba08b2f-d19d-4a0d-b68f-f4e2364c1566"): ("red lentil", "legume"),
        UUID("c85abe69-7e4f-49dc-90fc-ee20f029b021"): ("prawn", "shellfish"),
        UUID("47ea5a95-1021-474e-a545-6cb82510ce1a"): ("cod fillet", "fish"),
    }
)


def protein_features(recipe: Candidate) -> frozenset[str]:
    return frozenset(
        f"protein:{PROTEIN_INGREDIENTS[line.ingredient_id][1]}"
        for line in recipe.ingredients
        if line.essential and line.ingredient_id in PROTEIN_INGREDIENTS
    )
