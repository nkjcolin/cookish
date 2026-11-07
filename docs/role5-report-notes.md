# Role 5 recommendation and catalogue report draft

Cookish uses deterministic recipe ranking and small household preference updates.
Its pure recommendation engines are tested independently of the web interface.
Recipe details, household stars and the optional use-first endpoint use the existing
database services; Cook/Shop sessions, cooking confirmations and rating endpoints
now use the SQL repository. The migration and updated backend still need deployment
and checks on AWS. The explanations below describe the implemented source. [1,2]

## Recommendations before any feedback exists

A new household starts with zero learned taste weights. Cookish first excludes
unreviewed recipes and recipes incompatible with the household's allergens, diets
or equipment. It then assesses ingredient availability and ranks candidates using
stock coverage, usable ingredients approaching their use-first date, cuisine
preferences, effort and uncertainty. These initial weights are fixed configuration
values, not values learned from prior users. Equal scores use a deterministic recipe
ID tie-break, so no historical feedback needs to be invented. [1,3]

For returning households, a recipe cooked within the last seven elapsed days gets
a one-point repetition penalty. Cookish checks this before each ranking, using the
successful consumption event's time. Undone meals are excluded. Cooking it several
times does not multiply this penalty, and the recipe remains eligible. [2,3]

If the kitchen is empty, the Cook engine can return a fallback recipe whose missing
essentials are explicitly marked. This does not mean it is ready to cook: the
workflow checks essential stock before selection. If no recipe satisfies the
required constraints, it returns no result. The frontend route from missing stock
to adding ingredients or shopping still needs work. The source now uses real
sessions, but the complete first-use experience has not been verified on AWS. [1,2,4]

Shop can plan meals for an empty kitchen because purchasable ingredients go on the
shopping list. It excludes meals requiring unavailable non-buyable essentials such
as cooked rice. It neither silently substitutes uncooked rice nor invents a cooking
yield. With the current catalogue, an empty kitchen restricted to microwave equipment
has no eligible Shop plan after this check. [4]

## Recipe catalogue origin and scope

The catalogue contains 48 original AI-assisted recipe drafts: 28 base meals and
20 variants, mapped to 42 canonical ingredients. Wenlong approved the recipe
content on 20 October 2026. Named external creator pages informed dish concepts
and techniques; the adapted quantities and prose are project content, rather than
a copied commercial recipe collection. The review pack records these references
and the AI-assisted authorship. Human content approval does not establish measured
cooking times, nutritional values or successful cooking trials. [5]

Each recipe includes ingredients and essential flags, portions, steps, equipment,
estimated time, difficulty and taste tags. Role 2's authoritative ingredient catalogue
supplies allergen, diet, tracking and purchase metadata. Runtime reads include only
reviewed recipes. Forty-eight recipes meet the project's 40–60 target, but variants
share meal families and do not provide 48 unrelated choices; restrictive preferences
may still produce few or no suitable meals. [1,4,5]

## How feedback changes later rankings

Learning belongs to the **household**, because its members share preferences,
inventory and meal decisions. The report should therefore describe household weight
updates rather than separate per-user models. A user's identity records who submitted
an action. Learning uses cuisine, taste tags and protein categories. Eight catalogue
ingredient IDs map to poultry, egg, soy, legume, fish and shellfish. Only essential
ingredients contribute; a mixed meal may have several categories, each counted
once. This is a culinary grouping, not a nutrition measurement. [1,6]

After a confirmed cooked meal, its current feedback contributes the following amount
to each of its distinct features. Weights are clipped to the range −2 to +2. [6]

| Evidence for one meal | Contribution per feature |
|---|---:|
| Cooked, no rating yet | +0.0625 provisionally |
| Like | +0.25 |
| Maybe | 0 |
| Dislike | −0.25 |
| Skipped or selected without cooking | 0 |

The rating replaces the provisional contribution. For example, liking a Chinese,
low-oil egg recipe adds 0.25 to each of `cuisine:chinese`, `tag:low_oil` and
`protein:egg`, before clipping. A future recipe sharing all three gains 0.75
preference points. Other score components can still change which recipe wins,
and allergy/diet/equipment restrictions run before scoring. [3,6]

Repeated feedback for the same cooked record does not create another meal sample.
Changing a rating replaces that record's evidence; the engine recomputes bounded
weights in confirmation order so edits remain correct even after clipping. Starring
is separate: it adds a configured +1 recipe preference bonus while starred and
does not alter learned taste weights. Both stars and cooking feedback persist in
the database. Earlier meals recorded with cuisine/tags only keep those features
when edited; protein learning applies to new confirmations without backfilling
old rewards. [1,2,3,6]

## Use first and uncertainty

The optional use-first endpoint reads the authenticated household's inventory
snapshot. Role 2 computes freshness and estimated dates. Role 5 includes batches
marked `use_soon` that have a non-past date and known remaining stock, then orders
them by date, acquisition date and ID. Days remaining use the Singapore calendar.
It excludes expired/check batches, empty or unknown stock, invalid counted amounts,
and stale perishable quantity confirmations. A low amount may appear because some
stock remains; this does not promise enough for a particular recipe. [7]

The response preserves printed label fields separately from estimated dates.
This list suggests an order of use and does not certify food safety or change
inventory. It is an API feature; no new frontend screen or scheduled reminder is
included. [7]

## Evaluation and terminology

The planner-fix development run passed 70 scenarios containing 85 checked steps.
The separate real-catalogue review found missing non-buyable essentials in three
of seven Shop probes before the fix and none afterward. These are development
checks, not evidence of user satisfaction, reduced waste or production elasticity. [4,8]

The merged SQL integration passed 549 backend tests, including 20 SQL workflow
tests and migration preservation; frontend and AI jobs also passed. These results
predate the protein/history additions and do not verify deployment. [2,9]

Thirty **held-out scenarios** are reserved for independent authorship and final
evaluation after an implementation freeze. They must remain unseen during development
so the final check measures performance on cases the rules were not adjusted to pass.
No held-out pass result is claimed. Deployed Cook/Shop testing is also still required. [8]

An **idempotency key** identifies one intended stock-changing action: retrying the
same request should return the previous result rather than apply it twice. A
**revision check** compares the inventory version the client saw with the current
version, rejecting stale changes instead of overwriting newer stock information.
Role 2 provides stock-event handling; Role 5's confirmation workflow uses it in
the same transaction as session and feedback updates. [2]

## References

1. [Role 5 implementation and ownership](../backend/app/reco/README.md).
2. [Cook and Shop service integration](role5-integration.md) and
   [implemented storage additions](role5-storage-proposal.md).
3. [Cook ranking implementation](../backend/app/reco/cook.py) and
   [configured scoring weights](../backend/app/reco/config.py).
4. [Real-catalogue quality review and Shop fix](role5-catalogue-quality-review.md),
   including the original and post-fix recorded results.
5. [Recipe review pack, authorship, approval and concept references](recipe-review.md).
6. [Household feedback-learning implementation](../backend/app/reco/learning.py)
   and [explicit protein mapping](../backend/app/reco/protein.py).
7. [Role 5 use-first logic](../backend/app/reco/use_first.py) and
   [Role 2 freshness calculations](../backend/app/services/freshness.py).
8. [Development and held-out evaluation protocol](../eval/reco_scenarios/README.md)
   and [planner-fix development results](../eval/reco_scenarios/results/shop-essential-fix.json).
9. [SQL integration CI at `f313566`, 7 November 2026](https://github.com/nkjcolin/cookish/actions/runs/42342203535).

The separate [business-case draft](business-case.md) contains the market,
competitor and pricing references. Its assumed infrastructure/model costs still
need Roles 3/4's measured inputs before being described as actual cost per household.
