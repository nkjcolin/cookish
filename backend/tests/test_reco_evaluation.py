"""The evaluation must reject bad evidence, not only pass its authored examples."""

import json
import shutil
from dataclasses import replace

import pytest
import yaml

import app.reco.cook as cook_engine
import evaluation.run as runner
from app.reco.models import Recommendation, ScoreBreakdown, ScoredRecipe
from evaluation.run import (
    SUITE,
    InputError,
    hard_violations,
    load_yaml,
    main,
    make_world,
    run_scenario,
    run_suite,
    validate_references,
)
from evaluation.schema import Fixtures, Scenario

COLD_START = "cook-01-cold-start.yaml"


def write_yaml(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@pytest.fixture(scope="module")
def world():
    return make_world(load_yaml(SUITE / "fixtures.yaml", Fixtures))


@pytest.fixture
def isolated_suite(tmp_path):
    fixtures = tmp_path / "fixtures.yaml"
    cases = tmp_path / "development"
    cases.mkdir()
    shutil.copyfile(SUITE / "fixtures.yaml", fixtures)
    shutil.copyfile(SUITE / "development" / COLD_START, cases / COLD_START)
    return fixtures, cases


def cli_args(fixtures, cases):
    return ["--fixtures", str(fixtures), "--cases-dir", str(cases), "--case", "DEV-C01"]


def test_full_development_suite_has_exact_counts_and_no_failures():
    report = run_suite()
    assert report["summary"] == {
        "scenarios": 70,
        "passed": 70,
        "steps": 85,
        "steps_passed": 85,
        "failures_by_kind": {},
        "modes": {"cook": 40, "shop": 30},
        "held_out_executed": 0,
    }
    assert report["selection"] == "full"
    assert len({result["id"] for result in report["results"]}) == 70


@pytest.mark.parametrize("wrong_amount", ["1200 g", "1.200 g", "1/200 g", "-200 g", "200 grams"])
def test_quantity_fragment_cannot_match_a_different_quantity(wrong_amount):
    assert not runner.contains_amount_fragment(wrong_amount, "200 g")
    assert runner.contains_amount_fragment("Check at home — 200 g for the planned meals", "200 g")


def test_incorrect_shopping_amount_fails_even_when_digits_contain_expected(world, monkeypatch):
    case = load_yaml(SUITE / "development" / "shop-01-empty-pantry.yaml", Scenario)
    real_to_basket = runner.to_basket

    def corrupted_basket(*args):
        basket = real_to_basket(*args)
        return basket.model_copy(
            update={
                "items": [
                    item.model_copy(
                        update={"amount": "1200 g for the planned meals; buy as needed"}
                    )
                    if item.name == "rice"
                    else item
                    for item in basket.items
                ]
            }
        )

    monkeypatch.setattr(runner, "to_basket", corrupted_basket)
    result = run_scenario(case, world)
    assert not result["passed"]
    assert "rice amount" in result["steps"][0]["failures"][0]["message"]


def test_unavailable_git_status_is_unknown_not_clean(monkeypatch):
    monkeypatch.setattr(runner, "git_value", lambda *args: None)
    report = run_suite(selected=["DEV-C01"])
    assert report["provenance"]["git_head"] is None
    assert report["provenance"]["working_tree_dirty"] is None


def test_subset_is_labelled_and_preserves_provenance(tmp_path, capsys):
    output = tmp_path / "subset.json"
    assert main(["--case", "DEV-C34", "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["split"] == "development"
    assert report["selection"] == ["DEV-C34"]
    assert report["summary"]["scenarios"] == 1
    assert report["summary"]["steps"] == 3
    assert report["summary"]["held_out_executed"] == 0
    assert "not held-out" in report["scope"]
    provenance = report["provenance"]
    assert "git_head" in provenance
    assert len(provenance["fixture_sha256"]) == 64
    assert provenance["source_sha256"]
    assert all(len(value) == 64 for value in provenance["source_sha256"].values())
    assert len(provenance["scenario_sha256"]) == 70
    assert set(provenance["config"]) == {"cook", "shop", "learning"}
    assert set(provenance["runtime"]) == {"python", "pydantic", "pyyaml"}
    assert {"backend/pyproject.toml", "backend/uv.lock"} <= provenance["source_sha256"].keys()
    assert "held-out executed: 0" in capsys.readouterr().out


@pytest.mark.parametrize("nested", [False, True], ids=["top-level", "nested"])
def test_duplicate_yaml_keys_cannot_silently_overwrite_evidence(tmp_path, nested):
    path = tmp_path / "duplicated.yaml"
    text = (SUITE / "development" / COLD_START).read_text(encoding="utf-8")
    if nested:
        text = text.replace(
            "  max_cook_minutes: 60", "  max_cook_minutes: 60\n  max_cook_minutes: 5"
        )
    else:
        text += "\nmode: shop\n"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(InputError, match="duplicate YAML key"):
        load_yaml(path, Scenario)


@pytest.mark.parametrize("section", [None, "preferences", "expect"])
def test_unknown_fields_are_invalid_instead_of_ignored(tmp_path, section):
    data = yaml.safe_load((SUITE / "development" / COLD_START).read_text(encoding="utf-8"))
    target = data if section is None else data[section]
    target["unrecognised_assertion"] = True
    path = tmp_path / "invalid.yaml"
    write_yaml(path, data)
    with pytest.raises(InputError, match="unrecognised_assertion"):
        load_yaml(path, Scenario)


@pytest.mark.parametrize(
    ("filename", "assertion", "message"),
    [
        (COLD_START, {"planned": []}, "Cook expectations cannot contain Shop assertions"),
        (
            "shop-01-empty-pantry.yaml",
            {"needs_check": []},
            "Shop expectations cannot contain Cook assertions",
        ),
        (
            "shop-01-empty-pantry.yaml",
            {"relaxable": []},
            "Shop expectations cannot contain Cook assertions",
        ),
        (
            "shop-01-empty-pantry.yaml",
            {"missing_essential_fallback": False},
            "Shop expectations cannot contain Cook assertions",
        ),
    ],
)
def test_assertions_for_the_other_mode_are_not_silently_ignored(
    tmp_path, filename, assertion, message
):
    data = yaml.safe_load((SUITE / "development" / filename).read_text(encoding="utf-8"))
    data["expect"].update(assertion)
    path = tmp_path / "irrelevant.yaml"
    write_yaml(path, data)
    with pytest.raises(InputError, match=message):
        load_yaml(path, Scenario)


@pytest.mark.parametrize(
    "assertion",
    [
        {"ingredient_status": {"egg": "have"}},
        {"amounts": {"egg": "3 pcs"}},
        {"needs_check": []},
        {"freshness_check": []},
    ],
)
def test_no_result_cannot_claim_unchecked_suggestion_contents(tmp_path, assertion):
    source = SUITE / "development" / "cook-19-allergen-egg.yaml"
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["expect"].update(assertion)
    path = tmp_path / "impossible-assertion.yaml"
    write_yaml(path, data)
    with pytest.raises(InputError, match="no-result Cook step cannot assert suggestion contents"):
        load_yaml(path, Scenario)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"recipes": ["missing-recipe"]}, "unknown recipes"),
        ({"preferences": {"disliked_ingredients": ["missing-ingredient"]}}, "unknown ingredients"),
        ({"expect": {"selected_any": ["not-a-candidate"]}}, "expected recipes"),
        ({"expect": {"amounts": {"missing-ingredient": "5 g"}}}, "unknown ingredients"),
    ],
)
def test_unknown_references_cannot_make_partial_assertions_pass(world, change, message):
    data = yaml.safe_load((SUITE / "development" / COLD_START).read_text(encoding="utf-8"))
    for key, value in change.items():
        if isinstance(value, dict):
            data[key].update(value)
        else:
            data[key] = value
    case = Scenario.model_validate(data)
    with pytest.raises(InputError, match=message):
        validate_references(case, world)


def test_unknown_fixture_ingredient_is_rejected_before_engine_use(tmp_path):
    data = yaml.safe_load((SUITE / "fixtures.yaml").read_text(encoding="utf-8"))
    data["recipes"]["egg-rice"]["ingredients"][0]["ingredient"] = "absent-catalogue-entry"
    path = tmp_path / "fixtures.yaml"
    write_yaml(path, data)
    with pytest.raises(InputError, match="unknown ingredient absent-catalogue-entry"):
        make_world(load_yaml(path, Fixtures))


def test_duplicate_case_ids_are_rejected_even_in_a_subset(isolated_suite):
    fixtures, cases = isolated_suite
    shutil.copyfile(cases / COLD_START, cases / "duplicated-case.yaml")
    with pytest.raises(InputError, match="duplicate scenario IDs"):
        run_suite(fixtures, cases, selected=["DEV-C01"])


def test_missing_cases_cannot_be_reported_as_a_full_suite(isolated_suite):
    fixtures, cases = isolated_suite
    with pytest.raises(InputError, match="full development suite"):
        run_suite(fixtures, cases)


def test_wrong_expected_answer_fails_the_report_and_cli(isolated_suite, tmp_path, capsys):
    fixtures, cases = isolated_suite
    path = cases / COLD_START
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["expect"]["selected_any"] = ["tofu-rice"]
    write_yaml(path, data)
    report = run_suite(fixtures, cases, selected=["DEV-C01"])
    assert report["summary"]["passed"] == 0
    assert report["summary"]["failures_by_kind"] == {"expectation": 1}
    assert report["results"][0]["steps"][0]["observed"]["selected"] == "egg-rice"
    output = tmp_path / "failed-report.json"
    assert main([*cli_args(fixtures, cases), "--output", str(output)]) == 1
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["passed"] == 0
    assert "DEV-C01 step 0 [expectation]" in capsys.readouterr().out


def test_malformed_input_exits_two_without_writing_a_report(isolated_suite, tmp_path, capsys):
    fixtures, cases = isolated_suite
    (cases / COLD_START).write_text("version: [unterminated\n", encoding="utf-8")
    output = tmp_path / "must-not-exist.json"
    assert main([*cli_args(fixtures, cases), "--output", str(output)]) == 2
    assert not output.exists()
    assert "Invalid evaluation input" in capsys.readouterr().err


def test_an_allergenic_output_fails_even_when_expected_selection_accepts_it(world, monkeypatch):
    case = load_yaml(SUITE / "development" / "cook-19-allergen-egg.yaml", Scenario)
    # Deliberately corrupt both the expectation and the implementation. The
    # independent output oracle must still reject an allergenic recommendation.
    case.expect = case.expect.model_copy(update={"result": True, "selected_any": ["egg-rice"]})
    recipe = world.recipes["egg-rice"]
    scored = ScoredRecipe(
        recipe=recipe,
        ingredients=(),
        score=ScoreBreakdown(0, 0, 0, 0, 0, 0, 0),
        preferred_variant=False,
    )

    def unsafe_suggest(recipes, inventory, prefs, session, catalogue, **kwargs):
        return Recommendation(
            scored,
            replace(session, current_recipe_id=recipe.id, shown_recipe_ids=(recipe.id,)),
        )

    def forbidden_filter(*args, **kwargs):
        pytest.fail("the independent oracle must not invoke the production hard filter")

    monkeypatch.setattr(runner, "suggest", unsafe_suggest)
    monkeypatch.setattr(cook_engine, "filter_recipes", forbidden_filter)
    result = run_scenario(case, world)
    assert not result["passed"]
    assert result["steps"][0]["failures"] == [
        {"kind": "hard_constraint", "message": "egg: excluded allergen"}
    ]


def test_independent_oracle_checks_all_hard_restrictions(world, monkeypatch):
    case = load_yaml(SUITE / "development" / "cook-19-allergen-egg.yaml", Scenario)
    prefs, _ = runner.inputs(case, world)
    prefs = prefs.model_copy(update={"diets": ["vegan"]})
    bad_recipe = world.recipes["egg-rice"].model_copy(
        update={"reviewed": False, "equipment": ["oven"]}
    )

    def forbidden_filter(*args, **kwargs):
        pytest.fail("oracle must remain independent of the production filter")

    monkeypatch.setattr(cook_engine, "filter_recipes", forbidden_filter)
    assert hard_violations(bad_recipe, prefs, 5, world.catalogue) == [
        "unreviewed recipe",
        "unavailable equipment",
        "strict time bound exceeded",
        "egg: excluded allergen",
        "egg: incompatible diet",
    ]
