import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import type { Schemas } from "../api/client";
import { useCookRecord, useCurrentSuggestion, useFinishCooking, useRecipe, useStarRecipe } from "../api/cook";
import type { CookedState } from "./cook/view";
import { BottomBar } from "../components/BottomBar";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { RecipeImage } from "../components/RecipeImage";
import { Tag } from "../components/Tag";
import { TASTE_TAG_LABELS, difficultyLabel } from "./cook/view";
import { WhatsLeftSheet } from "./cook/WhatsLeftSheet";

type Status = Schemas["IngredientStatus"];

const displayFont = { fontVariationSettings: '"SOFT" 0, "WONK" 1' };
const roundButton =
  "absolute top-[8px] flex size-[40px] items-center justify-center rounded-pill border border-border bg-surface";

/** Previewing a suggestion never creates a cook record or enables stock confirmation. */
export function RecipePage({ preview = false }: { preview?: boolean }) {
  const navigate = useNavigate();
  const cachedRecord = useCookRecord();
  const record = preview ? undefined : cachedRecord;
  const suggestion = useCurrentSuggestion();
  const dish = preview ? suggestion : record;
  const recipe = useRecipe(dish?.recipe.id);
  const star = useStarRecipe();
  const finishCooking = useFinishCooking();
  const [starred, setStarred] = useState(dish?.recipe.starred ?? false);
  const [confirming, setConfirming] = useState(false);

  if (!dish) return <Navigate to="/cook" replace />;

  const summary = dish.recipe;
  const scaled = suggestion?.recipe.id === summary.id ? suggestion.ingredients : null;
  const missingEssentials = scaled?.some((line) => line.essential && line.status === "missing");

  function toggleStar() {
    star.mutate({ recipeId: summary.id, starred: !starred }, { onSuccess: (result) => setStarred(result.starred) });
  }

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="relative -mx-[20px] -mt-[16px] h-[230px] overflow-clip">
        <RecipeImage recipeId={summary.id} title={summary.title} className="h-full w-full" />
        <Link to="/cook" aria-label="Back" className={`${roundButton} left-[20px]`}>
          <Icon name="chevron-left" />
        </Link>
        <button
          type="button"
          aria-label={starred ? "Remove star" : "Star this recipe"}
          aria-pressed={starred}
          disabled={star.isPending}
          onClick={toggleStar}
          className={`${roundButton} right-[20px] ${starred ? "!bg-warn-soft" : ""}`}
        >
          <Icon name="star-lg" />
        </button>
      </div>

      <div className="flex flex-col gap-[10px]">
        <h1 className="font-display text-[28px] leading-[1.15] font-semibold" style={displayFont}>
          {summary.title}
        </h1>
        <div className="flex flex-wrap items-start gap-[6px]">
          <Tag>
            <Icon name="clock-sm" />
            {summary.total_minutes} min
          </Tag>
          <Tag>{difficultyLabel(summary.difficulty)}</Tag>
          {summary.taste_tags.map((tag) => (
            <Tag key={tag}>{TASTE_TAG_LABELS[tag]}</Tag>
          ))}
          {recipe.data?.variant_label && (
            <Tag tone="info">
              <Icon name="refresh-sm" />
              {recipe.data.variant_label} version
            </Tag>
          )}
        </div>
      </div>

      {preview && missingEssentials && (
        <p className="text-[13px] text-ink-muted">
          Get the missing ingredients first. If you already have them, update your kitchen.
        </p>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-[18px] font-bold whitespace-nowrap">Ingredients</h2>
        <span className="flex items-center gap-[10px] rounded-pill border border-border bg-surface py-[4px] pr-[12px] pl-[12px]">
          <Icon name="users-sm" />
          <span className="text-[13px] font-bold whitespace-nowrap">Serves {dish.people}</span>
        </span>
      </div>

      {recipe.isPending && <p className="text-[14px] text-ink-muted">Loading the recipe…</p>}
      {recipe.isError && (
        <p role="alert" className="text-[13px] text-danger">
          Could not load the recipe: {recipe.error.message}
        </p>
      )}

      {recipe.data && (
        <>
          <ul className="flex flex-col rounded-lg border border-border bg-surface px-[16px] py-[4px]">
            {recipe.data.ingredients.map((ingredient) => {
              const line = scaled?.find((s) => s.ingredient_id === ingredient.ingredient_id);
              const amount =
                line?.amount ??
                ingredient.coarse_amount ??
                (ingredient.quantity !== null ? `${ingredient.quantity} ${ingredient.unit ?? ""}`.trim() : "");
              return (
                <li
                  key={ingredient.ingredient_id}
                  className="flex items-center gap-[10px] border-b border-border py-[12px] last:border-b-0"
                >
                  <div className="flex min-w-px flex-1 flex-col gap-px">
                    <p className="text-[14px] font-semibold first-letter:uppercase">{ingredient.name}</p>
                    <p className="text-[12px] text-ink-muted">{amount || "to taste"}</p>
                  </div>
                  {line && <StatusTag status={line.status} />}
                </li>
              );
            })}
          </ul>

          <h2 className="text-[18px] font-bold whitespace-nowrap">Steps</h2>
          <ol className="flex flex-col gap-[14px]">
            {recipe.data.steps.map((step, index) => (
              <li key={index} className="flex items-start gap-[12px]">
                <span className="flex size-[26px] shrink-0 items-center justify-center rounded-pill bg-primary-soft text-[13px] font-bold text-primary">
                  {index + 1}
                </span>
                <p className="min-w-px flex-1 text-[14px] leading-[1.5]">{step}</p>
              </li>
            ))}
          </ol>
        </>
      )}

      <BottomBar>
        {preview ? (
          <div className="flex flex-col gap-[10px]">
            {missingEssentials ? (
              <>
                <Button className="w-full" onClick={() => navigate("/buy")}>
                  Go to Buy
                </Button>
                <Link to="/more/kitchen" className="text-center text-[14px] font-semibold text-primary">
                  Update kitchen
                </Link>
              </>
            ) : (
              <Button className="w-full" onClick={() => navigate("/cook")}>
                Back to suggestion
              </Button>
            )}
          </div>
        ) : (
          <Button className="w-full" onClick={() => setConfirming(true)}>
            I cooked this
          </Button>
        )}
      </BottomBar>

      {confirming && record && (
        <WhatsLeftSheet
          record={record}
          onClose={() => setConfirming(false)}
          onDone={(result) => {
            const cooked: CookedState = {
              recordId: record.id,
              title: summary.title,
              eventId: result.event.id,
              itemCount: result.event.lines.length,
            };
            finishCooking();
            navigate("/cook", { state: cooked });
          }}
        />
      )}
    </div>
  );
}

function StatusTag({ status }: { status: Status }) {
  switch (status) {
    case "have":
      return (
        <Tag tone="fresh">
          <Icon name="check-fresh-sm" />
          Have
        </Tag>
      );
    case "staple":
      return <Tag>Pantry</Tag>;
    case "low":
      return <Tag tone="warn">Running low</Tag>;
    case "missing":
      return <Tag tone="warn">Need to buy</Tag>;
    case "check":
      return <Tag tone="warn">Check first</Tag>;
    case "unknown":
      return <Tag>Not sure</Tag>;
  }
}
