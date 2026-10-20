from scripts.render_recipe_review import OUTPUT, render


def test_review_guide_matches_recipe_contents_and_research_notes():
    assert OUTPUT.read_text(encoding="utf-8") == render(), (
        "Run python scripts/render_recipe_review.py after changing recipes or review notes"
    )
