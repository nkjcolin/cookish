# Real-catalogue recommendation quality review

Review date: 5 November 2026. **Development review, before implementation freeze.**
The current catalogue is large enough to expose important integration problems;
adding more recipes is not the immediate priority. Resolve quantity checking and
shopping completeness before user testing or freezing for held-out evaluation.

## Method and reproducibility

The [runner](../backend/evaluation/catalogue_review.py) loads the actual 48 reviewed
recipe YAML files and Role 2's 42 ingredient rows through the seed parser and SQL
input mapping functions. It calls the production pure Cook/Shop engines, without
opening a database or changing recipes, weights, inventory or review approvals.

Run from `backend/`:

```powershell
.venv/Scripts/python.exe -m evaluation.catalogue_review --output ../private/catalogue-review.json
```

The [recorded results](../eval/catalogue_quality/results.json) include source
commit, LF-normalized source hashes, dependency versions, exact preferences,
scores, ingredient blockers and shopping lines. The clock is fixed at
`2026-11-05T12:00:00+08:00`. There are **25 Cook probes and seven Shop probes**.
The first five Cook suggestions simulate successive skips; each profile starts
without feedback or stars. Output dietary/equipment constraints are also checked
directly against raw catalogue rows, including optional ingredients.

Three declared kitchens are used:

- **Empty:** no stock. Existing absent-staple assumptions still apply.
- **Demo:** Role 2's eight demo batches reconstructed at the fixed clock.
- **All catalogue units:** every counted ingredient has 100 of its default unit;
  state-tracked ingredients are `enough`. Synthetic future labels and current
  confirmations isolate unit handling from freshness. This is a deliberately
  generous test input, not a real household or portion model.

“Ready to select” means the engine assessments satisfy the existing workflow's
essential-stock gate. It is not a cooking trial, food-safety assessment or
measurement of user satisfaction. Frontend observations below are source-path
inspection, not a completed browser session. These probes do not count toward
the reserved 30 held-out scenarios; none were authored or run.

## Main findings

### 1. Quantity checks cannot yet resolve many real recipes

With all equipment and all ingredients present in **catalogue default units**,
only **13/48 recipes** meet the stock gate. **35/48 have at least one essential
ingredient whose recipe unit differs from its inventory default unit**. Another
recipe has only optional mismatches, so 36 recipes have any mismatch.

| Ingredient | Recipes with an essential mismatch | Recipe / inventory units |
|---|---:|---|
| Firm tofu | 14 | grams / packs |
| Carrot | 12 | grams / pieces |
| Tomato | 12 | grams / pieces |
| Onion | 10 | grams / pieces |
| Potato | 5 | grams / pieces |
| Cucumber | 3 | grams / pieces |

Rows overlap; do not sum them as distinct recipes. The conservative engine
behavior is appropriate: it cannot infer grams from “three tomatoes.” The
problem is the resolution path. [QuickCheckSheet](../frontend/src/pages/cook/QuickCheckSheet.tsx)
only updates `remaining_state`; “Have it” does not supply a quantity or change
units. [UpdateItemSheet](../frontend/src/pages/kitchen/UpdateItemSheet.tsx) also
keeps the current unit when changing a count. A state-only confirmation leaves
the mismatch unresolved, so the backend still refuses selection.

**Concrete demo:** the first suggestion is “Cabbage and tofu rice bowls.” Rice is
unknown and tofu is stored as one pack, while the recipe needs 300 g. Confirming
all existing stock as `enough` resolves rice but leaves tofu `unknown`. The
original demo kitchen has **zero immediately selectable recipes** under its
preferences; that fact alone is expected for a check-oriented demo, but the
unresolvable tofu check is a usability blocker.

**Owners:** Role 5 + Roles 1/2. Agree a consistent quantity strategy and a UI
that captures the required information. Options include explicit measured batch
amounts or a deliberate tracking-policy change. Do not invent an average tomato
weight. Tofu's catalogue pack definition is 300 g, but applying it to an existing
batch still requires a clear meaning for that batch's `pack` unit.

### 2. Counted purchases with unknown pack suggestions cannot be completed in the UI

For an empty kitchen, the default three-meal basket includes **carrot and onion**
as counted ingredients with `suggested_packs: null`. Six of the seven Shop probes
contain at least one such counted line.

[ConfirmPurchasePage](../frontend/src/pages/ConfirmPurchasePage.tsx) only displays
its pack controls when a suggested or entered pack value is already non-null.
There is no initial entry path for these lines. The backend correctly requires
an explicit actual pack count, so ticking such an item as bought sends an
incomplete request and is rejected. State-tracked items with null suggestions
are different: they do not require numeric packs.

**Owners:** Role 1 + Role 5, with Role 2's purchase metadata. The UI needs to
distinguish counted lines requiring input from state-tracked purchases and let
users explicitly enter an actual pack count. Preserve the unknown value until
the user supplies it; defaulting silently to one would hide uncertainty.

### 3. Some Shop plans omit an unavailable essential ingredient

The empty-kitchen seven-meal plan includes “Cucumber, tomato and chickpea rice
salad” and “Microwave broccoli and chickpea rice.” Both require **cooked rice**.
The catalogue marks cooked rice as non-buyable; the shopping list omits it, even
though the kitchen has none. The same gap occurs in the halal and microwave-only
probes. Four of the seven probes have no such omission.

**Owner:** Role 5 first; recipe changes would also need review. Exclude recipes
whose essential, non-staple, non-buyable requirements are unavailable, or define
an explicit preparation dependency with the right ingredients and time. Do not
silently substitute dry rice or a cooked-to-dry ratio. Add a regression using
these real catalogue recipes.

### 4. Cold start and limited coverage need honest presentation

| Profile, using all catalogue units | Eligible recipes | Ready to select |
|---|---:|---:|
| All equipment, unrestricted | 48 | 13 |
| Stove only | 43 | 10 |
| Vegetarian | 35 | 7 |
| Vegan | 23 | 3 |
| Halal, using catalogue flags | 39 | 8 |
| Microwave only | 2 | 1 |
| No equipment | 1 | 0 |
| At most 15 minutes | 1 | 0 |
| At most 20 minutes | 4 | 2 |
| At most 30 minutes | 16 | 4 |

Time rows count after the time limit; the others count after dietary/equipment
filtering. These counts concern stored metadata, not independent certification.
For an empty kitchen, the first suggestion is the rice salad and all five of
its essential non-staple ingredients are missing. The engine intentionally
returns a missing-stock fallback, not a cookable claim. CookPage's quick-check
decision examines existing `needs_check`/`freshness_check` batches; absent stock
has no batch to check. The product needs a clear add-stock/shop route before
selection, rather than leaving a new user with a rejected “Cook this” action.

Requesting seven microwave-only meals produces two distinct families. The API
already reports the actual two-meal count: this is narrow coverage, not a false
seven-meal claim. Additional quick or limited-equipment recipes should be chosen
after fixing quantity handling and establishing target-user demand.

### 5. Variety is mixed, and raw recipe count overstates breadth

The 48 recipes represent **28 families**: 29 are tagged Chinese, seven Other,
four Indian, four Western, two Malay and two Japanese. Variants account for part
of these counts. The unrestricted first five skips cover five families, but the
demo's first five cover only three: its first two are cabbage-tofu variants.

Shop avoids repeating a family in the same plan. The empty-kitchen seven-meal
plan covers four cuisines; the vegan plan covers five. The demo three-meal plan
is entirely Chinese. This is a consequence of the declared preferences and
shared-ingredient scoring, not evidence that users will find it monotonous.
Review the actual menu with participants before changing weights. Across-session
recent-cooked repetition remains pending an agreed history window; persisted
feedback alone does not establish that feature.

## Recommended order before freezing

1. Resolve the counted quantity/unit workflow with Roles 1/2; keep the engine's
   conservative checks. Retest the demo's “Have it” path and counted shopping
   confirmation through the real frontend/backend.
2. Fix the Role 5 non-buyable-essential planning gap and add real-catalogue
   regressions. This can proceed independently of the quantity decision.
3. Make empty-stock fallback navigation explicit, then assess whether a few
   genuinely different quick/limited-equipment meals are needed.
4. Rerun this review and the existing 70 development scenarios, retain both
   baselines, then freeze before independent held-out evaluation.

The review makes no claim about taste, cooking success, savings or willingness
to pay. It changes no recipes, production ranking weights or dietary policies.
