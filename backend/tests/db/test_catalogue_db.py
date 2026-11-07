"""Ingredient search against a real Postgres (pg_trgm): names, aliases, ranking and typos."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import models as m
from app.db.session import transaction
from app.main import app
from app.services.catalogue import search_ingredients

CATALOGUE = [
    ("egg", ["eggs", "chicken egg"], "egg", True),
    ("chicken thigh", ["chicken leg"], "meat", False),
    ("water spinach", ["kangkong", "kang kong"], "produce", False),
    ("spinach", [], "produce", False),
    ("cooked rice", [], "grain", False),
    ("uncooked rice", ["raw rice"], "grain", False),
    ("rice vermicelli", ["bee hoon", "bihun"], "grain", False),
    ("firm tofu", ["tau kwa", "bean curd"], "pantry", True),
    ("tomato", ["tomatoes"], "produce", True),
    ("eggplant", ["brinjal"], "produce", True),
]


def _fill() -> None:
    with transaction() as s:
        for name, aliases, category, countable in CATALOGUE:
            s.add(
                m.Ingredient(
                    id=uuid4(),
                    canonical_name=name,
                    aliases=aliases,
                    category=category,
                    countable=countable,
                    default_unit="pcs" if countable else None,
                    default_storage="fridge",
                )
            )


def _names(q: str, limit: int = 10) -> list[str]:
    return [item.canonical_name for item in search_ingredients(q, limit).items]


def test_an_alias_finds_its_ingredient():
    _fill()
    assert _names("kangkong") == ["water spinach"]
    assert _names("bee hoon") == ["rice vermicelli"]
    assert _names("tau kwa") == ["firm tofu"]
    assert _names("brinjal") == ["eggplant"]


def test_the_whole_word_beats_a_longer_one():
    _fill()
    assert _names("egg")[0] == "egg"  # not eggplant, though both start with "egg"
    assert _names("spinach")[0] == "spinach"  # then water spinach, which only contains it
    assert _names("spinach") == ["spinach", "water spinach"]


def test_starting_with_it_beats_only_containing_it():
    _fill()
    assert _names("rice") == ["rice vermicelli", "cooked rice", "uncooked rice"]


def test_an_exact_alias_beats_another_ingredients_longer_name():
    _fill()
    with transaction() as s:
        s.add(
            m.Ingredient(
                id=uuid4(),
                canonical_name="eggs benedict kit",
                aliases=[],
                category="pantry",
                countable=False,
                default_storage="fridge",
            )
        )
    assert _names("eggs")[:2] == ["egg", "eggs benedict kit"]  # "eggs" is egg's own alias


def test_the_real_name_beats_an_alias_at_the_same_level():
    _fill()
    # "chicken egg" is an alias that starts with "chicken", but chicken thigh is named it
    assert _names("chicken") == ["chicken thigh", "egg"]


def test_a_typo_still_finds_it_but_a_stranger_does_not():
    _fill()
    assert _names("tomatoe") == ["tomato"]
    assert _names("kangkung") == ["water spinach"]
    assert _names("xyz") == []


def test_capitals_and_extra_spaces_do_not_matter():
    _fill()
    assert _names("  KANG   Kong ") == ["water spinach"]


def test_an_ingredient_appears_once_even_when_several_names_match():
    _fill()
    assert _names("egg").count("egg") == 1  # its name, "eggs" and "chicken egg" all match
    assert len(_names("rice", limit=10)) == len(set(_names("rice", limit=10)))


def test_percent_and_underscore_mean_themselves():
    _fill()
    assert _names("%") == []
    assert _names("_") == []
    assert _names("e%g") == []


def test_the_limit_is_respected_and_nothing_typed_lists_the_catalogue_alphabetically():
    _fill()
    assert len(_names("rice", limit=2)) == 2
    assert _names("", limit=3) == ["chicken thigh", "cooked rice", "egg"]
    assert _names("   ", limit=2) == ["chicken thigh", "cooked rice"]
    assert _names("egg", limit=0) == []
    assert len(_names("", limit=1000)) == len(CATALOGUE)


def test_the_result_has_what_the_add_item_box_needs():
    _fill()
    (item,) = search_ingredients("tomato", 5).items
    assert (item.canonical_name, item.category, item.countable) == ("tomato", "produce", True)
    assert (item.default_unit, item.default_storage, item.is_staple) == ("pcs", "fridge", False)


def test_the_endpoint_answers_with_the_same_search():
    _fill()
    response = TestClient(app).get("/api/ingredients?q=kangkong")
    assert response.status_code == 200
    assert [i["canonical_name"] for i in response.json()["items"]] == ["water spinach"]


def test_the_endpoint_resolves_a_known_id_regardless_of_the_custom_batch_name():
    _fill()
    egg = search_ingredients("egg", 1).items[0]
    response = TestClient(app).get(
        "/api/ingredients",
        params={"q": "Grandma's breakfast box", "ingredient_id": str(egg.id), "limit": 1},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert [(item["id"], item["canonical_name"], item["default_unit"]) for item in items] == [
        (str(egg.id), "egg", "pcs")
    ]
