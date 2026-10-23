# Cookish business case evidence and decisions

Research date: **24 October 2026**. Owner: Role 5, Wenlong. This evidence pack
supports the [short report draft](business-case.md) and addresses TA feedback
on citations, market size, running cost and reasons to pay. Commercial choices
below are proposals for review; subscriptions and usage limits are not implemented.

## Market and initial audience

The initial audience is Singapore households that prepare meals at home several
times a week, manage shared groceries and can use the current English interface
and recipe catalogue. Students in shared homes, couples and families are possible
recruitment groups, not independently measured customer segments.

| Evidence | What it supports | Important boundary |
|---|---|---|
| SingStat reports **1,487,100 resident households in 2025**, average size 3.06. [M1](#references) | A broad demographic ceiling for a household product. | A resident household's reference person is a citizen or permanent resident. The count is not the number of regular cooks or prospective subscribers. |
| HES 2023 reports average monthly spending of **S$456 on food and non-alcoholic beverages** and **S$966 on food and beverage serving services**. [M2](#references) | Food decisions concern a recurring household expense; prepared meals are also a convenient alternative. | Spending does not establish cooking frequency, software budgets or willingness to pay. |
| NEA's 2016–2017 study interviewed **443 households** and audited waste from **279**. Some respondents linked spoiled food to overbuying or items hidden in the fridge. [M3](#references) | Historical motivation for inventory visibility and better purchase decisions. | This is older evidence; it does not establish current prevalence or Cookish's effect. |
| NEA reports **790,000 tonnes of food waste in 2025**, with **18% recycled**. [M4](#references) | National environmental context. | This includes multiple sectors. It is not household avoidable waste or an estimate of waste the app could prevent. |

Use the household count as the broad total addressable market ceiling. Define
the serviceable segment using a **joint** screening rule: regular home cooking,
grocery responsibility, interface access and catalogue fit. No reviewed source
measures that joint share, so the following are sensitivity assumptions:

| Assumed jointly eligible share | Illustrative serviceable households |
|---:|---:|
| 10% | 148,710 |
| 20% | 297,420 |
| 30% | 446,130 |

These are `1,487,100 × assumed share`, not forecasts. Do not multiply separate
national rates as though cooking habits, internet access and household type
were independent. Revenue additionally needs adoption, retention and payment.

Estimate the obtainable segment from an actual recruitment channel. For example,
**500 qualified households reached × 20% trial uptake × 50% four-week retention
= 50 active households**; an assumed 20% paid share gives 10 paying households.
Every input in that example is hypothetical. It illustrates a calculation, not
a course recruitment commitment or evidence of demand. The current 6–8-person
usability study cannot estimate a population conversion rate.

## Current alternatives and price context

Prices were checked on 24 October 2026. Currency, storefront and billing period
are retained; no currency conversion or equal-feature comparison is implied.
Capabilities below are vendor descriptions, not results of hands-on benchmarking.

| Alternative | Verified offering | Free access and paid price | Consequence for the business case |
|---|---|---|---|
| **SuperCook** | Ingredient-based recipe discovery from a manually maintained or voice-entered pantry. | Singapore iOS listing: **Free**; no paid tier identified in that listing. [C1](#references) | Ingredient matching alone has a free substitute. |
| **Samsung Food / Food+** | Free recipe saving, meal planning and shared lists; Food+ adds personalised planning, pantry automation and expiry-prioritised searches. | Singapore iOS: **S$9.98/month or S$89.98/year**. US iOS: **US$6.99/month or US$59.99/year**. [C2–C5](#references) | Expiry-aware recommendations and integrated pantry updates are already available. |
| **Cooklist** | Pantry matching, barcode and loyalty-card imports, shared lists and expiry features. | Free download with in-app purchases. US iOS lists monthly Pro products at **US$5.99, US$7.99 and US$9.99**, annual products at **US$49.99 and US$59.99**; offer eligibility is unclear. [C6–C7](#references) | Do not claim a single universal price, a verified free allowance or Singapore retailer compatibility. |
| **Plan to Eat** | Recipe organisation, meal planning and grocery-list generation. Its earlier automatic Pantry feature was retired. | Website: **US$5.95/month or US$49/year**, 14-day trial; no ongoing free plan. Official help lists Apple annual purchase at US$54.99. [C8–C10](#references) | Reliable manual kitchen checks remain a credible competing workflow. |

The preliminary price of **US$4.99 per household per month** is **US$59.88 over
12 monthly payments**. That is above Plan to Eat's annual website plan and close
to Samsung Food+'s annual US price. Lower monthly pricing is not proof of better
value. Compare annual and monthly commitments explicitly.

Mealime is excluded from the active comparison: its official notice announced
discontinuation on **21 October 2026**, with features moving to Meals Hub in
Albertsons store apps. Singapore availability of that replacement was not
verified. The notice does not establish why other subscription businesses would
succeed or fail. [C12](#references)

## Traceable review evidence for the original report

These are purposively selected public examples relevant to inventory maintenance
and navigation, not a systematic sample. Storefront locale does not establish
the reviewer's location. Review text and featured ordering may change; retain the
reviewer, review date and source URL in the report notes. App versions at the time
of these experiences were not established. Paraphrases below contain no direct quotes.

| Product, reviewer and review date | Reported experience | Suitable implication |
|---|---|---|
| Cooklist — **Heidi Wright, 29 June 2026** [C6](#references) | Delayed responses during quantity edits could cause repeated changes. | Test update latency and duplicate-action handling; this is not our measured competitor latency. |
| Cooklist — **Grace Birchler, 14 July 2026** [C6](#references) | Liked recipe discovery but found pantry upkeep tedious. | Measure ongoing maintenance effort as well as entry speed. |
| Samsung Food — **Karen Moctezuma, 5 November 2025** [C11](#references) | Difficulty representing stock quantities and reconciling shopping items. | Test stock clarity; do not claim the current product lacks quantity support. |
| Samsung Food — **ShaSha Grace, 23 December 2024** [C11](#references) | Liked the app but found saved-recipe access involved too many steps. | Historical feedback motivating navigation tests. |
| Samsung Food — **Shawn Wright, 17 September 2026** [C11](#references) | Positive navigation experience and useful portion adjustments. | Include mixed evidence; selected complaints do not establish a general usability defect. |

Plan to Eat supplies a different kind of evidence: its own explanation says an
earlier Pantry feature could suppress needed purchases when records differed
from actual stock. The article was **updated 22 October 2025**; that is not a
verified discontinuation date. [C10](#references)

The report can therefore discuss specific reported frictions and testable
design questions. It should not say that users generally dislike competitors,
that the cited Samsung complaints all occurred in 2026, or that Cookish has
already solved those problems.

## Proposed value and free versus paid boundary

**Value hypothesis:** a focused selection of reviewed recipes, explicit stock
uncertainty and user-confirmed purchase/consumption updates may reduce the total
effort of deciding what to cook and buy. Success means less decision and upkeep
time without more missing-ingredient errors. A larger feature list, AI branding
or national food-waste statistics do not establish that benefit.

| Proposed tier | Access | Rationale and status |
|---|---|---|
| Free | Shared manual inventory, core Cook/Shop, household dietary checks, corrections/undo and normal preference learning; a limited assisted-entry trial. | Lets a household complete the core workflow. Safety-related restrictions and correction controls are not a paid incentive. These entitlements are a proposal; no billing gates exist. |
| Paid — price hypothesis **US$4.99/household/month** | The same workflow plus a recurring, clearly stated allowance of assisted imports. A candidate allowance is **20 imports/month**, subject to measured model costs and observed demand. | Payment would buy recurring convenience. Quotas, metering and upgrade screens remain future work; the cost model treats failed/retried provider calls as costs too. |

The preliminary report also suggested paid natural-language refinement and
richer preference history. The current scope uses fixed adjustment tags and
household feature weights. Do not sell those earlier ideas as delivered paid
features. Future premium features require a separate scope decision.

The database adapter and deployed AI workflow remain incomplete. Current
evidence supports the [recipe catalogue](role5-handoff.md), pure algorithms,
transaction workflow and [development scenarios](../eval/reco_scenarios/README.md).
It does not establish deployed convenience, customer retention or commercial readiness.

## Questions to add to Role 1's study

Coordinate a short exploratory interview after participants try the workflow:

1. Which tool or habit do you use now, and what is difficult about it?
2. Which Cookish step saved effort, and which created more work? Include the time
   spent correcting imports and maintaining stock, not only choosing a recipe.
3. With a free option available, would recurring assisted imports be useful enough
   to pay for? Present the allowance and price together, and allow “stay free”
   and “use another tool.” Ask for the reason before suggesting an answer.
4. How often would you import groceries, and what happens when the allowance is used?

Retain negative feedback. If comparing prices, vary their order and report the
small sample and anchoring risk. Stated interest is exploratory evidence;
continued usage and an actual voluntary payment decision would be stronger.
Do not infer conversion percentages from 6–8 convenience-sampled participants.

## Cost and handoff

The [cost assumptions and calculator](../eval/business_case/README.md) separate
published Singapore AWS rates from assumed workloads and an unselected model
provider. It reports cost per active household, per active login and per paying
household, including the free-household subsidy. Role 3 supplies measured cloud
usage and the on-premise comparison; Role 4 supplies model tokens, retries and
cost per import. No price, cost or conversion assumption here is a measured result.

Role 2 can use the [short draft](business-case.md) in the final report and retain
this evidence pack in the public repository. Keep a concise reference list in
the report itself, within its ten-page limit. AI assistance was used for source
discovery, synthesis and calculation tooling; Wenlong and the team should review
the claims, commercial assumptions and final wording before submission.

## References

All external pages were accessed **24 October 2026**. “Undated” means no reliable
publication date was established; access dates are not publication dates.

- **M1.** Singapore Department of Statistics, [Resident Households](https://www.singstat.gov.sg/find-data/explore-data-themes/households/resident-households), 2025 data; [General Household Survey release](https://www.singstat.gov.sg/publication-resources/general-household-survey-2025-households-and-housing), 30 June 2026.
- **M2.** Singapore Department of Statistics, [Key Indicators of the Household Expenditure Survey 2023](https://www.singstat.gov.sg/files/a379514d-c004-46ad-9c12-1046b4e33ba0.pdf), printed pp.106–107; [report publication](https://www.singstat.gov.sg/publication-resources/report-on-the-household-expenditure-survey-2023), 28 November 2024.
- **M3.** National Environment Agency, [Half of Food Waste Thrown Away by Singapore Households Can Be Prevented: NEA Household Waste Study](https://www.nea.gov.sg/media/news/news/index/half-of-food-waste-thrown-away-by-singapore-households-can-be-prevented-nea-household-waste-study), 3 December 2017; fieldwork November 2016–March 2017.
- **M4.** National Environment Agency, [Food Waste Management](https://www.nea.gov.sg/our-services/waste-management/3r-programmes-and-resources/food-waste-management), 2025 figures; page updated 18 June 2026.
- **C1.** AMR Systems LLC, [SuperCook Recipe by Ingredient, Singapore App Store](https://apps.apple.com/sg/app/supercook-recipe-by-ingredient/id1477747816), current listing; displayed app version 2.0.6 dated 15 June 2022.
- **C2.** Samsung Food, [Free Meal Planner](https://samsungfood.com/meal-planner/), undated product page.
- **C3.** Samsung Food, [Food+](https://samsungfood.com/food-plus/), undated product page.
- **C4.** Samsung Food, [Singapore App Store listing](https://apps.apple.com/sg/app/samsung-food-meal-planning/id1133637674), current prices.
- **C5.** Samsung Food, [US App Store listing](https://apps.apple.com/us/app/samsung-food-meal-planner/id1133637674?ls=1), current prices.
- **C6.** Cooklist Inc., [Google Play developer description and public reviews](https://play.google.com/store/apps/details?hl=en_US&id=com.cooklist.android), app updated 17 June 2026; review dates listed above.
- **C7.** Cooklist Inc., [US App Store listing](https://apps.apple.com/us/app/cooklist-pantry-meals-recipes/id1352600944), current in-app purchase products; individual eligibility not established.
- **C8.** Plan to Eat, [Pricing](https://www.plantoeat.com/pricing/), current website plans.
- **C9.** Plan to Eat, [How Much Does Plan to Eat Cost?](https://learn.plantoeat.com/help/how-much-does-plan-to-eat-cost), updated 6 October 2026.
- **C10.** Plan to Eat, [A Digital Pantry Inventory: Does It Really Help?](https://learn.plantoeat.com/help/a-digital-pantry-inventory-does-it-really-help), updated 22 October 2025.
- **C11.** Samsung Food, [Google Play developer description and public reviews](https://play.google.com/store/apps/details?hl=en_US&id=com.foodient.whisk), review dates listed above.
- **C12.** Mealime, [Mealime Closing](https://www.mealime.com/closing), notice specifying 21 October 2026 as the discontinuation date.

Project evidence: [SPEC B5](SPEC.md#b5-role-5--recommendation-algorithms-and-recipe-catalogue-wenlong),
[recipe provenance](role5-handoff.md#recipe-provenance-and-human-review),
[implementation status](role5-integration.md) and
[evaluation scope](../eval/reco_scenarios/README.md). The original price and tier
proposal came from the team's local `Preliminary.pdf`, p.4, section 3.4; no copy
of that PDF is added to the repository by this work.
