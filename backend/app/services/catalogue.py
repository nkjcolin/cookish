"""Ingredient catalogue search. Role 2 owns this file.

The catalogue is global and read-only at runtime, so there is no household here. The search
looks at the canonical name and every alias ("kangkong" finds water spinach) and ranks:

1. the whole name or alias is what was typed,
2. a name or alias starts with it,
3. a name or alias contains it,
4. a name or alias is close to it (pg_trgm similarity), which forgives a typo.

Within one of those levels, a match on the real name beats a match on an alias, so "chicken"
finds chicken thigh before an egg whose alias is "chicken egg". One row comes back per
ingredient, best match first. Ties go to the shorter name, and among typos to the closest.
Typing nothing lists the catalogue alphabetically, so the "add item" box has something to show.
"""

import unicodedata
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import models as m
from app.db.session import transaction
from app.schemas.catalogue import Ingredient, IngredientSearchResult

# pg_trgm's own default: below this, two words are not treated as alike.
TYPO_THRESHOLD = 0.3
MAX_RESULTS = 100


def _name_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def match_exact_names(s: Session, names: Iterable[str]) -> dict[str, UUID]:
    """Resolve reviewed names only when one catalogue ingredient matches exactly.

    Search suggestions may be fuzzy; automatic inventory links must not be. Canonical
    names and aliases have equal standing here, so a collision between ingredients is
    left unresolved. Repeated aliases for the same ingredient are harmless.
    """
    keys = {name: _name_key(name) for name in names}
    wanted = {key for key in keys.values() if key}
    if not wanted:
        return {}
    matches: dict[str, set[UUID]] = {key: set() for key in wanted}
    # The small shared catalogue is read once per add request, never cached across seeds.
    rows = s.execute(select(m.Ingredient.id, m.Ingredient.canonical_name, m.Ingredient.aliases))
    for ingredient_id, canonical_name, aliases in rows:
        for label in (canonical_name, *(aliases or [])):
            key = _name_key(label)
            if key in matches:
                matches[key].add(ingredient_id)
    return {
        name: next(iter(matches[key]))
        for name, key in keys.items()
        if key in matches and len(matches[key]) == 1
    }


_SEARCH = text(
    r"""
    SELECT i.id, i.canonical_name, i.category, i.countable, i.default_unit,
           i.default_storage, i.is_staple
    FROM ingredients i
    CROSS JOIN LATERAL (
        SELECT min(
                   CASE
                       WHEN lower(n) = :q THEN 2
                       WHEN lower(n) LIKE :prefix ESCAPE '\' THEN 4
                       WHEN lower(n) LIKE :contains ESCAPE '\' THEN 6
                       WHEN similarity(lower(n), :q) >= :threshold THEN 8
                   END + CASE WHEN position = 1 THEN 0 ELSE 1 END
               ) AS rank,
               max(similarity(lower(n), :q)) AS sim
        FROM unnest(array_prepend(i.canonical_name, i.aliases)) WITH ORDINALITY AS t(n, position)
    ) best
    WHERE best.rank IS NOT NULL
    ORDER BY best.rank,
             CASE WHEN best.rank >= 8 THEN 1 - best.sim ELSE 0 END,
             length(i.canonical_name),
             i.canonical_name
    LIMIT :limit
    """
)

_ALL = text(
    """
    SELECT id, canonical_name, category, countable, default_unit, default_storage, is_staple
    FROM ingredients
    ORDER BY canonical_name
    LIMIT :limit
    """
)


def _escape_like(value: str) -> str:
    """Make % and _ in what the user typed mean themselves, not "anything"."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_ingredients(q: str, limit: int) -> IngredientSearchResult:
    """Match canonical names and aliases (pg_trgm), best match first."""
    needle = " ".join(q.lower().split())
    limit = max(0, min(limit, MAX_RESULTS))
    if limit == 0:
        return IngredientSearchResult(items=[])
    with transaction() as s:
        if not needle:
            rows = s.execute(_ALL, {"limit": limit}).mappings().all()
        else:
            like = _escape_like(needle)
            rows = (
                s.execute(
                    _SEARCH,
                    {
                        "q": needle,
                        "prefix": f"{like}%",
                        "contains": f"%{like}%",
                        "threshold": TYPO_THRESHOLD,
                        "limit": limit,
                    },
                )
                .mappings()
                .all()
            )
        return IngredientSearchResult(items=[Ingredient.model_validate(dict(r)) for r in rows])
