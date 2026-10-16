"""The ingredient catalogue, used to match what the model read to an ingredient id.

The catalogue is Role 2's backend/seed/ingredients.csv, bundled read-only with this Lambda
and loaded once per process. Only three columns are used here: `id`, `canonical_name`
and `aliases` (several names separated by "|"). Agree the exact format with Role 2.

INGREDIENTS_CSV overrides where the file is read from; on AWS, Role 3 sets it to the
bundled copy.
"""

import csv
import logging
import os
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "backend" / "seed" / "ingredients.csv"


def _key(name: str) -> str:
    return " ".join(name.lower().split())


@dataclass(frozen=True)
class Catalogue:
    names: dict[UUID, str] = field(default_factory=dict)  # id -> canonical name
    ids: dict[str, UUID] = field(default_factory=dict)  # any known name -> id

    def resolve(self, ingredient_id: UUID | None, display_name: str) -> UUID | None:
        """Keep the model's id only if it exists, else try the name, else null."""
        if ingredient_id in self.names:
            return ingredient_id
        return self.ids.get(_key(display_name))

    def prompt_lines(self) -> str:
        """The catalogue as `id | canonical_name` lines, for the prompt."""
        return "\n".join(f"{id} | {name}" for id, name in self.names.items())


def load(path: Path) -> Catalogue:
    catalogue = Catalogue()
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            ingredient_id = UUID(row["id"])
            catalogue.names[ingredient_id] = row["canonical_name"]
            for name in [row["canonical_name"], *(row.get("aliases") or "").split("|")]:
                if name.strip():
                    catalogue.ids[_key(name)] = ingredient_id
    return catalogue


@cache
def get_catalogue() -> Catalogue:
    path = Path(os.environ.get("INGREDIENTS_CSV", DEFAULT_PATH))
    if not path.exists():
        logger.warning("No ingredient catalogue at %s; every draft item is unmatched", path)
        return Catalogue()
    return load(path)
