# Cookish recipe catalogue: Wenlong's review pack

**48 complete recipe drafts: 28 base meals and 20 variants, using 42 canonical ingredients. 48 still await human review.**

This is the proposed coursework catalogue, ready for content review. It meets the SPEC's **40–60 recipes including variants** size target once approved; the number marked human-reviewed is currently 0. Recipe quantities and instructions are original AI-assisted project drafts. Named creator pages informed dish concepts and techniques; they do not validate these exact formulations. There have been no cooking trials, nutrition calculations or user acceptance tests.

## Why this selection fits Cookish

- **Meals that Shop can count:** every suggestion includes rice, noodles or potato instead of quietly assuming the user will add a separate staple. All base quantities serve two. This is a portion-design choice, not a claim of nutritional completeness.
- **A manageable shared pantry:** rice, eggs, tofu, chicken and common vegetables recur across dishes. The 42-name ingredient list stays small enough for Role 2 to catalogue and Role 4 to match; it is not a price-verified shopping list.
- **Useful recommendation choices:** there are distinct soups, rice dishes, noodles, curries and assembled meals, with meaningful less-oil, quicker, extra-vegetable and added-protein variants.
- **Singapore home-cooking context:** familiar rice/noodle/vegetable combinations are prioritised. The mix is weighted toward Chinese home cooking, with Indian, Malay-inspired and other options; it is not representative coverage of every cuisine. Simplified dishes are named plainly rather than claimed to be authentic versions.
- **Explicit appliance constraints:** stove meals dominate; one microwave-only meal, one rice-cooker-only meal and a no-appliance assembled meal exercise equipment filtering. Rice-cooker compatibility needs a model-specific check.

The selection is suitable as a bounded prototype catalogue. It cannot guarantee results for every combination of allergies, dietary restrictions, equipment and time limits. Those cases still need the agreed no-result/relaxation behaviour. A load test with more simultaneous sessions can reuse this catalogue: increasing recipe count does not by itself demonstrate service scale-out.

## Review priorities

1. Review the shortlist below for dishes you actually want to include. Check the simplified flavours, repetition, portions and the choice of cod and soba against your intended users' budgets and preferences.
2. Open each numbered recipe for its ingredients, method, reference scope and specific review questions. Ingredients marked optional still participate in stored-recipe dietary/allergen checks under the current contract.
3. Trial the appliance-specific meals, steamed custards, low-oil methods and rice dishes first. All timings are estimates for two servings. Larger portions may need more cookware or time, even when ingredient quantities scale.
4. Record reviewer, date, corrections and any cooking-trial evidence in the review PR. Set reviewed: true only for recipes actually reviewed; an automated schema check cannot approve culinary quality.

Freshly cooked rice time is included where uncooked rice is an ingredient. Recipes listing **cooked rice** assume it is already prepared; their times exclude its original cooking and cooling. The cold salad requires safely chilled rice. No raw/cooked rice yield conversion is assumed.

## Coverage and authoring rules

- 16 meals are estimated at 30 minutes or less; 32 need longer. Porridge takes about 60 minutes.
- Cuisine labels: chinese 29, indian 4, japanese 2, malay 2, other 7, western 4. These are catalogue groupings, not authenticity certifications.
- low_oil: 17 recipes, each with at most **5 ml of added cooking oils per two servings**, including sesame oil. This does not mean low total fat.
- vegetable_rich: 27 recipes, each with at least **300 g of counted vegetables per two servings**. Counted here: bok choy, broccoli, cabbage, carrot, cauliflower, chye sim, cucumber, fresh shiitake, long bean, pumpkin, spinach, tomato and water spinach. Potato, peas, pulses, rice and aromatics (including onion, garlic, ginger and spring onion) are excluded from this editorial threshold.
- high_protein: 3 explicit **added-protein variants only**: chicken added to egg fried rice, eggs added to vegetable bee hoon, and tofu added to steamed egg. The existing enum is used as an internal adjustment marker. It is not a measured high-protein nutrition claim; absence does not mean a dish is low in protein. Swapping tofu for chicken does not automatically earn this tag.
- light, rich, spicy and soupy describe the drafted cooking style or texture. Diet suitability and allergens must come from Role 2's authoritative ingredient metadata, including sauces, noodles and optional ingredients.

These rules make the authored examples consistent; the recommendation services and learning updates still need implementation. A variant relationship alone does not prove that it satisfies every adjustment: compare actual time, tags and hard constraints.

## Shortlist

| # | Meal | Estimated total / active minutes | Relationship |
|---|---|---|---|
| 01 | [Tomato and egg rice bowls](#tomato-egg-stir-fry) | 35 / 20 | Base |
| 02 | [Tomato and egg rice bowls with less oil](#tomato-egg-stir-fry-less-oil) | 35 / 20 | less oil (#01) |
| 03 | [Cabbage and tofu rice bowls](#cabbage-tofu-stir-fry) | 35 / 20 | Base |
| 04 | [Cabbage and tofu rice bowls with less oil](#cabbage-tofu-stir-fry-less-oil) | 35 / 20 | less oil (#03) |
| 05 | [Garlic water spinach and tofu rice bowls](#garlic-water-spinach) | 35 / 20 | Base |
| 06 | [One-pot ginger chicken and bok choy rice](#ginger-chicken-rice) | 45 / 20 | Base |
| 07 | [Tofu, mushroom and cabbage noodle soup](#tofu-mushroom-soup) | 30 / 15 | Base |
| 08 | [Tomato and red lentil dhal with rice](#red-lentil-dhal) | 40 / 15 | Base |
| 09 | [Egg fried rice with vegetables](#egg-fried-rice) | 20 / 20 | Base |
| 10 | [Steamed ginger cod with broccoli and rice](#steamed-ginger-fish) | 35 / 15 | Base |
| 11 | [Ginger chicken and bok choy rice with less oil](#ginger-chicken-rice-less-oil) | 45 / 15 | Less added oil (#06) |
| 12 | [One-pot tofu and mushroom rice](#tofu-mushroom-rice) | 40 / 15 | Tofu and mushroom alternative (#06) |
| 13 | [Quick tomato and egg rice](#quicker-tomato-egg-rice) | 20 / 20 | Quicker with cooked rice (#01) |
| 14 | [Egg fried rice with extra cabbage and carrot](#cabbage-carrot-egg-fried-rice) | 25 / 25 | More vegetables (#09) |
| 15 | [Tofu and vegetable fried rice](#tofu-vegetable-fried-rice) | 25 / 25 | Tofu instead of egg (#09) |
| 16 | [Chicken, egg and vegetable fried rice](#chicken-vegetable-fried-rice) | 30 / 30 | More protein with added chicken (#09) |
| 17 | [Bok choy and tofu bee hoon soup](#rice-vermicelli-tofu-soup) | 25 / 15 | Base |
| 18 | [Bok choy and chicken bee hoon soup](#rice-vermicelli-chicken-soup) | 30 / 20 | Chicken alternative (#17) |
| 19 | [Cabbage and carrot bee hoon](#bee-hoon-cabbage) | 25 / 20 | Base |
| 20 | [Egg, cabbage and carrot bee hoon](#bee-hoon-egg) | 30 / 25 | More protein with egg (#19) |
| 21 | [Microwave broccoli and chickpea rice](#microwave-broccoli-chickpea-rice) | 20 / 10 | Base |
| 22 | [Rice-cooker bok choy and tofu rice](#rice-cooker-bok-choy-tofu-rice) | 55 / 10 | Base |
| 23 | [Chye sim and egg bee hoon soup](#chye-sim-egg-bee-hoon) | 25 / 15 | Base |
| 24 | [Tofu and broccoli stir-fry with rice](#tofu-broccoli-stir-fry) | 35 / 20 | Base |
| 25 | [Chicken and broccoli stir-fry with rice](#chicken-broccoli-stir-fry) | 35 / 20 | chicken (#24) |
| 26 | [Mushroom omelette with rice](#mushroom-omelette) | 35 / 20 | Base |
| 27 | [Tomato and onion omelette with rice](#tomato-onion-omelette) | 35 / 20 | tomato and onion (#26) |
| 28 | [Steamed egg with rice](#steamed-egg) | 35 / 15 | Base |
| 29 | [Steamed egg and tofu with rice](#steamed-egg-tofu) | 40 / 15 | add tofu (#28) |
| 30 | [Ginger chicken and potato soup](#ginger-chicken-soup) | 40 / 15 | Base |
| 31 | [Fish and tomato vermicelli soup](#fish-tomato-soup) | 30 / 15 | Base |
| 32 | [Red lentil and spinach dhal with rice](#lentil-spinach-dhal) | 45 / 20 | add spinach (#08) |
| 33 | [Potato and cauliflower curry with rice](#potato-cauliflower-curry) | 45 / 20 | Base |
| 34 | [Chickpea and tomato curry with rice](#chickpea-tomato-curry) | 40 / 20 | Base |
| 35 | [Coconut tofu and vegetable curry with rice](#coconut-tofu-curry) | 40 / 20 | Base |
| 36 | [Coconut chicken and vegetable curry with rice](#coconut-chicken-curry) | 45 / 20 | chicken (#35) |
| 37 | [Tempeh and long bean stir-fry with rice](#tempeh-long-bean-stir-fry) | 40 / 25 | Base |
| 38 | [Tempeh and cabbage stir-fry with rice](#tempeh-cabbage-stir-fry) | 35 / 20 | cabbage variation (#37) |
| 39 | [Chilli tofu with rice](#sambal-tofu) | 40 / 25 | Base |
| 40 | [Chilli prawns with rice](#sambal-prawn) | 35 / 20 | prawn variation (#39) |
| 41 | [Lemon pepper fish with potatoes and carrots](#lemon-pepper-fish) | 35 / 20 | Base |
| 42 | [Lemon pepper chicken with potatoes and carrots](#lemon-pepper-chicken) | 40 / 25 | chicken variation (#41) |
| 43 | [Pumpkin, potato and red lentil soup](#pumpkin-lentil-soup) | 45 / 20 | Base |
| 44 | [Ginger chicken rice porridge](#chicken-rice-porridge) | 60 / 20 | Base |
| 45 | [Mushroom and tofu rice porridge](#mushroom-rice-porridge) | 60 / 20 | mushroom and tofu variation (#44) |
| 46 | [Cucumber, tomato and chickpea rice salad](#cucumber-tomato-chickpea-salad) | 15 / 15 | Base |
| 47 | [Sesame soba with tofu and vegetables](#sesame-soba-tofu) | 25 / 20 | Base |
| 48 | [Sesame soba with egg and vegetables](#sesame-soba-egg) | 30 / 20 | egg variation (#47) |

## Shared food-handling references

These sources inform general handling guidance; they are not endorsements of the recipes or substitutes for cooking trials.

- [SFA: Fried Rice Syndrome](https://www.sfa.gov.sg/food-safety-tips/food-risk-concerns/risk-at-a-glance/fried-rice-syndrome): promptly chill cooked rice below 4°C. Reheating cannot reliably remove hazards caused by poor storage.
- [SFA: Food Safety Tips](https://www.sfa.gov.sg/food-safety-tips/safe-food-practices/food-safety-tips): thorough cooking, prompt storage, and reheating guidance. Drafts use a 75°C-for-two-minutes thermometer check where specified; microwave heating needs stirring and checks in several places.
- [SFA: December 2024 food safety advisory](https://www.sfa.gov.sg/docs/default-source/circulars/others/2024/advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf): temperature/time guidance used as the conservative drafting benchmark for raw meat and fish. Actual times depend on equipment, portion and thickness.

Reference pages accessed for this research: **2026-10-20**. Dish-specific creator references and their limited use appear in every card below. The project does not import source photographs, ratings or nutrition panels, and does not assert a licence to redistribute third-party recipe text.

<a id="tomato-egg-stir-fry"></a>

## 01. Tomato and egg rice bowls

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** A recognisable home-cooked rice meal using counted eggs and shared produce; serves as the adjustment baseline.

**Variant/design choice:** Baseline: 15 ml added oil and uncooked rice for two servings. Separate less-oil and quicker variants retain the main topping.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 200 g | — |
| tomato | 300 g | cut into wedges |
| egg | 3 pcs | beaten |
| canola oil | 15 ml | — |
| salt | 1 g | Optional.  |
| water | for the rice according to its packet and a splash for the tomatoes | — |
| spring onion | 10 g | Optional. thinly sliced |

**Method**

1. Start the uncooked rice in a covered saucepan using water and cooking time from the rice packet. Prepare the topping while it cooks; keep the finished rice hot and serve both components together.
2. Warm two thirds of the oil in a nonstick pan. Stir the beaten eggs over medium heat until set, then transfer them to a clean bowl.
3. Use the remaining oil to soften the tomatoes for a few minutes. Add a splash of water, cover and cook until the wedges release a sauce.
4. Fold the eggs into the tomatoes. Add the salt if using and heat until the eggs are completely cooked and the topping is hot throughout.
5. Divide the cooked rice between bowls, spoon over the topping and add the spring onion if using. Serve immediately.

**Research references**

- [The Woks of Life — Chinese Tomato Egg Stir-fry](https://thewoksoflife.com/stir-fried-tomato-and-egg/) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Check rice yield, seasoning and the 35-minute estimate with parallel cooking; eggs are counted, not converted from grams.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tomato-egg-stir-fry.yaml) · reviewed: false

<a id="tomato-egg-stir-fry-less-oil"></a>

## 02. Tomato and egg rice bowls with less oil

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** A controlled less-oil alternative with the same eggs, tomatoes and rice.

**Variant/design choice:** Added oil decreases from 15 ml to 5 ml per two servings; covered cooking uses water instead of extra oil.

**Tags:** light, low_oil, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 200 g | — |
| tomato | 300 g | cut into wedges |
| egg | 3 pcs | beaten |
| canola oil | 5 ml | — |
| salt | 1 g | Optional.  |
| water | for the rice according to its packet and small splashes to soften the tomatoes | — |
| spring onion | 10 g | Optional. thinly sliced |

**Method**

1. Start the uncooked rice in a covered saucepan using water and cooking time from the rice packet. Prepare the topping while it cooks; keep the finished rice hot and serve both components together.
2. Warm the oil in a nonstick pan over medium-low heat. Gently stir the beaten eggs until set, then put them in a clean bowl.
3. Add the tomatoes and a small splash of water to the same pan. Cover until softened, adding a little more water only if the pan dries out.
4. Remove the lid briefly to thicken the tomato juices. Return the eggs, add the salt if using and heat until completely cooked.
5. Spoon the topping over the cooked rice and finish with spring onion if using. Serve immediately.

**Research references**

- [The Woks of Life — Chinese Tomato Egg Stir-fry](https://thewoksoflife.com/stir-fried-tomato-and-egg/) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Test sticking and texture on an ordinary nonstick pan; low_oil describes the added oil only.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tomato-egg-stir-fry-less-oil.yaml) · reviewed: false

<a id="cabbage-tofu-stir-fry"></a>

## 03. Cabbage and tofu rice bowls

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** A plant-based ingredient combination with substantial tofu, shared cabbage and a complete rice portion.

**Variant/design choice:** Baseline for the less-oil version; the source's broader dish is only a cabbage-cooking reference, not a copied tofu meal.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 160 g | — |
| cabbage | 300 g | thinly sliced |
| firm tofu | 300 g | drained and cubed |
| garlic | 8 g | Optional. finely chopped |
| canola oil | 15 ml | — |
| soy sauce | 10 ml | Optional.  |
| water | for the rice according to its packet and splashes for the cabbage | — |

**Method**

1. Start the uncooked rice in a covered saucepan using water and cooking time from the rice packet. Prepare the topping while it cooks; keep the finished rice hot and serve both components together.
2. Dry the tofu surfaces with a clean kitchen towel. Warm two thirds of the oil in a nonstick pan and turn the tofu gently until lightly coloured.
3. Add the remaining oil and garlic if using, followed by the cabbage. Stir until the leaves begin to wilt.
4. Add a splash of water and cover briefly until the cabbage is tender and the tofu is hot throughout. Add the soy sauce if using.
5. Divide the rice and topping between bowls. Serve immediately while hot.

**Research references**

- [The Woks of Life — Chinese Cabbage Stir-Fry](https://thewoksoflife.com/chinese-cabbage-stir-fry/) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Check tofu breakage and cabbage tenderness. Optional soy sauce remains part of the stored ingredient set for hard filtering.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/cabbage-tofu-stir-fry.yaml) · reviewed: false

<a id="cabbage-tofu-stir-fry-less-oil"></a>

## 04. Cabbage and tofu rice bowls with less oil

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** Tests a cooking-method refinement without changing the core ingredients or servings.

**Variant/design choice:** Same ingredient quantities as the base except added oil decreases from 15 ml to 5 ml; tofu is warmed through rather than browned.

**Tags:** light, low_oil, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 160 g | — |
| cabbage | 300 g | thinly sliced |
| firm tofu | 300 g | drained and cubed |
| garlic | 8 g | Optional. finely chopped |
| canola oil | 5 ml | — |
| soy sauce | 10 ml | Optional.  |
| water | for the rice according to its packet and splashes for the cabbage | — |

**Method**

1. Start the uncooked rice in a covered saucepan using water and cooking time from the rice packet. Prepare the topping while it cooks; keep the finished rice hot and serve both components together.
2. Warm the oil in a nonstick pan and briefly stir the garlic if using. Add the cabbage and a splash of water.
3. Cover until the cabbage starts to soften. Add the tofu and turn gently, adding a little more water only if necessary.
4. Cover until the tofu is hot throughout and the cabbage is tender. Add soy sauce if using, then uncover briefly to reduce excess liquid.
5. Serve the topping over the cooked rice immediately.

**Research references**

- [The Woks of Life — Chinese Cabbage Stir-Fry](https://thewoksoflife.com/chinese-cabbage-stir-fry/) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Compare the softer tofu texture against the base; check that the method works with the smaller oil amount.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/cabbage-tofu-stir-fry-less-oil.yaml) · reviewed: false

<a id="garlic-water-spinach"></a>

## 05. Garlic water spinach and tofu rice bowls

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** Uses a recognisable local leafy vegetable while adding tofu and rice so it can occupy one Shop meal slot.

**Variant/design choice:** This is an original garlic/tofu composition, not kangkung belacan: no shrimp paste, chilli paste or dried shrimp is implied.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 160 g | — |
| water spinach | 300 g | washed thoroughly; separate chopped stems from leaves |
| firm tofu | 300 g | drained and cubed |
| garlic | 12 g | finely chopped |
| canola oil | 10 ml | — |
| soy sauce | 10 ml | Optional.  |
| water | for the rice according to its packet and a splash for the greens | — |

**Method**

1. Start the uncooked rice in a covered saucepan using water and cooking time from the rice packet. Prepare the topping while it cooks; keep the finished rice hot and serve both components together.
2. Heat half the oil in a pan and turn the tofu until lightly coloured and hot throughout. Set it aside in a clean bowl.
3. Add the remaining oil, garlic and water-spinach stems. Stir briefly, then add the leaves and a splash of water.
4. Cover for a few minutes, then stir until the stems are tender and the leaves are fully cooked.
5. Return the tofu, add soy sauce if using and heat everything together. Serve over the cooked rice.

**Research references**

- [Nyonya Cooking — Kangkung Belacan](https://www.nyonyacooking.com/recipes/kangkung-belacan~sL-aXO7Xn) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Review the mild flavour and vegetable preparation; confirm the canonical kangkong alias with Role 2.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/garlic-water-spinach.yaml) · reviewed: false

<a id="ginger-chicken-rice"></a>

## 06. One-pot ginger chicken and bok choy rice

**2 servings · 45 min total / 20 min active · equipment: stove**

**Why include it:** A single-pan rice meal with a distinct protein and leafy vegetable; makes repeated ingredients useful across the basket.

**Variant/design choice:** Baseline for the no-added-oil simmered variant, with matched rice, chicken, bok choy and seasonings.

**Tags:** light.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| chicken thigh | 300 g | skinless, boneless and cut into small even pieces |
| uncooked rice | 200 g | — |
| bok choy | 200 g | washed; stems sliced and leaves chopped separately |
| ginger | 20 g | peeled and sliced |
| garlic | 8 g | Optional. finely chopped |
| spring onion | 10 g | Optional. thinly sliced |
| canola oil | 10 ml | — |
| soy sauce | 15 ml | Optional.  |
| water | 400 ml | — |

**Method**

1. Rinse and drain the rice. Prepare vegetables on a clean board; use separate utensils and a board for the raw chicken.
2. Warm the oil in a lidded saucepan. Stir in ginger and garlic if using, then add chicken and turn it until the surfaces change colour.
3. Add the rice, measured water, bok choy stems and soy sauce if using. Bring to a boil, cover and cook gently for about 20 minutes; check the rice packet and add a little water if necessary.
4. Place the bok choy leaves on top and cover again until wilted and the rice is tender. Confirm the thickest chicken pieces reach at least 75 C for 2 minutes with a food thermometer; continue cooking if needed.
5. Leave covered off the heat for 5 minutes, then gently mix. Add spring onion if using and serve immediately.

**Research references**

- [RecipeTin Eats — One Pot Chinese Chicken and Rice](https://www.recipetineats.com/one-pot-chinese-chicken-and-rice/) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Test the rice/water ratio with the team's actual rice and saucepan. Time is an estimate, not a substitute for checking chicken.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/ginger-chicken-rice.yaml) · reviewed: false

<a id="tofu-mushroom-soup"></a>

## 07. Tofu, mushroom and cabbage noodle soup

**2 servings · 30 min total / 15 min active · equipment: stove**

**Why include it:** A mushroom-forward noodle soup gives a different taste/texture from dry stir-fries while using overlapping tofu and cabbage.

**Variant/design choice:** No added cooking oil. This project broth omits the reference recipe's egg and other additions; it is not a reproduction.

**Tags:** light, soupy, low_oil, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| rice vermicelli | 150 g | dry; prepare according to packet |
| firm tofu | 300 g | drained and cubed |
| fresh shiitake mushroom | 150 g | cleaned and sliced; tough stems removed |
| cabbage | 200 g | thinly sliced |
| ginger | 10 g | peeled and sliced |
| spring onion | 10 g | Optional. thinly sliced |
| soy sauce | 15 ml | Optional.  |
| water | 1000 ml | measured cooking water; additional water for rinsing or preparing the noodles/rice as instructed, plus small top-ups if needed |

**Method**

1. Prepare the rice vermicelli as directed on its packet, then drain. Keep it separate while the broth cooks.
2. Bring the measured broth water to a boil with the ginger and mushrooms. Simmer until the mushrooms are tender.
3. Add cabbage and tofu. Bring the soup back to a boil, then simmer until the cabbage is soft and the tofu is hot throughout.
4. Add the prepared noodles and soy sauce if using. Heat together, divide between bowls and add spring onion if using.

**Research references**

- [The Woks of Life — Tofu Soup](https://thewoksoflife.com/tofu-soup/) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Taste the broth without stock cubes and check noodle absorption; every stock ingredient would need an explicit catalogue row if added later.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tofu-mushroom-soup.yaml) · reviewed: false

<a id="red-lentil-dhal"></a>

## 08. Tomato and red lentil dhal with rice

**2 servings · 40 min total / 15 min active · equipment: stove**

**Why include it:** A pantry-oriented meal with a different cuisine and protein source, useful when fresh leafy stock is unavailable.

**Variant/design choice:** Baseline for the spinach-added variant. The dry-lentil amount is not interchangeable with canned or cooked lentils.

**Tags:** soupy.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 150 g | — |
| red lentil | 160 g | dry split lentils, rinsed and drained |
| onion | 100 g | finely chopped |
| tomato | 200 g | chopped |
| garlic | 8 g | Optional. finely chopped |
| turmeric powder | 2 g | — |
| cumin powder | 2 g | — |
| canola oil | 10 ml | — |
| salt | 1 g | Optional.  |
| water | for the rice according to its packet and enough to simmer the lentils | — |

**Method**

1. Start the uncooked rice in a covered saucepan using water and cooking time from the rice packet. Prepare the topping while it cooks; keep the finished rice hot and serve both components together.
2. Warm the oil in another saucepan and soften the onion. Stir in garlic if using, then turmeric and cumin briefly without burning them.
3. Add the tomatoes and stir until they begin to break down. Add the lentils and enough water to cover them generously.
4. Bring to a boil and simmer, stirring occasionally, until the lentils are fully soft. Add water as they absorb it to maintain a spoonable consistency; allow about 20 to 25 minutes.
5. Add salt if using and serve the dhal with the freshly cooked rice.

**Research references**

- [Swasthi's Recipes — Red Lentil Curry](https://www.indianhealthyrecipes.com/red-lentil-curry/) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Review spice balance, finished consistency and water needs; recipe times assume split red lentils.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/red-lentil-dhal.yaml) · reviewed: false

<a id="egg-fried-rice"></a>

## 09. Egg fried rice with vegetables

**2 servings · 20 min total / 20 min active · equipment: stove**

**Why include it:** The cooked-rice baseline gives a quick path and supports controlled vegetable and chicken additions.

**Variant/design choice:** Base quantities are 400 g cooked rice, 2 eggs, 100 g carrot and 80 g peas for two servings.

**Tags:** light.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cooked rice | 400 g | already cooked rice; if stored, it must have been chilled promptly below 4 C and kept refrigerated; break up clumps |
| egg | 2 pcs | beaten |
| carrot | 100 g | Optional. cut into small dice |
| frozen pea | 80 g | Optional.  |
| garlic | 8 g | Optional. finely chopped |
| canola oil | 15 ml | — |
| soy sauce | 15 ml | Optional.  |
| spring onion | 10 g | Optional. thinly sliced |

**Method**

1. Use already cooked rice that has been handled safely; the time here excludes cooking rice from dry. Do not use rice with uncertain storage history.
2. Heat one third of the oil in a large nonstick pan. Stir the beaten eggs until set and transfer them to a clean bowl.
3. Add the remaining oil. Stir-fry the garlic, carrot and peas if using until the vegetables are tender.
4. Add the rice, break up clumps and stir until hot throughout. Fold in the eggs and soy sauce if using. For refrigerated rice, ensure the whole mixture reaches at least 75 C for 2 minutes; reheat only once.
5. Add spring onion if using and serve immediately. Heating cannot make poorly stored rice safe.

**Research references**

- [Made With Lau — Fried Rice](https://www.madewithlau.com/recipes/egg-fried-rice) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Review safe cooked-rice handling and the 20-minute estimate; do not present it as a raw-rice recipe.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/egg-fried-rice.yaml) · reviewed: false

<a id="steamed-ginger-fish"></a>

## 10. Steamed ginger cod with broccoli and rice

**2 servings · 35 min total / 15 min active · equipment: stove, steamer**

**Why include it:** A fish-based meal with a genuine steamer requirement and no added oil supports hard equipment filtering.

**Variant/design choice:** Cod fillets, broccoli and rice are project choices; this is not the source's whole-fish recipe or finishing-oil method.

**Tags:** light, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 160 g | — |
| cod fillet | 350 g | boneless; thaw in the refrigerator if frozen |
| broccoli | 250 g | cut into small florets |
| ginger | 20 g | peeled and finely sliced |
| soy sauce | 15 ml | Optional.  |
| spring onion | 15 g | Optional. thinly sliced |
| black pepper | 1 g | Optional.  |
| water | for the rice according to its packet and the steamer according to its instructions | — |

**Method**

1. Start the uncooked rice in a covered saucepan using water and cooking time from the rice packet. Prepare the topping while it cooks; keep the finished rice hot and serve both components together.
2. Set up the steamer with water according to its instructions. Put the fish on a heatproof plate and scatter ginger over it; add soy sauce and black pepper if using.
3. When the steamer is producing steady steam, cover and cook the fish. Allow roughly 10 to 15 minutes, adjusting for thickness, and continue until a clean thermometer in the thickest part reads at least 75 C for 2 minutes.
4. Steam the broccoli until tender, using a separate tray or steaming it after the fish if space is limited. Keep the cooked components hot.
5. Check for any remaining bones, add spring onion if using and serve with the rice and broccoli immediately.

**Research references**

- [Made With Lau — Steamed Fish with Ginger & Scallion](https://www.madewithlau.com/recipes/steamed-fish-ginger-scallion) — Dish or technique background only; quantities, meal composition and prose are original project drafts.

**Review focus:** Test fillet thickness and steamer capacity. Confirm all fish is thoroughly cooked and the rice remains hot if components are cooked sequentially.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/steamed-ginger-fish.yaml) · reviewed: false

<a id="ginger-chicken-rice-less-oil"></a>

## 11. Ginger chicken and bok choy rice with less oil

**2 servings · 45 min total / 15 min active · equipment: stove**

**Why include it:** Keeps the familiar ginger chicken rice meal and its vegetables while using a simmering method without added cooking oil.

**Variant/design choice:** Less-oil variant of the ginger chicken rice base; retain the same chicken, rice and vegetable amounts.

**Tags:** light, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 200 g | white rice, rinsed and drained |
| chicken thigh | 300 g | boneless and skinless, cut into small bite-size pieces |
| bok choy | 200 g | washed, stems thinly sliced and leaves cut separately |
| ginger | 20 g | peeled and finely sliced |
| garlic | 8 g | Optional. finely chopped |
| soy sauce | 15 ml | Optional.  |
| spring onion | 10 g | Optional. thinly sliced |
| water | 400 ml | — |

**Method**

1. Put the rice, water, ginger, garlic if using, and soy sauce if using in a heavy saucepan with a close-fitting lid. Stir once and distribute the chicken and bok choy stems evenly over the rice.
2. Bring to a full simmer, cover and lower the heat. Simmer for about 20 to 25 minutes, checking that the rice is becoming tender; if the pan dries before the rice is cooked, add a little more drinking water.
3. Check the centre of several of the largest chicken pieces with a clean food thermometer. Continue covered cooking until they reach at least 75 C for 2 minutes; elapsed time alone does not establish doneness.
4. Fold in the bok choy leaves, cover and cook for another 2 to 3 minutes until wilted. Turn off the heat, rest covered for 5 minutes, fluff gently, and finish with spring onion if using.

**Research references**

- [RecipeTin Eats: Ginger chicken and rice](https://www.recipetineats.com/ginger-chicken-and-rice/) — concept/technique reference only
- [Singapore Food Agency: Advisory on Food Safety Practices, December 2024](https://www.sfa.gov.sg/docs/default-source/circulars/others/2024/advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf) — chicken cooking temperature reference; not a recipe endorsement

**Review focus:** Check rice water absorption, chicken temperature, bok choy texture and whether the zero-added-oil flavour is acceptable.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/ginger-chicken-rice-less-oil.yaml) · reviewed: false

<a id="tofu-mushroom-rice"></a>

## 12. One-pot tofu and mushroom rice

**2 servings · 40 min total / 15 min active · equipment: stove**

**Why include it:** A substantial plant-based rice meal using the same aromatics and grain as ginger chicken rice.

**Variant/design choice:** Vegetarian alternative in the ginger rice family, rather than a claim that changing protein alone increases protein content.

**Tags:** light, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 200 g | white rice, rinsed and drained |
| firm tofu | 300 g | plain tofu, drained and cut into cubes |
| fresh shiitake mushroom | 180 g | tough stems removed and caps sliced |
| ginger | 15 g | peeled and finely sliced |
| garlic | 8 g | Optional. finely chopped |
| spring onion | 10 g | Optional. thinly sliced |
| soy sauce | 15 ml | — |
| canola oil | 5 ml | — |
| water | 350 ml | — |

**Method**

1. Warm the oil in a heavy saucepan. Cook the ginger and garlic if using for about 1 minute, then add the mushrooms and stir for 2 minutes.
2. Stir in the rice, water and soy sauce. Place the tofu evenly over the top and bring the liquid to a steady simmer.
3. Cover and cook over low heat for about 20 minutes until the rice is tender and the tofu is hot throughout. If the pan becomes dry while the rice is still firm, add a little drinking water and continue cooking.
4. Take the pan off the heat and leave covered for 5 minutes. Fold the tofu and mushrooms gently through the rice and scatter over the spring onion if using.

**Research references**

- [The Foodie Takes Flight: One Pot Mushroom Rice with Spicy Miso Sauce](https://thefoodietakesflight.com/one-pot-mushroom-rice/) — concept/technique reference only

**Review focus:** Check the final rice texture with fresh mushrooms, tofu firmness and seasoning; the simplified sauce differs from the reference.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tofu-mushroom-rice.yaml) · reviewed: false

<a id="quicker-tomato-egg-rice"></a>

## 13. Quick tomato and egg rice

**2 servings · 20 min total / 20 min active · equipment: stove**

**Why include it:** Provides the same recognisable tomato and egg meal when safely stored cooked rice is already available.

**Variant/design choice:** Quicker variant: 20-minute estimate replaces cooking rice from dry; pre-cooking and cooling rice are not included because cooked rice is the stated input.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cooked rice | 400 g | already cooked rice, cooled promptly and refrigerated below 4 C if not freshly cooked; do not use rice left unrefrigerated or with uncertain storage |
| tomato | 300 g | cut into small wedges |
| egg | 3 pcs | beaten |
| canola oil | 15 ml | — |
| salt | 1 g | Optional.  |
| spring onion | 10 g | Optional. thinly sliced |
| water | 60 ml | — |

**Method**

1. Break up the cooked rice clumps before starting. Heat two thirds of the oil in a large nonstick frying pan, scramble the eggs until fully set, then transfer them to a clean plate.
2. Put the remaining oil and tomatoes in the pan. Stir for 2 minutes, add half the water, cover and cook for about 3 minutes until the tomatoes soften.
3. Add the cooked rice, remaining water and salt if using. Fold through the tomatoes, cover and heat for about 4 to 6 minutes, stirring to warm the rice evenly.
4. Return the eggs and spring onion if using and stir gently until combined. Stir and check several parts with a clean food thermometer; keep the rice at 75 C or hotter for at least 2 minutes. Continue heating if necessary and serve immediately. Reheating cannot make poorly stored rice safe.

**Research references**

- [The Woks of Life: Chinese Tomato Egg Stir-fry](https://thewoksoflife.com/stir-fried-tomato-and-egg/) — concept/technique reference only
- [Singapore Food Agency: Fried Rice Syndrome](https://www.sfa.gov.sg/food-safety-tips/food-risk-concerns/risk-at-a-glance/fried-rice-syndrome) — food handling reference; not a recipe endorsement
- [Singapore Food Agency: Food Safety Tips](https://www.sfa.gov.sg/food-safety-tips/safe-food-practices/food-safety-tips) — reheating reference; not a recipe endorsement

**Review focus:** Compare against the base meal, check whether the rice becomes too wet, and test the timing including safe reheating.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/quicker-tomato-egg-rice.yaml) · reviewed: false

<a id="cabbage-carrot-egg-fried-rice"></a>

## 14. Egg fried rice with extra cabbage and carrot

**2 servings · 25 min total / 25 min active · equipment: stove**

**Why include it:** Uses cabbage and carrots that overlap with other meals and gives a clear increase in vegetable quantity.

**Variant/design choice:** Retains 400 g cooked rice, 2 eggs and 80 g peas from the base; increases carrot from 100 to 150 g and adds 200 g cabbage.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cooked rice | 400 g | already cooked rice, cooled promptly and refrigerated below 4 C if not freshly cooked; do not use rice left unrefrigerated or with uncertain storage |
| egg | 2 pcs | beaten |
| cabbage | 200 g | thinly shredded |
| carrot | 150 g | cut into small dice |
| frozen pea | 80 g | — |
| garlic | 8 g | Optional. finely chopped |
| spring onion | 10 g | Optional. thinly sliced |
| soy sauce | 15 ml | Optional.  |
| canola oil | 15 ml | — |

**Method**

1. Break the rice into loose grains. Heat one third of the oil in a large nonstick pan and scramble the eggs until fully set. Transfer the eggs to a clean plate.
2. Add the remaining oil, garlic if using, carrot and cabbage. Stir-fry for about 5 minutes, then add the peas and cook until the vegetables are tender and the peas are hot.
3. Add the rice and keep turning it through the vegetables for about 5 minutes. Work in batches if needed so the rice heats evenly.
4. Return the egg, add soy sauce and spring onion if using, and toss together. Stir and check several parts with a clean food thermometer; keep the rice at 75 C or hotter for at least 2 minutes. Continue heating if necessary and serve immediately. Reheating cannot make poorly stored rice safe.

**Research references**

- [The Woks of Life: Vegetable Fried Rice](https://thewoksoflife.com/vegetable-fried-rice/) — concept/technique reference only
- [Singapore Food Agency: Fried Rice Syndrome](https://www.sfa.gov.sg/food-safety-tips/food-risk-concerns/risk-at-a-glance/fried-rice-syndrome) — food handling reference; not a recipe endorsement
- [Singapore Food Agency: Food Safety Tips](https://www.sfa.gov.sg/food-safety-tips/safe-food-practices/food-safety-tips) — reheating reference; not a recipe endorsement

**Review focus:** Test pan capacity, whether the cabbage makes the rice wet, portion size and the 25-minute estimate.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/cabbage-carrot-egg-fried-rice.yaml) · reviewed: false

<a id="tofu-vegetable-fried-rice"></a>

## 15. Tofu and vegetable fried rice

**2 servings · 25 min total / 25 min active · equipment: stove**

**Why include it:** A substantial egg-free fried-rice option that reuses the base recipe vegetables and seasonings.

**Variant/design choice:** Replaces the base eggs with a generous plain-tofu portion; dietary suitability still comes from every ingredient in Role 2 metadata.

**Tags:** light.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cooked rice | 400 g | already cooked rice, cooled promptly and refrigerated below 4 C if not freshly cooked; do not use rice left unrefrigerated or with uncertain storage |
| firm tofu | 300 g | plain tofu, drained well and cut into small cubes |
| carrot | 100 g | cut into small dice |
| frozen pea | 80 g | — |
| garlic | 8 g | Optional. finely chopped |
| spring onion | 10 g | Optional. thinly sliced |
| soy sauce | 15 ml | Optional.  |
| canola oil | 15 ml | — |

**Method**

1. Break up the rice clumps. Heat two thirds of the oil in a nonstick pan and cook the tofu for 5 to 6 minutes, turning it gently, until some surfaces are lightly golden.
2. Move the tofu to a clean plate. Add the rest of the oil, carrot and garlic if using, then stir-fry for about 3 minutes. Add the peas and cook until the vegetables are tender.
3. Add the rice and stir-fry for about 5 minutes. Return the tofu and add soy sauce and spring onion if using, folding carefully so the tofu holds its shape.
4. Stir and check several parts with a clean food thermometer; keep the rice at 75 C or hotter for at least 2 minutes. Continue heating if necessary and serve immediately. Reheating cannot make poorly stored rice safe.

**Research references**

- [The Woks of Life: Vegetable Fried Rice](https://thewoksoflife.com/vegetable-fried-rice/) — concept/technique reference only
- [Singapore Food Agency: Fried Rice Syndrome](https://www.sfa.gov.sg/food-safety-tips/food-risk-concerns/risk-at-a-glance/fried-rice-syndrome) — food handling reference; not a recipe endorsement
- [Singapore Food Agency: Food Safety Tips](https://www.sfa.gov.sg/food-safety-tips/safe-food-practices/food-safety-tips) — reheating reference; not a recipe endorsement

**Review focus:** Check tofu browning and water release; verify the tofu product and optional soy sauce composition.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tofu-vegetable-fried-rice.yaml) · reviewed: false

<a id="chicken-vegetable-fried-rice"></a>

## 16. Chicken, egg and vegetable fried rice

**2 servings · 30 min total / 30 min active · equipment: stove**

**Why include it:** Adds chicken to the egg-rice base while keeping its vegetables and core seasoning.

**Variant/design choice:** More-protein variant adds 250 g chicken without removing the original 2 eggs, so the requested change is concrete.

**Tags:** light, high_protein.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cooked rice | 400 g | already cooked rice, cooled promptly and refrigerated below 4 C if not freshly cooked; do not use rice left unrefrigerated or with uncertain storage |
| chicken thigh | 250 g | boneless skinless meat, cut into small pieces using a separate board |
| egg | 2 pcs | beaten |
| carrot | 100 g | cut into small dice |
| frozen pea | 80 g | — |
| garlic | 8 g | Optional. finely chopped |
| spring onion | 10 g | Optional. thinly sliced |
| soy sauce | 15 ml | Optional.  |
| canola oil | 15 ml | — |

**Method**

1. Heat one third of the oil in a large nonstick pan. Scramble the eggs until fully set and transfer them to a clean plate.
2. Add another third of the oil and the chicken. Stir-fry until cooked, using a clean thermometer to check several thick pieces reach at least 75 C for 2 minutes. Transfer to a second clean plate, keeping raw-chicken utensils separate.
3. Add the remaining oil, garlic if using, carrot and peas. Cook until the vegetables are tender, then add the loosened rice and stir-fry for about 5 minutes.
4. Return the cooked chicken and egg, add soy sauce and spring onion if using, and turn everything through the rice. Stir and check several parts with a clean food thermometer; keep the rice at 75 C or hotter for at least 2 minutes. Continue heating if necessary and serve immediately. Reheating cannot make poorly stored rice safe.

**Research references**

- [The Woks of Life: Chicken Fried Rice](https://thewoksoflife.com/classic-chicken-fried-rice/) — concept/technique reference only
- [Singapore Food Agency: Advisory on Food Safety Practices, December 2024](https://www.sfa.gov.sg/docs/default-source/circulars/others/2024/advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf) — chicken cooking temperature reference; not a recipe endorsement
- [Singapore Food Agency: Fried Rice Syndrome](https://www.sfa.gov.sg/food-safety-tips/food-risk-concerns/risk-at-a-glance/fried-rice-syndrome) — food handling reference; not a recipe endorsement
- [Singapore Food Agency: Food Safety Tips](https://www.sfa.gov.sg/food-safety-tips/safe-food-practices/food-safety-tips) — reheating reference; not a recipe endorsement

**Review focus:** Review chicken piece size and temperature, total portion size, pan capacity and the additional cooking time.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/chicken-vegetable-fried-rice.yaml) · reviewed: false

<a id="rice-vermicelli-tofu-soup"></a>

## 17. Bok choy and tofu bee hoon soup

**2 servings · 25 min total / 15 min active · equipment: stove**

**Why include it:** A complete, simple soup meal without the mushrooms required by the other tofu soup; useful for ingredient dislikes and differing inventory.

**Variant/design choice:** Low-added-oil plant-based soup option; the chicken variant keeps the same noodles, greens and ginger.

**Tags:** light, soupy, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| rice vermicelli | 160 g | dry thin rice noodles |
| firm tofu | 300 g | plain tofu, drained and cut into small cubes |
| bok choy | 250 g | washed, stems and leaves separated and sliced |
| ginger | 15 g | peeled and finely sliced |
| soy sauce | 20 ml | — |
| water | 900 ml | measured cooking water; additional water for rinsing or preparing the noodles/rice as instructed, plus small top-ups if needed |

**Method**

1. Soak or cook the rice vermicelli according to the packet instructions, then drain. Prepare the vegetables while the noodles soften.
2. Bring the measured soup water, ginger and soy sauce to a boil in a saucepan. Add the bok choy stems and simmer for 3 minutes.
3. Add the tofu and bok choy leaves. Simmer gently for another 4 to 5 minutes, until the tofu is hot throughout and the stems are tender.
4. Add the prepared noodles and heat the soup back to a simmer. Divide the noodles, tofu, vegetables and broth evenly between bowls and serve hot.

**Research references**

- [The Woks of Life: Tofu Soup](https://thewoksoflife.com/tofu-soup/) — concept/technique reference only
- [Foong Family Flat: Chicken Bee Hoon Soup](https://foongfamilyflat.com/recipes/better-for-you-than-instant-noodles-chicken-beehoon-soup) — concept/technique reference only

**Review focus:** Taste the plain water-based broth and review noodle preparation, soup volume and whether the tofu portion is satisfying.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/rice-vermicelli-tofu-soup.yaml) · reviewed: false

<a id="rice-vermicelli-chicken-soup"></a>

## 18. Bok choy and chicken bee hoon soup

**2 servings · 30 min total / 20 min active · equipment: stove**

**Why include it:** Provides a light poultry soup using almost the same shopping ingredients as the tofu version.

**Variant/design choice:** Chicken alternative; do not represent a tofu-to-chicken substitution as an automatic increase in protein without comparing quantities.

**Tags:** light, soupy, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| rice vermicelli | 160 g | dry thin rice noodles |
| chicken thigh | 300 g | boneless skinless meat, cut into thin bite-size slices |
| bok choy | 250 g | washed, stems and leaves separated and sliced |
| ginger | 15 g | peeled and finely sliced |
| soy sauce | 20 ml | — |
| water | 900 ml | measured cooking water; additional water for rinsing or preparing the noodles/rice as instructed, plus small top-ups if needed |

**Method**

1. Prepare the rice vermicelli according to its packet and drain. Keep the noodle utensils separate from those used for the raw chicken.
2. Bring the measured soup water, ginger and soy sauce to a boil. Add the chicken, return to a simmer and cook for about 8 to 10 minutes.
3. Use a clean thermometer to check several thick chicken pieces reach at least 75 C for 2 minutes; continue simmering as needed. Add the bok choy stems and cook for 3 minutes, followed by the leaves for another 2 minutes.
4. Add the drained noodles, bring the soup back to a simmer and check that everything is hot. Share the chicken, noodles, vegetables and broth evenly between bowls.

**Research references**

- [Foong Family Flat: Chicken Bee Hoon Soup](https://foongfamilyflat.com/recipes/better-for-you-than-instant-noodles-chicken-beehoon-soup) — concept/technique reference only
- [Singapore Food Agency: Advisory on Food Safety Practices, December 2024](https://www.sfa.gov.sg/docs/default-source/circulars/others/2024/advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf) — chicken cooking temperature reference; not a recipe endorsement

**Review focus:** Check the homemade broth flavour and safe cooking of sliced chicken; verify noodle texture after reheating in the soup.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/rice-vermicelli-chicken-soup.yaml) · reviewed: false

<a id="bee-hoon-cabbage"></a>

## 19. Cabbage and carrot bee hoon

**2 servings · 25 min total / 20 min active · equipment: stove**

**Why include it:** A vegetable-heavy version of a familiar economical bee hoon meal, with a separate added-egg variant.

**Variant/design choice:** The egg variant preserves the noodle and vegetable amounts and adds eggs; this base intentionally has no high_protein tag.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| rice vermicelli | 180 g | dry thin rice noodles |
| cabbage | 250 g | thinly shredded |
| carrot | 150 g | cut into thin matchsticks |
| garlic | 10 g | finely chopped |
| soy sauce | 20 ml | — |
| canola oil | 15 ml | — |
| water | 150 ml | measured cooking water; additional water for rinsing or preparing the noodles/rice as instructed, plus small top-ups if needed |

**Method**

1. Prepare the rice vermicelli according to the packet until pliable, then drain well. Keep the measured braising water separate.
2. Warm the oil in a large frying pan and cook the garlic briefly without browning it. Add the cabbage and carrot and stir for 3 to 4 minutes.
3. Pour in the braising water and soy sauce and bring to a simmer. Add the noodles and lift and turn them through the vegetables with tongs.
4. Continue cooking for about 4 to 6 minutes, until the noodles are tender and the liquid has mostly been absorbed. Add a small splash of drinking water if the noodles are still firm; serve while hot.

**Research references**

- [Noob Cook: Economical Fried Bee Hoon](https://noobcook.com/economical-fried-bee-hoon/2/) — concept/technique reference only

**Review focus:** Review noodle brand and soaking time, saltiness, vegetable quantity and whether the base is a sufficiently substantial meal for participants.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/bee-hoon-cabbage.yaml) · reviewed: false

<a id="bee-hoon-egg"></a>

## 20. Egg, cabbage and carrot bee hoon

**2 servings · 30 min total / 25 min active · equipment: stove**

**Why include it:** Makes the more-protein adjustment visible while retaining the same bee hoon and vegetables.

**Variant/design choice:** Adds 4 eggs per two servings to the base without reducing the existing ingredients; high_protein is an internal qualitative ranking tag.

**Tags:** light, high_protein, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| rice vermicelli | 180 g | dry thin rice noodles |
| cabbage | 250 g | thinly shredded |
| carrot | 150 g | cut into thin matchsticks |
| egg | 4 pcs | beaten |
| garlic | 10 g | finely chopped |
| soy sauce | 20 ml | — |
| canola oil | 15 ml | — |
| water | 150 ml | measured cooking water; additional water for rinsing or preparing the noodles/rice as instructed, plus small top-ups if needed |

**Method**

1. Prepare and drain the rice vermicelli according to the packet. Warm one third of the oil in a large nonstick pan, scramble the eggs until fully set, and transfer them to a clean plate.
2. Add the remaining oil and garlic, then stir in the cabbage and carrot. Cook for 3 to 4 minutes until starting to soften.
3. Pour in the measured braising water and soy sauce. Add the noodles and turn them through the vegetables, simmering for about 4 to 6 minutes until tender and the liquid is mostly absorbed.
4. Fold the scrambled eggs through the noodles and heat everything until hot throughout. If the noodles need more cooking, add a little drinking water and continue before serving.

**Research references**

- [Noob Cook: Economical Fried Bee Hoon](https://noobcook.com/economical-fried-bee-hoon/2/) — concept/technique reference only

**Review focus:** Check whether four eggs give suitable portions, whether the pan fits the food, and whether the 30-minute estimate is realistic.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/bee-hoon-egg.yaml) · reviewed: false

<a id="microwave-broccoli-chickpea-rice"></a>

## 21. Microwave broccoli and chickpea rice

**2 servings · 20 min total / 10 min active · equipment: microwave**

**Why include it:** A complete microwave-only option using canned pulses and shared vegetables, including an option without soy sauce.

**Variant/design choice:** Provides equipment diversity and a low-added-oil meal; no stove, kettle or separately cooked ingredient beyond the explicitly listed cooked rice.

**Tags:** light, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cooked rice | 350 g | already cooked rice, cooled promptly and refrigerated below 4 C if not freshly cooked; do not use rice left unrefrigerated or with uncertain storage |
| canned chickpea | 240 g | drained cooked chickpeas, rinsed |
| broccoli | 250 g | washed and cut into small even florets; tender stem thinly sliced |
| garlic | 6 g | Optional. finely grated |
| canola oil | 5 ml | Optional.  |
| salt | 1 g | Optional.  |
| lemon | 0.5 pcs | Optional. juice only |
| water | 60 ml | — |

**Method**

1. Put the broccoli, garlic if using and half the water in a large microwave-safe bowl with room for the remaining ingredients. Cover with a vented microwave-safe lid and microwave on high for about 3 to 4 minutes, until the broccoli starts to soften.
2. Open the lid away from your face. Stir in the rice, drained chickpeas, remaining water, oil and salt if using. Cover loosely again and microwave on high for about 4 to 6 minutes, stirring thoroughly halfway through; times depend on the microwave and portion size.
3. Check several places, including the centre, with a clean thermometer. Continue heating and stirring until the rice mixture is at least 75 C for 2 minutes throughout. Allow to stand covered for 1 minute, then stir again.
4. Add the lemon juice if using and divide into bowls. Serve immediately; only use rice that was safely stored, because reheating cannot remove all risks from rice left out too long.

**Research references**

- [Panasonic: Microwave Cooking Tips](https://www.panasonic.com/ca/consumer/home-appliances-learn/panasonickitchen/microwave-cooking-tips.html) — concept/technique reference only
- [Singapore Food Agency: Fried Rice Syndrome](https://www.sfa.gov.sg/food-safety-tips/food-risk-concerns/risk-at-a-glance/fried-rice-syndrome) — food handling reference; not a recipe endorsement
- [Singapore Food Agency: Food Safety Tips](https://www.sfa.gov.sg/food-safety-tips/safe-food-practices/food-safety-tips) — reheating reference; not a recipe endorsement

**Review focus:** Test on the actual microwave: bowl capacity, power, even heating, steam handling, broccoli texture and the 20-minute estimate.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/microwave-broccoli-chickpea-rice.yaml) · reviewed: false

<a id="rice-cooker-bok-choy-tofu-rice"></a>

## 22. Rice-cooker bok choy and tofu rice

**2 servings · 55 min total / 10 min active · equipment: rice_cooker**

**Why include it:** A main meal for households with a rice cooker but no stove, using the same tofu and greens as the soup dishes.

**Variant/design choice:** Adds appliance coverage without claiming every rice cooker supports every mixed recipe; rice and toppings cook together in one appliance.

**Tags:** light, low_oil, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 200 g | white rice, rinsed and drained |
| firm tofu | 300 g | plain tofu, drained and cut into small cubes |
| bok choy | 300 g | washed and cut into small pieces, with thick stems thinly sliced |
| ginger | 15 g | peeled and finely sliced |
| garlic | 8 g | Optional. finely chopped |
| soy sauce | 15 ml | — |
| water | the amount required by the rice cooker instructions for this quantity of white rice and a mixed-rice recipe, counting soy sauce as part of the cooking liquid | — |

**Method**

1. Use a rice cooker whose instructions allow mixed rice with vegetables and tofu. Put the rinsed rice in the inner pot and add the water and soy sauce as the cooking liquid; keep within the mixed-rice capacity stated by the manufacturer.
2. Distribute the ginger, garlic if using, tofu and bok choy over the rice. Keep the rice level below and do not pack the vegetables tightly against the lid or steam vent.
3. Start the appropriate white-rice or mixed-rice cycle and let it finish. The cycle is commonly around 30 to 40 minutes, but use your cooker instructions and allow longer when needed.
4. Open carefully after the cycle ends. Check that the rice is tender, the stems are cooked and the tofu is hot throughout; if not, continue with the manufacturer-approved cooking mode. Rest covered for 5 minutes, then gently mix and serve.

**Research references**

- [The Foodie Takes Flight: One Pot Mushroom Rice with Spicy Miso Sauce](https://thefoodietakesflight.com/one-pot-mushroom-rice/) — concept/technique reference only
- [Nomadette: Rice Cooker Chicken Rice](https://nomadette.com/rice-cooker-chicken-rice/) — concept/technique reference only

**Review focus:** A cooking trial is particularly important: verify cooker model, mixed-rice capacity, water level, wet vegetables and the 55-minute estimate. Allow 55 minutes including preparation, a 40-minute cycle and resting; verify against the actual cooker.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/rice-cooker-bok-choy-tofu-rice.yaml) · reviewed: false

<a id="chye-sim-egg-bee-hoon"></a>

## 23. Chye sim and egg bee hoon soup

**2 servings · 25 min total / 15 min active · equipment: stove**

**Why include it:** A simple local-style leafy-green noodle soup that uses chye sim and does not need soy sauce or tofu.

**Variant/design choice:** Quick, no-added-oil alternative with a different allergen combination from the tofu noodle soups.

**Tags:** light, soupy, low_oil, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| rice vermicelli | 160 g | dry thin rice noodles |
| chye sim | 300 g | washed, tough ends removed, stems and leaves cut separately |
| egg | 3 pcs | beaten |
| ginger | 10 g | Optional. peeled and finely sliced |
| garlic | 6 g | Optional. finely chopped |
| salt | 2 g | — |
| black pepper | 0.5 g | Optional.  |
| water | 900 ml | measured cooking water; additional water for rinsing or preparing the noodles/rice as instructed, plus small top-ups if needed |

**Method**

1. Start heating the broth water in a saucepan while preparing the rice vermicelli according to its packet in a separate bowl or pan. Drain the noodles when ready.
2. Bring the broth water to a boil. Add the chye sim stems and simmer for about 3 minutes. Add the leaves, salt and pepper if using and cook for another 2 minutes until the stems are tender.
3. Keep the soup at a gentle simmer and pour in the egg in a thin stream, stirring slowly to form ribbons. Continue simmering until all the egg is fully set.
4. Add the prepared noodles, bring back to a simmer and serve the noodles, greens, egg and broth together while hot.

**Research references**

- [Meandering Rivr: Chye Sim Egg Soup](https://meanderingrivr.blogspot.com/2014/12/vegetarianism-chye-sim-egg-soup.html) — concept/technique reference only
- [Noob Cook: Economical Fried Bee Hoon](https://noobcook.com/economical-fried-bee-hoon/2/) — concept/technique reference only

**Review focus:** Review seasoning in the simple broth, noodle texture, fully set egg and the 25-minute estimate; the linked egg-soup reference is concept only, not copied instructions. Trial the 25-minute estimate with noodle preparation and broth heating in parallel.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/chye-sim-egg-bee-hoon.yaml) · reviewed: false

<a id="tofu-broccoli-stir-fry"></a>

## 24. Tofu and broccoli stir-fry with rice

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** A common tofu-and-green-vegetable meal that reuses the shared broccoli, rice and aromatics; useful for testing vegetarian protein swaps.

**Variant/design choice:** Base of the chicken broccoli variant. Sauce is deliberately simpler and unthickened; rice time is included.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| firm tofu | 300 g | drained, patted dry and cut into 2 cm cubes |
| broccoli | 300 g | trimmed into small florets; tender stems thinly sliced |
| garlic | 8 g | finely chopped |
| ginger | 8 g | finely chopped |
| soy sauce | 20 ml | — |
| canola oil | 10 ml | — |
| uncooked rice | 150 g | dry white rice |
| water | for rinsing and cooking the rice according to its packet; a little extra for steaming the broccoli | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Heat half the canola oil in a non-stick frying pan over medium heat. Add the firm tofu and turn gently for 6 to 8 minutes until lightly golden; transfer to a clean plate.
3. Add the remaining oil, garlic and ginger to the pan. Stir briefly, then add the broccoli and enough water to cover the base of the pan. Cover and cook for 4 to 6 minutes until the stems are tender.
4. Return the tofu and add the soy sauce. Toss gently and cook uncovered for 2 minutes until everything is hot; add a splash of water if the pan becomes dry. Serve over the cooked rice.

**Research references**

- [10-Minute Broccoli Tofu Bowls — Sarah, The Woks of Life](https://thewoksoflife.com/broccoli-tofu-bowls/) — Dish concept and basic cooking technique only; the quantities, constrained ingredients and instructions are original project choices, not a reproduction or source endorsement.

**Review focus:** Check tofu browning with 10 ml oil, broccoli tenderness and soy sauce strength; test the complete 35-minute meal.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tofu-broccoli-stir-fry.yaml) · reviewed: false

<a id="chicken-broccoli-stir-fry"></a>

## 25. Chicken and broccoli stir-fry with rice

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** A familiar meat alternative using the same vegetable and staple set as the tofu base.

**Variant/design choice:** Replaces firm tofu with chicken thigh; it is a protein-choice variant, not a quantified higher-protein claim. Omits the reference sauce blend and uses a covered finish.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| chicken thigh | 300 g | raw boneless skinless meat, cut into 2 cm pieces |
| broccoli | 300 g | trimmed into small florets; tender stems thinly sliced |
| garlic | 8 g | finely chopped |
| ginger | 8 g | finely chopped |
| soy sauce | 20 ml | — |
| canola oil | 10 ml | — |
| uncooked rice | 150 g | dry white rice |
| water | for rinsing and cooking the rice according to its packet; a little extra for steaming the broccoli | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Heat the canola oil in a non-stick pan over medium-high heat. Add the chicken thigh pieces in one layer; turn and cook for about 6 minutes. Lower the heat and stir in the garlic and ginger for 30 seconds.
3. Add the broccoli, soy sauce and enough water to cover the base of the pan. Cover and simmer for 5 to 8 minutes, stirring occasionally, until the broccoli is tender and the chicken is cooked.
4. Check the thickest chicken pieces with a food thermometer: they must reach at least 75 C and stay at that temperature for 2 minutes. Continue cooking if needed. Serve with the rice.

**Research references**

- [Chicken and Broccoli — Bill, The Woks of Life](https://thewoksoflife.com/chinese-chicken-broccoli-brown-sauce/) — Dish concept and basic cooking technique only; the quantities, constrained ingredients and instructions are original project choices, not a reproduction or source endorsement.

**Review focus:** Confirm poultry temperature, small piece size, actual cooking time and sauce balance.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/chicken-broccoli-stir-fry.yaml) · reviewed: false

<a id="mushroom-omelette"></a>

## 26. Mushroom omelette with rice

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** A short ingredient-list egg meal that uses fresh mushrooms and offers a texture distinct from stir-fried eggs.

**Variant/design choice:** Original rice meal with shiitake and spring onion, without the source butter, dairy or cheese. Tomato-onion variant switches the vegetables.

**Tags:** light.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| egg | 4 pcs | — |
| fresh shiitake mushroom | 180 g | tough stems removed; caps sliced |
| spring onion | 15 g | washed and finely sliced |
| canola oil | 10 ml | — |
| salt | 1 g | — |
| uncooked rice | 150 g | dry white rice |
| water | for rinsing and cooking the rice according to its packet | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Beat the eggs with the salt and spring onion. Heat half the canola oil in a non-stick pan and cook the fresh shiitake mushrooms for 5 to 7 minutes until tender and their liquid has evaporated.
3. Spread the mushrooms evenly, add the remaining oil, then pour over the egg mixture. Cook over medium-low heat, gently lifting the set edges to let uncooked egg reach the pan.
4. Cover and cook for about 4 to 6 minutes until the centre is fully set with no runny egg; lower the heat if the underside browns too quickly. Divide the omelette and serve with the rice.

**Research references**

- [Omelette — Nagi Maehashi, RecipeTin Eats](https://www.recipetineats.com/omelette/) — Dish concept and basic cooking technique only; the quantities, constrained ingredients and instructions are original project choices, not a reproduction or source endorsement.

**Review focus:** Check that the four-egg omelette sets evenly in the chosen pan and the rice and egg portions feel sufficient.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/mushroom-omelette.yaml) · reviewed: false

<a id="tomato-onion-omelette"></a>

## 27. Tomato and onion omelette with rice

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** A pantry-friendly alternative for users with tomatoes and onion instead of mushrooms.

**Variant/design choice:** Replaces mushrooms and spring onion with tomato and bulb onion; water is cooked off before adding egg. This is an egg omelette, not the Indian chickpea-flour dish also called tomato omelette.

**Tags:** light.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| egg | 4 pcs | — |
| tomato | 200 g | diced |
| onion | 80 g | finely diced |
| canola oil | 10 ml | — |
| salt | 1 g | — |
| uncooked rice | 150 g | dry white rice |
| water | for rinsing and cooking the rice according to its packet | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Heat half the canola oil in a non-stick pan. Cook the onion over medium heat for 4 minutes, add the tomato and cook for a further 5 minutes until the mixture is soft and excess liquid has evaporated.
3. Beat the eggs with the salt. Spread the vegetables evenly, add the remaining oil and pour in the eggs. Cook over medium-low heat, lifting the set edges to let uncooked egg reach the pan.
4. Cover for about 4 to 6 minutes until the centre has set fully without any runny egg. Divide and serve with the rice.

**Research references**

- [Omelette — Nagi Maehashi, RecipeTin Eats](https://www.recipetineats.com/omelette/) — General omelette method only. Tomato-onion filling, rice, ingredient quantities and absence of dairy are original project choices.

**Review focus:** Check tomato moisture, tendency to stick and whether the estimated 35 minutes works with rice.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tomato-onion-omelette.yaml) · reviewed: false

<a id="steamed-egg"></a>

## 28. Steamed egg with rice

**2 servings · 35 min total / 15 min active · equipment: stove, steamer**

**Why include it:** An oil-free soft-texture meal with few tracked ingredients; distinct from omelettes and fried rice.

**Variant/design choice:** Base for the tofu addition variant. Uses plain water and a continuous gentle steam; source timing and stock formula are not copied.

**Tags:** light, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| egg | 4 pcs | — |
| soy sauce | 10 ml | — |
| spring onion | 15 g | washed and finely sliced |
| uncooked rice | 150 g | dry white rice |
| water | for the rice according to its packet; for the custard use one and a half times the beaten egg volume; additional water for steaming | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Beat the eggs in a measuring jug and note their volume. Gently mix in one and a half times that volume of room-temperature water. Pour into a shallow heatproof dish, leaving room at the top.
3. Add water to the steamer below its rack and bring to a simmer. Cover the egg dish loosely with a heatproof plate, place it on the rack and steam with the lid on for about 15 to 20 minutes.
4. Check that the custard is set through the centre with no liquid egg; continue steaming if necessary, topping up the steamer with hot water before it runs dry. Lift out carefully, add soy sauce and spring onion, and serve with the rice.

**Research references**

- [Steamed Eggs — Judy, The Woks of Life](https://thewoksoflife.com/steamed-egg/) — Steamed egg custard and soy/spring onion serving concept only. The water ratio, continuous-steam method and rice portions are original project choices.

**Review focus:** Check custard depth, egg-to-water ratio, steamer fit, fully set centre and total time.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/steamed-egg.yaml) · reviewed: false

<a id="steamed-egg-tofu"></a>

## 29. Steamed egg and tofu with rice

**2 servings · 40 min total / 15 min active · equipment: stove, steamer**

**Why include it:** An explicit add-protein adjustment: retains all four eggs and adds tofu rather than merely exchanging ingredients.

**Variant/design choice:** Adds 200 g firm tofu to the same two-serving base. high_protein is an internal qualitative tag for this increase, not a nutrition certification.

**Tags:** light, high_protein, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| egg | 4 pcs | — |
| firm tofu | 200 g | drained and cut into small cubes |
| soy sauce | 10 ml | — |
| spring onion | 15 g | washed and finely sliced |
| uncooked rice | 150 g | dry white rice |
| water | for the rice according to its packet; for the custard use one and a half times the beaten egg volume; additional water for steaming | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Spread the firm tofu in a shallow heatproof dish. Beat the eggs, measure their volume, and mix in one and a half times that volume of room-temperature water. Pour over the tofu, leaving room at the top.
3. Bring the steamer water to a simmer below the rack. Cover the dish loosely with a heatproof plate and steam with the lid on for about 20 to 25 minutes. Keep water in the steamer throughout.
4. Continue steaming until the egg is fully set at the centre and the tofu is hot throughout. Lift out carefully, spoon the soy sauce over, scatter the spring onion and serve with the rice.

**Research references**

- [Steamed Eggs — Judy, The Woks of Life](https://thewoksoflife.com/steamed-egg/) — Egg custard technique concept only; firm-tofu addition, rice and the continuous-steam method are original project choices.

**Review focus:** Firm tofu gives a firmer texture than silken tofu; check acceptability, centre doneness, steaming time and dish capacity.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/steamed-egg-tofu.yaml) · reviewed: false

<a id="ginger-chicken-soup"></a>

## 30. Ginger chicken and potato soup

**2 servings · 40 min total / 15 min active · equipment: stove**

**Why include it:** A single-pot oil-free meal with potato as its starchy component; provides a non-rice choice while keeping ingredients shared.

**Variant/design choice:** Concept reference only. Original stove method replaces the source noodles and stock with potato, carrot and a lightly seasoned water broth.

**Tags:** light, soupy, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| chicken thigh | 300 g | raw boneless skinless meat, cut into 2 cm pieces |
| potato | 400 g | peeled and cut into 1.5 cm cubes |
| carrot | 180 g | thinly sliced |
| ginger | 15 g | peeled and thinly sliced |
| spring onion | 15 g | washed and sliced; keep white and green parts separate |
| salt | 2 g | — |
| water | 900 ml | — |

**Method**

1. Put the water, ginger, potato, carrot and white parts of the spring onion into a saucepan. Bring to a boil, then cover and simmer for 8 minutes.
2. Add the chicken thigh pieces, stir and return to a simmer. Cover and cook for about 15 to 20 minutes until the potato and carrot are tender.
3. Check the thickest chicken pieces with a thermometer: they must reach at least 75 C and remain there for 2 minutes. Keep simmering if needed. Stir in the salt and spring onion greens, then divide the soup and solids between bowls.

**Research references**

- [Ginger Chicken Soup — Rebecca McLeod, Bec's Table](https://becs-table.com.au/ginger-chicken-soup/) — Ginger/chicken-thigh soup pairing only. Potato, carrot, no added oil, water broth and stovetop steps are independent project choices.

**Review focus:** Check broth flavour without stock, potato portion and tenderness, chicken temperature and the 40-minute estimate.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/ginger-chicken-soup.yaml) · reviewed: false

<a id="fish-tomato-soup"></a>

## 31. Fish and tomato vermicelli soup

**2 servings · 30 min total / 15 min active · equipment: stove**

**Why include it:** A fish-based soup with an explicit noodle portion so a recommendation does not silently omit the meal staple.

**Variant/design choice:** Concept reference only. Uses small boneless cod pieces and vermicelli instead of the source whole-fish broth; no health claims or reference timings are adopted.

**Tags:** light, soupy, low_oil, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cod fillet | 300 g | raw boneless fillet, thawed if frozen and cut into 2 cm pieces; check for bones |
| tomato | 300 g | cut into small wedges |
| ginger | 10 g | peeled and thinly sliced |
| spring onion | 15 g | washed and sliced |
| salt | 2 g | — |
| rice vermicelli | 140 g | dry thin rice noodles |
| water | enough for noodle preparation according to its packet and a soup broth to cover the fish and tomatoes | — |

**Method**

1. Prepare the rice vermicelli in water according to its packet, then drain and divide between serving bowls.
2. Put the tomato and ginger in a saucepan with enough water for a soup broth. Bring to a boil and simmer for 8 to 10 minutes until the tomato softens.
3. Add the cod and simmer gently for about 6 to 10 minutes. Check the thickest pieces with a food thermometer; continue cooking until at least 75 C is maintained for 2 minutes and the fish is opaque throughout.
4. Stir in the salt and spring onion. Divide the fish and hot soup over the vermicelli and serve immediately.

**Research references**

- [Cantonese-styled Tomato Fish Soup — The Chinese Soup Lady](https://thechinesesouplady.com/how-to-make-a-delicious-cantonese-styled-tomato-fish-soup-with-vegetables/) — Fish, tomato and ginger pairing only. Boneless cod, vermicelli and short-simmer directions are original project choices; no TCM or nutrition claims are used.

**Review focus:** Confirm cod cost/availability, fish bone checks, noodle packet timing, broth concentration and thermometer endpoint.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/fish-tomato-soup.yaml) · reviewed: false

<a id="lentil-spinach-dhal"></a>

## 32. Red lentil and spinach dhal with rice

**2 servings · 45 min total / 20 min active · equipment: stove**

**Why include it:** Adds a leafy vegetable to the lentil base while reusing every base ingredient; useful for an explainable vegetable-rich adjustment.

**Variant/design choice:** Keeps the base lentil, tomato, onion, spice, oil and rice amounts and adds 200 g spinach; the simplified cumin/turmeric flavour and quantities are original.

**Tags:** soupy, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| red lentil | 160 g | dry split lentils, picked over and rinsed |
| tomato | 200 g | chopped |
| onion | 100 g | finely chopped |
| garlic | 8 g | Optional. finely chopped |
| turmeric powder | 2 g | — |
| cumin powder | 2 g | — |
| canola oil | 10 ml | — |
| salt | 1 g | Optional.  |
| spinach | 200 g | washed and roughly chopped |
| uncooked rice | 150 g | dry white rice |
| water | for the rice according to its packet and enough to simmer the lentils | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Heat the canola oil in another saucepan. Cook the onion over medium-low heat for 5 minutes. Stir in the garlic if using, turmeric and cumin, then add the tomato and cook for 3 minutes.
3. Add the red lentils and enough water to cover them generously. Simmer partly covered for 20 to 25 minutes, stirring and adding water as needed, until the lentils are soft and no hard centres remain.
4. Stir in the spinach and simmer for another 3 to 5 minutes until wilted and tender. Stir in the salt if using, then serve the dhal with the rice.

**Research references**

- [Red Lentil Curry — Swasthi Shreekanth, Swasthi's Recipes](https://www.indianhealthyrecipes.com/red-lentil-curry/) — Lentil curry with an onion-tomato base as concept only; the limited spice list, quantities, spinach and single-pot lentil method are project choices.

**Review focus:** Check whether turmeric level is balanced, lentils soften in the proposed time, and spinach texture and liquid level are acceptable.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/lentil-spinach-dhal.yaml) · reviewed: false

<a id="potato-cauliflower-curry"></a>

## 33. Potato and cauliflower curry with rice

**2 servings · 45 min total / 20 min active · equipment: stove**

**Why include it:** A vegetable-heavy curry expands ingredient use and mild flavour choices; the reduced rice portion accounts for potato already in the dish.

**Variant/design choice:** A simplified saucy potato-cauliflower meal using the existing cumin and turmeric catalogue, not a claim to reproduce the traditional recipe.

**Tags:** vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| potato | 250 g | peeled and cut into 1.5 cm cubes |
| cauliflower | 300 g | trimmed into small florets |
| onion | 100 g | finely chopped |
| tomato | 200 g | chopped |
| garlic | 8 g | finely chopped |
| turmeric powder | 1 g | — |
| cumin powder | 2 g | — |
| canola oil | 10 ml | — |
| salt | 2 g | — |
| uncooked rice | 120 g | dry white rice |
| water | for rinsing and cooking the rice according to its packet; enough extra water to simmer the vegetables | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Heat the canola oil in a wide saucepan. Cook the onion for 5 minutes, then stir in the garlic, turmeric and cumin. Add the tomato and cook for 4 minutes until softened.
3. Add the potato, salt and enough water to reach halfway up the potato pieces. Cover and simmer for 8 minutes, stirring once.
4. Add the cauliflower, cover again and simmer for 10 to 15 minutes until the potato yields easily to a fork and cauliflower is tender. Add a little water if it dries out; uncover briefly if too wet. Serve with the rice.

**Research references**

- [Aloo Gobi Recipe (Cauliflower Potato Curry) — Swasthi Shreekanth](https://www.indianhealthyrecipes.com/aloo-gobi-recipe/) — Dish concept and basic cooking technique only; the quantities, constrained ingredients and instructions are original project choices, not a reproduction or source endorsement.

**Review focus:** Assess satiety as a vegetable-led meal, potato/cauliflower timing, spice balance and whether users would want an explicit protein addition.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/potato-cauliflower-curry.yaml) · reviewed: false

<a id="chickpea-tomato-curry"></a>

## 34. Chickpea and tomato curry with rice

**2 servings · 40 min total / 20 min active · equipment: stove**

**Why include it:** A canned-legume meal supports low-fresh-stock scenarios and avoids requiring advance soaking or pressure cooking.

**Variant/design choice:** Uses drained canned chickpeas, fresh tomato and a short spice list; omits coconut milk and the source spice blend.

**Tags:** soupy, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| canned chickpea | 360 g | drained and rinsed cooked chickpeas; weight after draining |
| tomato | 300 g | finely chopped |
| onion | 100 g | finely chopped |
| garlic | 8 g | finely chopped |
| turmeric powder | 1 g | — |
| cumin powder | 2 g | — |
| canola oil | 10 ml | — |
| salt | 1 g | — |
| uncooked rice | 150 g | dry white rice |
| water | for rinsing and cooking the rice according to its packet; enough extra water for a loose curry sauce | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Heat the canola oil in a saucepan. Cook the onion over medium heat for 5 minutes, then add the garlic, turmeric and cumin and stir for 30 seconds.
3. Add the tomato and salt. Cook for 6 to 8 minutes, stirring, until the tomatoes break down. Add the canned chickpeas and enough water to make a loose sauce.
4. Simmer for 10 to 12 minutes until the chickpeas are hot and soft, stirring occasionally. Crush a few chickpeas with the spoon to thicken the sauce and serve with the rice.

**Research references**

- [Chickpea Curry Recipe — Swasthi Shreekanth](https://www.indianhealthyrecipes.com/chickpea-curry/) — Dish concept and basic cooking technique only; the quantities, constrained ingredients and instructions are original project choices, not a reproduction or source endorsement.

**Review focus:** Check drained-weight clarity, tomato acidity, sauce thickness and satiety for two servings.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/chickpea-tomato-curry.yaml) · reviewed: false

<a id="coconut-tofu-curry"></a>

## 35. Coconut tofu and vegetable curry with rice

**2 servings · 40 min total / 20 min active · equipment: stove**

**Why include it:** A coconut-based option creates a clear rich/spicy contrast for feedback ranking while sharing tofu, carrots and long beans.

**Variant/design choice:** Original simplified coconut curry inspired by vegetable-coconut stew. Omits source shrimp, dried shrimp and other extras; ingredients here determine suitability.

**Tags:** rich, spicy, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| firm tofu | 300 g | drained and cut into 2 cm cubes |
| coconut milk | 200 ml | unsweetened cooking coconut milk |
| carrot | 150 g | thinly sliced |
| long bean | 180 g | trimmed and cut into short lengths |
| onion | 80 g | finely chopped |
| garlic | 8 g | finely chopped |
| ginger | 8 g | finely chopped |
| turmeric powder | 1 g | — |
| chilli paste | 10 g | plain chilli paste; not sambal or curry paste |
| canola oil | 10 ml | — |
| salt | 1 g | — |
| uncooked rice | 150 g | dry white rice |
| water | for rinsing and cooking the rice according to its packet; extra water for a loose curry sauce | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Heat the canola oil in a saucepan and cook the onion for 4 minutes. Stir in the garlic, ginger, turmeric and chilli paste and cook for a further minute.
3. Add the carrot and long bean, plus enough water to cover the base of the pan. Cover and simmer for 6 to 8 minutes, until the vegetables are nearly tender.
4. Stir in the coconut milk, firm tofu and salt. Add water if needed to make a loose sauce and simmer gently for 6 to 8 minutes until the tofu is hot throughout and the vegetables are tender. Serve with the rice.

**Research references**

- [The Best Sayur Lodeh (Vegetables in Coconut Milk) — Emily Halim, Nyonya Cooking](https://www.nyonyacooking.com/recipes/the-best-sayur-lodeh-vegetables-in-coconut-milk~SMijNnrFRE) — Vegetables and tofu in a coconut sauce concept only. The reference page contains shrimp despite vegetarian prose; no dietary claims, recipe quantities or complete method are adopted.

**Review focus:** Confirm plain chilli paste composition/heat, coconut sauce balance, bean tenderness and the broad cuisine label.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/coconut-tofu-curry.yaml) · reviewed: false

<a id="coconut-chicken-curry"></a>

## 36. Coconut chicken and vegetable curry with rice

**2 servings · 45 min total / 20 min active · equipment: stove**

**Why include it:** A chicken alternative to the coconut tofu meal provides a controlled protein swap with the same flavour and vegetable profile.

**Variant/design choice:** Replaces tofu with raw chicken; the poultry cooking sequence and longer total time are original changes. No claim that this is the source recipe.

**Tags:** rich, spicy, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| chicken thigh | 300 g | raw boneless skinless meat, cut into 2 cm pieces |
| coconut milk | 200 ml | unsweetened cooking coconut milk |
| carrot | 150 g | thinly sliced |
| long bean | 180 g | trimmed and cut into short lengths |
| onion | 80 g | finely chopped |
| garlic | 8 g | finely chopped |
| ginger | 8 g | finely chopped |
| turmeric powder | 1 g | — |
| chilli paste | 10 g | plain chilli paste; not sambal or curry paste |
| canola oil | 10 ml | — |
| salt | 1 g | — |
| uncooked rice | 150 g | dry white rice |
| water | for rinsing and cooking the rice according to its packet; extra water for a loose curry sauce | — |

**Method**

1. Start the rice first: rinse the uncooked rice, then cook it in water in a covered saucepan following its packet instructions. Prepare the rest of the meal while it cooks; keep the rice covered until serving.
2. Heat the canola oil in a saucepan. Cook the onion for 4 minutes, then stir in the garlic, ginger, turmeric and chilli paste for 1 minute.
3. Add the chicken thigh pieces and turn for 3 minutes. Add the coconut milk, carrot, long bean, salt and enough water to make a loose sauce.
4. Simmer gently, partly covered, for about 15 to 20 minutes until the vegetables are tender. Check the thickest chicken pieces with a food thermometer: they must reach at least 75 C and remain there for 2 minutes. Continue simmering if needed, then serve with the rice.

**Research references**

- [The Best Sayur Lodeh (Vegetables in Coconut Milk) — Emily Halim, Nyonya Cooking](https://www.nyonyacooking.com/recipes/the-best-sayur-lodeh-vegetables-in-coconut-milk~SMijNnrFRE) — Coconut-vegetable sauce concept only; chicken adaptation, ingredients and cooking sequence are original project choices. Source dietary claims are not used.

**Review focus:** Check chicken temperature, coconut sauce texture during the longer simmer and consistency of flavour with the tofu base.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/coconut-chicken-curry.yaml) · reviewed: false

<a id="tempeh-long-bean-stir-fry"></a>

## 37. Tempeh and long bean stir-fry with rice

**2 servings · 40 min total / 25 min active · equipment: stove**

**Why include it:** A full tempeh-and-rice meal with a locally familiar vegetable. Reuses garlic, soy sauce and rice across the catalogue while introducing a distinct tempeh texture for preference feedback. Long beans provide a perishable item for use-soon ranking scenarios.

**Variant/design choice:** Base for a cabbage variation. This relationship supplies ingredient reuse and preference variety; it is not a less-oil, quicker or more-protein adjustment.

**Tags:** .

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| tempeh | 300 g | plain tempeh cut into 1 cm cubes |
| long bean | 250 g | washed and trimmed; cut into 3 cm lengths |
| garlic | 8 g | peeled and finely chopped |
| soy sauce | 20 ml | — |
| canola oil | 15 ml | — |
| uncooked rice | 180 g | dry white rice |
| water | enough for rinsing and cooking the rice plus a few splashes for the stir-fry | — |

**Method**

1. Rinse the rice, drain, and place in a saucepan with the water amount directed on its packet. Bring to a boil, cover, and cook on low heat for the packet's time, then rest covered off the heat while finishing the stir-fry.
2. While the rice cooks, wash and cut the beans, cube the tempeh, and chop the garlic.
3. Heat the oil in a lidded frying pan over medium heat. Cook the tempeh for 6-8 minutes, turning to colour several sides.
4. Add the garlic and beans. Stir for a minute, then add a splash of water, cover, and cook for 8-10 minutes, stirring occasionally and adding a little more water if dry, until the beans are tender.
5. Stir in the soy sauce and cook uncovered for 1-2 minutes to coat the tempeh. Check the tempeh is cooked through according to its packet, fluff the rice, and serve together immediately.

**Research references**

- [Nunuk Sri Rahayu — Tumis Tempe Kacang Panjang (Cook Me Indonesian)](https://www.cookmeindonesian.com/tumis-tempe-kacang-panjang-stir-fried-tempeh-with-long-beans-vegan/) — Concept only: tempeh and long beans can form a stir-fry served with rice. Project seasoning, amounts and prose are original; no authentic Indonesian flavour claim.

**Review focus:** Taste plain soy-seasoned tempeh; check bean tenderness, tempeh packet cooking guidance, portions and 40-minute timing with a rice saucepan and frying pan. Confirm ingredient composition before deriving diet flags.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tempeh-long-bean-stir-fry.yaml) · reviewed: false

<a id="tempeh-cabbage-stir-fry"></a>

## 38. Tempeh and cabbage stir-fry with rice

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** Reuses the tempeh base with cabbage, a shared ingredient in several other dishes. Allows inventory-sensitive ranking without requiring a new condiment or ingredient family.

**Variant/design choice:** Cabbage variation of tempeh-long-bean-stir-fry; do not interpret its five-minute estimate difference as a certified quicker adjustment.

**Tags:** vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| tempeh | 300 g | plain tempeh cut into 1 cm cubes |
| cabbage | 300 g | washed and sliced into thin strips |
| garlic | 8 g | peeled and finely chopped |
| soy sauce | 20 ml | — |
| canola oil | 15 ml | — |
| uncooked rice | 180 g | dry white rice |
| water | enough for rinsing and cooking the rice plus a few splashes for the stir-fry | — |

**Method**

1. Rinse the rice, drain, and put in a saucepan with water according to its packet. Bring to a boil, cover, and cook over low heat for the packet's time, then rest covered off the heat.
2. Meanwhile, prepare the cabbage, tempeh and garlic. Heat the oil in a lidded frying pan over medium heat and cook the tempeh for 6-8 minutes, turning occasionally.
3. Stir in the garlic, then add the cabbage. Add a splash of water, cover, and cook for 5-7 minutes, stirring partway through, until the cabbage stems are tender.
4. Add the soy sauce. Cook uncovered for another 1-2 minutes until the liquid lightly coats the ingredients and the tempeh is cooked through according to its packet. Fluff the rice and serve with the stir-fry immediately.

**Research references**

- [Nunuk Sri Rahayu — Tumis Tempe Kacang Panjang (Cook Me Indonesian)](https://www.cookmeindonesian.com/tumis-tempe-kacang-panjang-stir-fried-tempeh-with-long-beans-vegan/) — General vegetable-substitution concept. Cabbage, quantities and the simpler seasoning are project choices.

**Review focus:** Check cabbage cut size, moisture and tenderness; compare portions and flavour with the long-bean base.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/tempeh-cabbage-stir-fry.yaml) · reviewed: false

<a id="sambal-tofu"></a>

## 39. Chilli tofu with rice

**2 servings · 40 min total / 25 min active · equipment: stove**

**Why include it:** Adds a spicy tofu-and-rice choice so Like/Maybe/Dislike feedback has a meaningful spicy tag to learn from. Tomato gives sauce body without extra canned sauces or sugar. Public title is Chilli tofu, while the preallocated slug is retained.

**Variant/design choice:** Base for a prawn variation. Tofu versus prawn is a protein-source choice, not a verified more-protein adjustment.

**Tags:** spicy, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| firm tofu | 350 g | drained and cut into 2 cm cubes |
| chilli paste | 15 g | plain chilli paste without shrimp paste; heat varies by brand |
| onion | 100 g | peeled and diced |
| garlic | 8 g | peeled and minced |
| tomato | 300 g | washed and diced |
| canola oil | 15 ml | — |
| salt | 1 g | — |
| uncooked rice | 180 g | dry white rice |
| water | enough to rinse and cook the rice plus a few splashes for the sauce | — |

**Method**

1. Rinse the rice and cook in a covered saucepan using the water amount and time on its packet. Rest covered off the heat when cooked.
2. Meanwhile, drain and cube the tofu and prepare the vegetables. Warm half the oil in a non-stick frying pan over medium heat and cook the tofu for 6-8 minutes, turning gently. Transfer to a clean plate.
3. Add the remaining oil and the onion to the same pan. Stir for 4 minutes, then add the garlic and chilli paste and stir for 1 minute.
4. Add the tomato, salt and a splash of water. Simmer for 6-8 minutes, stirring occasionally, until the tomato breaks down into a sauce.
5. Return the tofu and gently coat it in the sauce. Simmer for 3-4 minutes until hot throughout, adding a little more water if needed. Fluff the rice and serve with the tofu immediately.

**Research references**

- [Bee Yinn Low — Sambal Udang (Rasa Malaysia)](https://rasamalaysia.com/sambal-udang-prawn-sambal/) — Chilli-main-with-rice concept only. Our plain chilli, tomato and tofu dish is a distinct simplified composition, without belacan, tamarind or an authenticity claim.

**Review focus:** Choose a specific plain chilli paste and test the 15 g heat level. Confirm the paste contains no undeclared shrimp or other additions. Check tofu browning, sauce quantity and full-meal portions.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/sambal-tofu.yaml) · reviewed: false

<a id="sambal-prawn"></a>

## 40. Chilli prawns with rice

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** Adds a shellfish case for allergy filtering and a spicy alternative that otherwise reuses the tofu recipe's vegetable-and-rice basket. The ingredient list measures peeled meat, avoiding an unspoken shell-on conversion.

**Variant/design choice:** Prawn variation of sambal-tofu, with cooking steps changed for raw seafood. Never infer allergy safety from variant membership.

**Tags:** spicy, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| prawn | 300 g | raw peeled and deveined meat; thawed in the fridge if frozen |
| chilli paste | 15 g | plain chilli paste without shrimp paste; heat varies by brand |
| onion | 100 g | peeled and diced |
| garlic | 8 g | peeled and minced |
| tomato | 300 g | washed and diced |
| canola oil | 15 ml | — |
| salt | 1 g | — |
| uncooked rice | 180 g | dry white rice |
| water | enough to rinse and cook the rice plus a few splashes for the sauce | — |

**Method**

1. Rinse the rice and cook in a covered saucepan using its packet's water amount and cooking time. Rest covered off the heat when cooked.
2. Prepare the onion, garlic and tomato. Keep the raw prawns and their utensils separate from the cooked rice and vegetables.
3. Heat the oil in a frying pan over medium heat. Cook the onion for 4 minutes, then add the garlic and chilli paste and stir for a minute.
4. Add the tomato, salt and a splash of water. Simmer for 6-8 minutes until the tomato forms a sauce, stirring occasionally.
5. Add the prawns and turn them in the sauce for about 5-7 minutes. Verify the thickest prawns reach 75 C for 2 minutes; extend cooking as needed. Fluff the rice and serve immediately.

**Research references**

- [Bee Yinn Low — Sambal Udang (Rasa Malaysia)](https://rasamalaysia.com/sambal-udang-prawn-sambal/) — Prawn-and-chilli serving concept only. Tomato sauce, seasoning and amounts are original project choices.
- [Singapore Food Agency — Adopting Good Food Safety and Personal Hygiene Practices (6 December 2024)](https://www.sfa.gov.sg/docs/default-source/circulars/others/2024/advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf) — Cooking endpoint and separation of raw and cooked food.

**Review focus:** Test chilli strength, prawn size and cooking endpoint. Ensure fridge thawing and peeled raw weight are clear. Confirm shellfish restrictions come from Role 2's canonical ingredient metadata.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/sambal-prawn.yaml) · reviewed: false

<a id="lemon-pepper-fish"></a>

## 41. Lemon pepper fish with potatoes and carrots

**2 servings · 35 min total / 20 min active · equipment: stove**

**Why include it:** A complete plate outside the rice/noodle families, with cod, potatoes and carrots. Uses fresh lemon and pepper rather than adding a seasoning blend whose contents would complicate ingredient matching.

**Variant/design choice:** Base for a chicken variation. The cuisine tag is a broad navigation label; no specific regional authenticity is asserted.

**Tags:** light.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cod fillet | 320 g | boneless raw fillets about 2 cm thick; thawed in the fridge if frozen |
| potato | 450 g | scrubbed and cut into 2 cm cubes |
| carrot | 250 g | washed and sliced into 5 mm rounds |
| lemon | 0.5 pcs | washed; finely grate the yellow zest and reserve the juice |
| black pepper | 0.5 g | — |
| canola oil | 15 ml | — |
| salt | 1.5 g | — |
| water | enough to cover and boil the potatoes and carrots | — |

**Method**

1. Prepare the potatoes and carrots. Place them in a saucepan, cover with water, bring to a boil, and simmer for 12-15 minutes until a fork enters the potato easily. Drain and keep covered.
2. While the vegetables cook, zest and juice the lemon. Pat the cod dry, check for bones, and season with half the salt and half the black pepper.
3. Heat two-thirds of the oil in a non-stick frying pan over medium heat. Place the fillets in the pan and cook for about 4-5 minutes per side, turning carefully. Verify the centre reaches 75 C for 2 minutes; allow longer for thicker pieces.
4. Toss the drained vegetables with the remaining oil, salt and pepper, then add the lemon zest. Divide between plates with the fish and spoon the lemon juice over just before serving.

**Research references**

- [Nagi Maehashi — Crispy Pan Fried Fish (RecipeTin Eats)](https://www.recipetineats.com/crispy-pan-fried-fish/) — Technique reference for drying fillets and pan cooking. Our fish is uncoated and paired with an original potato-and-carrot side.
- [Singapore Food Agency — Adopting Good Food Safety and Personal Hygiene Practices (6 December 2024)](https://www.sfa.gov.sg/docs/default-source/circulars/others/2024/advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf) — Cooking-temperature endpoint.

**Review focus:** Check cod portion affordability, boneless handling, texture at the stated safe endpoint, pan sticking, lemon balance and potato tenderness. Verify time with approximately 2 cm fillets.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/lemon-pepper-fish.yaml) · reviewed: false

<a id="lemon-pepper-chicken"></a>

## 42. Lemon pepper chicken with potatoes and carrots

**2 servings · 40 min total / 25 min active · equipment: stove**

**Why include it:** Reuses the fish meal's vegetables and flavour components with chicken, so the catalogue offers a non-fish alternative without expanding the shopping vocabulary.

**Variant/design choice:** Chicken variation of lemon-pepper-fish. No more-protein claim; only the protein source changes.

**Tags:** light.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| chicken thigh | 320 g | raw boneless skinless meat; unfold and cut into strips about 2 cm thick |
| potato | 450 g | scrubbed and cut into 2 cm cubes |
| carrot | 250 g | washed and sliced into 5 mm rounds |
| lemon | 0.5 pcs | washed; finely grate the yellow zest and reserve the juice |
| black pepper | 0.5 g | — |
| canola oil | 15 ml | — |
| salt | 1.5 g | — |
| water | enough to cover and boil the vegetables plus a splash for the chicken pan | — |

**Method**

1. Cut the potatoes and carrots, cover them with water in a saucepan, and bring to a boil. Simmer for 12-15 minutes until the potato is tender, then drain and keep covered.
2. Meanwhile, prepare the lemon. Cut the chicken on a separate board; wash hands and utensils afterwards. Season the chicken with half the salt and half the pepper.
3. Heat two-thirds of the oil in a lidded non-stick frying pan over medium heat. Cook the chicken for 4 minutes, turn, and cook for 4 minutes more.
4. Add a splash of water and cover. Continue cooking for about 4-6 minutes, turning if needed. Verify the thickest chicken reaches 75 C for 2 minutes; extend cooking as necessary.
5. Toss the drained potatoes and carrots with the remaining oil, salt and pepper. Stir the lemon zest and juice into the cooked chicken pan, then serve the chicken and pan juices beside the vegetables immediately.

**Research references**

- [Nagi Maehashi — Lemon Pepper Chicken (RecipeTin Eats)](https://www.recipetineats.com/homemade-lemon-pepper-chicken/) — Lemon zest and pepper flavour concept only. No flour coating or source amounts are used; our thigh-strip meal and sides are original.
- [Singapore Food Agency — Adopting Good Food Safety and Personal Hygiene Practices (6 December 2024)](https://www.sfa.gov.sg/docs/default-source/circulars/others/2024/advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf) — Chicken cooking endpoint and cross-contamination precautions.

**Review focus:** Test 2 cm chicken strips, time to the specified endpoint, pan moisture, lemon bitterness and balanced portions. Confirm that the ingredient is boneless skinless thigh.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/lemon-pepper-chicken.yaml) · reviewed: false

<a id="pumpkin-lentil-soup"></a>

## 43. Pumpkin, potato and red lentil soup

**2 servings · 45 min total / 20 min active · equipment: stove**

**Why include it:** Provides a substantial one-pot soup using dry lentils, pumpkin and potato, with no blender, stock cube or cream needed. Useful for the soupy preference dimension and contrasting equipment/time scenarios.

**Variant/design choice:** Independent base recipe. Its low ingredient overlap with meat dishes adds variety without introducing new catalogue names.

**Tags:** soupy, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| pumpkin | 350 g | peeled and deseeded flesh cut into 2 cm cubes |
| potato | 250 g | scrubbed and cut into 1.5 cm cubes |
| red lentil | 140 g | dry split red lentils; rinsed and drained |
| onion | 100 g | peeled and diced |
| garlic | 8 g | peeled and minced |
| cumin powder | 2 g | — |
| canola oil | 10 ml | — |
| salt | 2 g | — |
| water | 1000 ml | cooking water; separate tap water is used to rinse produce and lentils |

**Method**

1. Prepare the vegetables and rinse the lentils. Heat the oil in a large saucepan over medium heat and soften the onion for 4 minutes.
2. Add the garlic and cumin and stir for 30 seconds. Add the pumpkin, potato, lentils and measured water, then bring to a boil.
3. Lower to a gentle simmer, partially cover, and cook for 25-30 minutes, stirring along the base regularly, until the lentils have collapsed and the pumpkin and potato are easily crushed.
4. If it thickens too quickly, cover fully and lower the heat. Mash some of the pumpkin and potato against the side of the pot with a spoon to thicken the soup without a blender.
5. Stir in the salt, check everything is tender, and divide the hot soup between bowls. The potatoes and lentils are part of the meal; no unlisted bread or side is required.

**Research references**

- [Bianca Zapatka — Pumpkin Lentil Curry](https://biancazapatka.com/en/pumpkin-lentil-curry/) — Pumpkin and red-lentil pairing and simmering concept. The potato soup, water-based cooking liquid and seasoning are original project choices.

**Review focus:** Test the soup's thickness, pot capacity, lentil softness and salt/cumin balance. Portions are intended as two substantial meal bowls. Verify 45-minute estimate including peeling pumpkin.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/pumpkin-lentil-soup.yaml) · reviewed: false

<a id="chicken-rice-porridge"></a>

## 44. Ginger chicken rice porridge

**2 servings · 60 min total / 20 min active · equipment: stove**

**Why include it:** Adds a familiar rice-porridge meal and a genuinely longer-cooking option. Starting from dry rice makes the total time honest and avoids silently requiring leftover rice. No added oil is used.

**Variant/design choice:** Base for mushroom-and-tofu porridge. low_oil is an internal qualitative tag here because the recipe has no added oil, not a regulated nutrition claim.

**Tags:** light, soupy, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 140 g | dry white rice; rinsed and drained |
| chicken thigh | 260 g | raw boneless skinless meat cut into 1 cm strips |
| ginger | 15 g | peeled and cut into fine strips |
| spring onion | 15 g | Optional. washed and finely sliced |
| salt | 2 g | — |
| water | 1400 ml | measured cooking water; additional water for rinsing or preparing the noodles/rice as instructed, plus small top-ups if needed |

**Method**

1. Rinse and drain the rice. Put it in a large saucepan with the ginger and the cooking water, using a little more than a litre of water per 100 g dry rice as a starting point, then bring to a boil.
2. Reduce to a gentle simmer with the lid partly open. Cook for 35-40 minutes, stirring along the base regularly, until the grains are very soft and the mixture is porridge-like. Add water if it becomes too thick.
3. While it simmers, prepare the chicken on a separate board. Wash hands and utensils, then prepare the spring onion if using.
4. Stir the chicken strips into the simmering porridge so they separate. Cook for about 8-10 minutes, stirring often. Verify the thickest chicken reaches 75 C for 2 minutes.
5. Add the salt and spring onion if using. Simmer for another minute, then serve promptly; this recipe starts from dry rice and needs no advance rice cooking.

**Research references**

- [Daddy Lau — Congee (Made With Lau)](https://www.madewithlau.com/recipes/chicken-congee) — Raw-rice porridge base concept. Project uses its own quantities, gentle simmer, simple ginger seasoning and no source marinade.
- [Singapore Food Agency — Adopting Good Food Safety and Personal Hygiene Practices (6 December 2024)](https://www.sfa.gov.sg/docs/default-source/circulars/others/2024/advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf) — Chicken cooking endpoint and separate handling of raw meat.

**Review focus:** Test rice type and liquid amount, sticking, bowl size, 60-minute timing and chicken endpoint. Confirm that the measured starting water amount is treated as a starting point, with texture determining top-ups.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/chicken-rice-porridge.yaml) · reviewed: false

<a id="mushroom-rice-porridge"></a>

## 45. Mushroom and tofu rice porridge

**2 servings · 60 min total / 20 min active · equipment: stove**

**Why include it:** A tofu-and-mushroom counterpart to chicken porridge that maintains a meaningful protein ingredient and the same meal format. Reuses fresh shiitake and tofu from the other soup and rice dishes.

**Variant/design choice:** Mushroom-and-tofu variation of chicken-rice-porridge. Derive actual dietary eligibility from ingredient metadata, particularly the selected soy sauce.

**Tags:** light, soupy, low_oil.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| uncooked rice | 140 g | dry white rice; rinsed and drained |
| fresh shiitake mushroom | 150 g | cleaned; tough stems removed and caps thinly sliced |
| firm tofu | 300 g | drained and cut into 1.5 cm cubes |
| ginger | 15 g | peeled and cut into fine strips |
| spring onion | 15 g | Optional. washed and finely sliced |
| soy sauce | 20 ml | — |
| water | 1400 ml | measured cooking water; additional water for rinsing or preparing the noodles/rice as instructed, plus small top-ups if needed |

**Method**

1. Rinse and drain the rice. Add to a large saucepan with the ginger and cooking water, using a little more than a litre of water per 100 g dry rice as a starting point. Bring to a boil.
2. Lower to a gentle simmer, leave the lid partly open, and cook for 35-40 minutes, stirring regularly along the base. Add more water if needed as the grains soften and split.
3. Meanwhile, prepare the mushrooms, tofu and spring onion if using. Add the mushrooms and tofu once the rice is very soft.
4. Simmer for 10-12 minutes, stirring gently, until the mushrooms are tender and the tofu is hot through. Stir in the soy sauce and spring onion if using.
5. Check the porridge is loose enough to spoon, adding water and bringing back to a simmer if needed. Divide into bowls and serve promptly.

**Research references**

- [Daddy Lau — Congee (Made With Lau)](https://www.madewithlau.com/recipes/chicken-congee) — Raw-rice porridge concept only; mushroom, tofu, soy seasoning and amounts are original.

**Review focus:** Test seasoning without stock, mushroom texture, liquid ratio and portion size. Verify fresh shiitake weight rather than substituting dried mushrooms at the same amount.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/mushroom-rice-porridge.yaml) · reviewed: false

<a id="cucumber-tomato-chickpea-salad"></a>

## 46. Cucumber, tomato and chickpea rice salad

**2 servings · 15 min total / 15 min active · equipment: none (prepared ingredients)**

**Why include it:** A no-appliance assembly option for users with already cooked rice, giving the catalogue a useful equipment-filter boundary. Chickpeas and rice make it a meal, while cucumber and tomato use shared perishable ingredients.

**Variant/design choice:** Independent recipe. Fifteen minutes is assembly time with cooked rice already available; it must not be offered as a 15-minute dry-rice substitution.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| cucumber | 200 g | washed and diced |
| tomato | 250 g | washed and diced |
| canned chickpea | 300 g | drained cooked weight; ready to eat according to the label |
| cooked rice | 300 g | freshly cooked for immediate use or promptly chilled and kept below 4 C; cooking and chilling time excluded |
| lemon | 0.5 pcs | washed; juice only |
| canola oil | 15 ml | — |
| salt | 1 g | — |
| black pepper | 0.5 g | — |

**Method**

1. Start with freshly cooked rice for immediate assembly, or cold cooked rice that was chilled promptly and kept below 4 C. The 15-minute time assumes cooked rice is already available; do not leave hot rice out to cool for this salad.
2. Wash and dice the cucumber and tomato. Drain the canned chickpeas and check that the label permits eating them without further cooking.
3. Squeeze the lemon juice into a large bowl and mix with the oil, salt and pepper.
4. Add the rice, chickpeas, cucumber and tomato. Fold together so the dressing is evenly distributed, then divide between bowls and eat immediately. If serving later, refrigerate promptly below 4 C.

**Research references**

- [Jeanine Donofrio — Chickpea Salad (Love and Lemons)](https://www.loveandlemons.com/chickpea-salad/) — Chickpea, vegetable and lemon concept only; our rice meal and simple dressing are original.
- [Singapore Food Agency — Fried Rice Syndrome](https://www.sfa.gov.sg/food-safety-tips/food-risk-concerns/risk-at-a-glance/fried-rice-syndrome) — Prompt chilling and cold storage of cooked rice; immediate service when freshly cooked rice is used.

**Review focus:** Check filling portions, canned chickpea label, rice handling and lemon balance. Confirm the UI preserves the advance-cooking caveat and does not automatically map uncooked rice to cooked rice.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/cucumber-tomato-chickpea-salad.yaml) · reviewed: false

<a id="sesame-soba-tofu"></a>

## 47. Sesame soba with tofu and vegetables

**2 servings · 25 min total / 20 min active · equipment: stove**

**Why include it:** A noodle meal with a different texture from rice vermicelli, using shared tofu, carrot and cucumber. Provides useful soy, sesame and soba-product composition cases for authoritative ingredient-based filtering.

**Variant/design choice:** Base for an egg variation; no more-protein claim. Japanese is a broad catalogue label, not an authenticity claim for this simplified dressing.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| soba noodle | 180 g | dry soba; check packet cooking time and product composition |
| firm tofu | 300 g | drained and cut into 1.5 cm cubes |
| cucumber | 200 g | washed and cut into thin strips |
| carrot | 150 g | washed and coarsely grated |
| sesame oil | 10 ml | — |
| soy sauce | 20 ml | — |
| water | enough to simmer the tofu and boil and rinse the noodles | — |

**Method**

1. Bring a large saucepan of water to a boil. Meanwhile, prepare the cucumber, carrot and tofu, and mix the sesame oil and soy sauce in a large serving bowl.
2. Gently simmer the tofu cubes in the water for 5 minutes or until heated through according to the packet, then lift them into a colander with a slotted spoon.
3. Return the water to a boil and add the soba. Cook for the time on the noodle packet, stirring gently to separate the strands.
4. Drain the noodles, rinse under cold running water to remove surface starch, and drain well.
5. Toss the noodles, cucumber and carrot in the dressing, fold in the warm drained tofu, and serve immediately. Refrigerate any portion being kept for later promptly.

**Research references**

- [Nami — Soba Noodle Salad (Just One Cookbook)](https://www.justonecookbook.com/soba-salad/) — Noodle rinsing and substantial salad variation concepts; project dressing, tofu preparation, amounts and prose are original.

**Review focus:** Test noodle brand timing, sesame/soy balance and warm tofu with cooled noodles. Confirm the selected soba's wheat/buckwheat composition and tofu's packet instructions before publishing diet or allergen labels.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/sesame-soba-tofu.yaml) · reviewed: false

<a id="sesame-soba-egg"></a>

## 48. Sesame soba with egg and vegetables

**2 servings · 30 min total / 20 min active · equipment: stove**

**Why include it:** An egg counterpart to tofu soba, retaining the same vegetables, dressing and noodle basket. Gives an explicit egg-filter case without adding a new ingredient.

**Variant/design choice:** Egg variation of sesame-soba-tofu. It replaces tofu rather than adding a certified protein increase.

**Tags:** light, vegetable_rich.

| Ingredient | Amount for two | Preparation / optionality |
|---|---|---|
| soba noodle | 180 g | dry soba; check packet cooking time and product composition |
| egg | 4 pcs | whole chicken eggs |
| cucumber | 200 g | washed and cut into thin strips |
| carrot | 150 g | washed and coarsely grated |
| sesame oil | 10 ml | — |
| soy sauce | 20 ml | — |
| water | enough to boil and cool the eggs and separately boil and rinse the noodles | — |

**Method**

1. Put the eggs in a saucepan, cover with water, and bring to a boil. Reduce to a gentle simmer for 10-12 minutes, until the whites and yolks are fully firm. Cool under cold running water, peel, and quarter.
2. While the eggs cook, wash and prepare the cucumber and carrot. Mix the sesame oil and soy sauce in a large serving bowl.
3. In a separate saucepan, bring fresh water to a boil and cook the soba for the time on its packet, stirring gently to separate the strands.
4. Drain the noodles and rinse under cold running water to remove surface starch, then drain well.
5. Toss the noodles and vegetables in the dressing, divide between bowls, and top with the egg. Serve immediately or refrigerate promptly if keeping for later.

**Research references**

- [Nami — Soba Noodle Salad (Just One Cookbook)](https://www.justonecookbook.com/soba-salad/) — Noodle rinsing and egg-meal variation concept only; amounts, dressing and egg preparation are project choices.

**Review focus:** Check egg doneness, portion appetite, noodle timing and the two-saucepan 30-minute estimate. Keep egg, sesame, soy and soba composition visible to Role 2's metadata review.

- [ ] Ingredient forms, quantities, portions and flavour reviewed.
- [ ] Equipment, timing, cooking steps and handling reviewed.
- [ ] Variant differences and tags make sense for the project.

Record reviewer, date, changes and any cooking-trial evidence in the review PR. These generated checkboxes are a review checklist, not the evidence record.

[Recipe YAML](../backend/seed/recipes/sesame-soba-egg.yaml) · reviewed: false

## Ingredient reuse

Counts include variants and optional ingredients. This shows catalogue reuse, not expected purchase quantities or required stock.

| Canonical ingredient | Recipes using it |
|---|---|
| black pepper | 5 |
| bok choy | 5 |
| broccoli | 4 |
| cabbage | 7 |
| canned chickpea | 3 |
| canola oil | 33 |
| carrot | 13 |
| cauliflower | 1 |
| chicken thigh | 9 |
| chilli paste | 4 |
| chye sim | 1 |
| coconut milk | 2 |
| cod fillet | 3 |
| cooked rice | 7 |
| cucumber | 3 |
| cumin powder | 5 |
| egg | 13 |
| firm tofu | 14 |
| fresh shiitake mushroom | 4 |
| frozen pea | 4 |
| garlic | 28 |
| ginger | 17 |
| lemon | 4 |
| long bean | 3 |
| onion | 10 |
| potato | 5 |
| prawn | 1 |
| pumpkin | 1 |
| red lentil | 3 |
| rice vermicelli | 7 |
| salt | 22 |
| sesame oil | 2 |
| soba noodle | 2 |
| soy sauce | 26 |
| spinach | 1 |
| spring onion | 19 |
| tempeh | 2 |
| tomato | 12 |
| turmeric powder | 6 |
| uncooked rice | 28 |
| water | 43 |
| water spinach | 1 |

Generated from the recipe YAML files, recipe_plan.yaml and recipe_review.yaml. Update those sources and run `uv run python scripts/render_recipe_review.py` from backend/ to refresh this guide.
