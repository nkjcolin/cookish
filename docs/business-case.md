# Cookish business case and pricing draft

Role 5 contribution, prepared **24 October 2026**. This short draft is intended
for the final report; the [research pack](business-case-research.md) retains
the competitor table, review details and source dates. Cost and commercial
assumptions require team review and later measurements.

The cost figures below were updated on **7 November 2026** to use the verified
ARM64 Lambda architecture. The market and competitor research dates are unchanged.

## Motivation and addressable audience

Cookish targets Singapore households that regularly cook and manage shared
groceries. Singapore had **1,487,100 resident households in 2025**, a broad market
ceiling rather than a count of likely customers. [1] In 2023, average household
spending was **S$456/month on food and non-alcoholic beverages**, showing the
relevance of everyday food decisions without establishing demand for software.
[2] NEA's 2016–2017 household study associated some spoiled-food disposal with
overbuying and forgotten fridge contents; this is historical motivation, not
evidence that Cookish reduces waste. [3]

A serviceable segment must jointly satisfy cooking frequency, grocery
responsibility, interface access and catalogue fit. Assuming 10–30% of resident
households meet these conditions gives **148,710–446,130 households**. These are
planning scenarios, not measured demand. Obtainable adoption should be estimated
from qualified outreach, trial uptake and retention, with paid conversion tested
separately.

## Alternatives and reason to pay

Free SuperCook already matches recipes to pantry ingredients, while Samsung
Food+ advertises expiry-prioritised searches and automated pantry updates. [4,5]
Cookish therefore tests a narrower proposition: whether a focused reviewed
catalogue, explicit stock uncertainty and confirmed cooking/shopping updates
reduce total decision and maintenance effort. One Cooklist reviewer, Heidi Wright
(29 June 2026), reported slow quantity edits; Plan to Eat's own account of its
retired automatic Pantry explains how stale records could hide needed purchases.
These sources motivate usability tests; they do not establish prevalence or
Cookish's superiority. [6,7]

The proposed model remains **US$4.99 per household per month**, with shared manual
inventory, core Cook/Shop, dietary checks and normal preference learning free.
Payment would provide recurring assisted-entry convenience, initially considered
as **20 imports/month**, alongside a **three-import one-time free trial**. These
limits and billing are proposals. At US$59.88 over twelve monthly payments, the
price exceeds Plan to Eat's US$49 annual website plan, so it cannot be justified
by price comparison alone. [8] User evaluation must include free alternatives,
correction effort, reasons to remain free and willingness to pay; a small
usability sample cannot establish commercial demand.

## Preliminary cost per household and user

A model using published Singapore AWS rates and assumed usage gives the following
**gross monthly infrastructure estimates in USD**. The base case assumes two
active login accounts per household, 10% paying households, 300 non-AI requests
per household and ten imports per paying household each month. Model cost is
assumed at US$0.01 per attempt with 1.1 attempts per import; deployed-provider
usage has not been costed here. Free-trial usage is included. [9]

| Active households | Total/month | Per active household | Per active login | Allocated per paying household |
|---:|---:|---:|---:|---:|
| 100 | 34.55 | 0.345 | 0.173 | 3.455 |
| 1,000 | 85.96 | 0.086 | 0.043 | 0.860 |
| 10,000 | 600.08 | 0.060 | 0.030 | 0.600 |

Paying-household allocation includes supporting free households. At 1,000
households, low/high usage assumptions produce **US$65.11–226.39/month**. Credits
and free allowances are not deducted; fees, taxes, labor, acquisition and capacity
upgrades are excluded. The 10,000-household calculation does not demonstrate that
the specified micro database supports that load. Role 3's deployment measurements
and Role 4's model charges must replace the assumptions before reporting actual
cost or concluding commercial viability. [9]

## References

Accessed 24 October 2026; Lambda price records in reference 9 were refreshed on
7 November 2026. Retain the references used in the final report itself;
the longer research pack is supporting repository material.

1. Singapore Department of Statistics. [Resident Households](https://www.singstat.gov.sg/find-data/explore-data-themes/households/resident-households), 2025 data, released 30 June 2026.
2. Singapore Department of Statistics. [Key Indicators of the Household Expenditure Survey 2023](https://www.singstat.gov.sg/files/a379514d-c004-46ad-9c12-1046b4e33ba0.pdf), p.106; report published 28 November 2024.
3. National Environment Agency. [Half of Food Waste Thrown Away by Singapore Households Can Be Prevented](https://www.nea.gov.sg/media/news/news/index/half-of-food-waste-thrown-away-by-singapore-households-can-be-prevented-nea-household-waste-study), 3 December 2017.
4. AMR Systems LLC. [SuperCook, Singapore App Store](https://apps.apple.com/sg/app/supercook-recipe-by-ingredient/id1477747816), current listing.
5. Samsung Food. [Food+](https://samsungfood.com/food-plus/), product description, undated.
6. Cooklist Inc. [Google Play listing and reviews](https://play.google.com/store/apps/details?hl=en_US&id=com.cooklist.android), Heidi Wright review dated 29 June 2026.
7. Plan to Eat. [A Digital Pantry Inventory: Does It Really Help?](https://learn.plantoeat.com/help/a-digital-pantry-inventory-does-it-really-help), updated 22 October 2025; removal date not established.
8. Plan to Eat. [Pricing](https://www.plantoeat.com/pricing/), current website plans.
9. Cookish Role 5. [Cost model, assumptions and AWS price sources](../eval/business_case/README.md), Lambda assumptions updated 7 November 2026, with [selected AWS rate records](../eval/business_case/aws-rates.json) and [reproducible results](../eval/business_case/results.json). AWS documents the [public bulk pricing API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api.html).
