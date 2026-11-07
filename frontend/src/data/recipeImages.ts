/** Static serving illustrations for the reviewed seed catalogue; keys are stable recipe UUIDs. */
export type RecipeImageData = { src: string; alt: string };

// Less-oil variants share their parent illustration; all changed ingredient combinations
// and the quick mixed-rice recipe have distinct images. Never match images by title.
export const RECIPE_IMAGES: Readonly<Record<string, RecipeImageData>> = {
  // bee-hoon-cabbage
  "48daffdb-9a7e-4645-b7bd-dc3b575080b2": {
    src: "/recipes/bee-hoon-cabbage.webp",
    alt: "Illustrative serving of cabbage and carrot bee hoon",
  },
  // bee-hoon-egg
  "88e3e915-9e9a-4d66-8520-90c4efb34f8a": {
    src: "/recipes/bee-hoon-egg.webp",
    alt: "Illustrative serving of egg, cabbage and carrot bee hoon",
  },
  // cabbage-carrot-egg-fried-rice
  "84caffd7-90b8-4d20-878c-c266f7fa6a87": {
    src: "/recipes/cabbage-carrot-egg-fried-rice.webp",
    alt: "Illustrative serving of egg fried rice with extra cabbage and carrot",
  },
  // cabbage-tofu-stir-fry
  "2173bce1-8bbd-40ee-be78-e80627d8ba07": {
    src: "/recipes/cabbage-tofu-stir-fry.webp",
    alt: "Illustrative serving of cabbage and tofu rice bowls",
  },
  // cabbage-tofu-stir-fry-less-oil
  "79093e58-6ac3-46ab-adee-c948efc5b880": {
    src: "/recipes/cabbage-tofu-stir-fry.webp",
    alt: "Illustrative serving of cabbage and tofu rice bowls",
  },
  // chicken-broccoli-stir-fry
  "5380fd71-a373-4bed-8474-7f0d8e46cb43": {
    src: "/recipes/chicken-broccoli-stir-fry.webp",
    alt: "Illustrative serving of chicken and broccoli stir-fry with rice",
  },
  // chicken-rice-porridge
  "1d920435-f931-4d7b-91d2-86d184e31e3b": {
    src: "/recipes/chicken-rice-porridge.webp",
    alt: "Illustrative serving of ginger chicken rice porridge",
  },
  // chicken-vegetable-fried-rice
  "5189d7a4-b3b0-4bbb-90f3-0622f193d72a": {
    src: "/recipes/chicken-vegetable-fried-rice.webp",
    alt: "Illustrative serving of chicken, egg and vegetable fried rice",
  },
  // chickpea-tomato-curry
  "785f4606-ac45-4a26-b915-a47a0eab08ae": {
    src: "/recipes/chickpea-tomato-curry.webp",
    alt: "Illustrative serving of chickpea and tomato curry with rice",
  },
  // chye-sim-egg-bee-hoon
  "ecbccf1f-44c2-448b-a25f-2695250fe976": {
    src: "/recipes/chye-sim-egg-bee-hoon.webp",
    alt: "Illustrative serving of chye sim and egg bee hoon soup",
  },
  // coconut-chicken-curry
  "f7c59407-af6a-4501-8f26-ce7668147f45": {
    src: "/recipes/coconut-chicken-curry.webp",
    alt: "Illustrative serving of coconut chicken and vegetable curry with rice",
  },
  // coconut-tofu-curry
  "5bd66173-7561-4c71-965d-ee17a8c8ebed": {
    src: "/recipes/coconut-tofu-curry.webp",
    alt: "Illustrative serving of coconut tofu and vegetable curry with rice",
  },
  // cucumber-tomato-chickpea-salad
  "719b4fca-2889-4389-a4f7-8605dee34c48": {
    src: "/recipes/cucumber-tomato-chickpea-salad.webp",
    alt: "Illustrative serving of cucumber, tomato and chickpea rice salad",
  },
  // egg-fried-rice
  "82837c0b-d649-4fe6-aa5b-196c64459b28": {
    src: "/recipes/egg-fried-rice.webp",
    alt: "Illustrative serving of egg fried rice with vegetables",
  },
  // fish-tomato-soup
  "61456d3b-fc96-4bef-91b5-f54dce95fed7": {
    src: "/recipes/fish-tomato-soup.webp",
    alt: "Illustrative serving of fish and tomato vermicelli soup",
  },
  // garlic-water-spinach
  "c3f44203-7245-430e-ad1b-52428f6cfed3": {
    src: "/recipes/garlic-water-spinach.webp",
    alt: "Illustrative serving of garlic water spinach and tofu rice bowls",
  },
  // ginger-chicken-rice
  "85d5ed52-10d6-4769-8bc5-435decbd08d8": {
    src: "/recipes/ginger-chicken-rice.webp",
    alt: "Illustrative serving of one-pot ginger chicken and bok choy rice",
  },
  // ginger-chicken-rice-less-oil
  "bd2118d6-393b-413f-b7e6-b3116b108437": {
    src: "/recipes/ginger-chicken-rice.webp",
    alt: "Illustrative serving of one-pot ginger chicken and bok choy rice",
  },
  // ginger-chicken-soup
  "c67a5a88-4c59-4498-a8c6-b76b4e30257e": {
    src: "/recipes/ginger-chicken-soup.webp",
    alt: "Illustrative serving of ginger chicken and potato soup",
  },
  // lemon-pepper-chicken
  "f81dd997-b06c-48ce-87ec-43727f62e023": {
    src: "/recipes/lemon-pepper-chicken.webp",
    alt: "Illustrative serving of lemon pepper chicken with potatoes and carrots",
  },
  // lemon-pepper-fish
  "6c1f5f1d-bf31-48d5-8ea1-ce2572a89897": {
    src: "/recipes/lemon-pepper-fish.webp",
    alt: "Illustrative serving of lemon pepper fish with potatoes and carrots",
  },
  // lentil-spinach-dhal
  "445528bb-43c7-432d-a06f-859645a43ab0": {
    src: "/recipes/lentil-spinach-dhal.webp",
    alt: "Illustrative serving of red lentil and spinach dhal with rice",
  },
  // microwave-broccoli-chickpea-rice
  "0c7bea35-103a-4199-b3cd-11cf607baf3f": {
    src: "/recipes/microwave-broccoli-chickpea-rice.webp",
    alt: "Illustrative serving of microwave broccoli and chickpea rice",
  },
  // mushroom-omelette
  "aa138433-2918-4a6f-b361-c1fe5eedeaaf": {
    src: "/recipes/mushroom-omelette.webp",
    alt: "Illustrative serving of mushroom omelette with rice",
  },
  // mushroom-rice-porridge
  "ed9445a6-d029-4143-bbb5-22f64f133a2b": {
    src: "/recipes/mushroom-rice-porridge.webp",
    alt: "Illustrative serving of mushroom and tofu rice porridge",
  },
  // potato-cauliflower-curry
  "cd823518-b570-4185-ba71-b1d0cdde2adf": {
    src: "/recipes/potato-cauliflower-curry.webp",
    alt: "Illustrative serving of potato and cauliflower curry with rice",
  },
  // pumpkin-lentil-soup
  "5e1d2eab-44fb-4882-bd2e-577b6e186a26": {
    src: "/recipes/pumpkin-lentil-soup.webp",
    alt: "Illustrative serving of pumpkin, potato and red lentil soup",
  },
  // quicker-tomato-egg-rice
  "eaacfdcd-aa3e-4fd9-9252-7602e8fedc65": {
    src: "/recipes/quicker-tomato-egg-rice.webp",
    alt: "Illustrative serving of quick tomato and egg rice",
  },
  // red-lentil-dhal
  "97f2ee52-db16-4544-80ba-11b117dcd4b0": {
    src: "/recipes/red-lentil-dhal.webp",
    alt: "Illustrative serving of tomato and red lentil dhal with rice",
  },
  // rice-cooker-bok-choy-tofu-rice
  "a8fadb00-3dba-48b3-b7a8-5f9dc87f4a7e": {
    src: "/recipes/rice-cooker-bok-choy-tofu-rice.webp",
    alt: "Illustrative serving of rice-cooker bok choy and tofu rice",
  },
  // rice-vermicelli-chicken-soup
  "c3954096-77f8-49a4-a0c3-519390c4477d": {
    src: "/recipes/rice-vermicelli-chicken-soup.webp",
    alt: "Illustrative serving of bok choy and chicken bee hoon soup",
  },
  // rice-vermicelli-tofu-soup
  "202bfb57-26ca-4201-b935-7a7ea4db9785": {
    src: "/recipes/rice-vermicelli-tofu-soup.webp",
    alt: "Illustrative serving of bok choy and tofu bee hoon soup",
  },
  // sambal-prawn
  "bf7c533d-ae14-4e97-b0a5-fa05ef11a822": {
    src: "/recipes/sambal-prawn.webp",
    alt: "Illustrative serving of chilli prawns with rice",
  },
  // sambal-tofu
  "c3729c50-e498-4026-94d0-a35154738ed9": {
    src: "/recipes/sambal-tofu.webp",
    alt: "Illustrative serving of chilli tofu with rice",
  },
  // sesame-soba-egg
  "bb825baf-2b21-466f-8709-03d9b8a3abcf": {
    src: "/recipes/sesame-soba-egg.webp",
    alt: "Illustrative serving of sesame soba with egg and vegetables",
  },
  // sesame-soba-tofu
  "4a8e2e32-267d-4c29-a05c-179aa9f0ce24": {
    src: "/recipes/sesame-soba-tofu.webp",
    alt: "Illustrative serving of sesame soba with tofu and vegetables",
  },
  // steamed-egg
  "9d5276e3-b3c1-4fb0-8825-7334f1b5dba8": {
    src: "/recipes/steamed-egg.webp",
    alt: "Illustrative serving of steamed egg with rice",
  },
  // steamed-egg-tofu
  "d3f3cc29-e09a-4f90-938f-21526f114c44": {
    src: "/recipes/steamed-egg-tofu.webp",
    alt: "Illustrative serving of steamed egg and tofu with rice",
  },
  // steamed-ginger-fish
  "ab302fa5-3663-4431-b28c-f380b5b9b1f7": {
    src: "/recipes/steamed-ginger-fish.webp",
    alt: "Illustrative serving of steamed ginger cod with broccoli and rice",
  },
  // tempeh-cabbage-stir-fry
  "900f9630-7d36-4cad-9db6-1851bef26fd1": {
    src: "/recipes/tempeh-cabbage-stir-fry.webp",
    alt: "Illustrative serving of tempeh and cabbage stir-fry with rice",
  },
  // tempeh-long-bean-stir-fry
  "404b4550-6cd6-4ee4-b79e-9b0b87161ece": {
    src: "/recipes/tempeh-long-bean-stir-fry.webp",
    alt: "Illustrative serving of tempeh and long bean stir-fry with rice",
  },
  // tofu-broccoli-stir-fry
  "66ee604f-e55c-46a3-8d5f-a64e5e58085d": {
    src: "/recipes/tofu-broccoli-stir-fry.webp",
    alt: "Illustrative serving of tofu and broccoli stir-fry with rice",
  },
  // tofu-mushroom-rice
  "109d8db0-0c6c-4229-b0fc-bf295cfb6eb7": {
    src: "/recipes/tofu-mushroom-rice.webp",
    alt: "Illustrative serving of one-pot tofu and mushroom rice",
  },
  // tofu-mushroom-soup
  "cec3641a-2ff2-44ae-b64c-8e59d69bea59": {
    src: "/recipes/tofu-mushroom-soup.webp",
    alt: "Illustrative serving of tofu, mushroom and cabbage noodle soup",
  },
  // tofu-vegetable-fried-rice
  "23c3cd8d-ad33-4891-b2ec-6c10a93a43cb": {
    src: "/recipes/tofu-vegetable-fried-rice.webp",
    alt: "Illustrative serving of tofu and vegetable fried rice",
  },
  // tomato-egg-stir-fry
  "645a8d38-bfae-47f2-b00e-3ca6828a964e": {
    src: "/recipes/tomato-egg-stir-fry.webp",
    alt: "Illustrative serving of tomato and egg rice bowls",
  },
  // tomato-egg-stir-fry-less-oil
  "45045a12-f142-4125-b594-34f486c75032": {
    src: "/recipes/tomato-egg-stir-fry.webp",
    alt: "Illustrative serving of tomato and egg rice bowls",
  },
  // tomato-onion-omelette
  "aef915ed-711e-41c8-9d1a-8c31f0cd51f8": {
    src: "/recipes/tomato-onion-omelette.webp",
    alt: "Illustrative serving of tomato and onion omelette with rice",
  },
};

export function getRecipeImage(recipeId: string): RecipeImageData | undefined {
  return Object.hasOwn(RECIPE_IMAGES, recipeId) ? RECIPE_IMAGES[recipeId] : undefined;
}
