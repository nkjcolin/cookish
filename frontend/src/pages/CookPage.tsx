import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import type { Schemas } from "../api/client";
import { useCookStep, useCookSuggestion, useInterpret, useSelectSuggestion, useStarRecipe } from "../api/cook";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { Icon } from "../components/Icon";
import { Tag } from "../components/Tag";
import { AdjustSheet } from "./cook/AdjustSheet";
import { QuickCheckSheet } from "./cook/QuickCheckSheet";
import { COOK_TAG_LABELS, TASTE_TAG_LABELS, difficultyLabel, ingredientLines, mealName } from "./cook/view";

type Suggestion = Schemas["Suggestion"];
type CookTag = Schemas["CookTag"];

const displayFont = { fontVariationSettings: '"SOFT" 0, "WONK" 1' };
const heroImage = {
  backgroundImage: "linear-gradient(160.97deg, rgb(214, 237, 204) 0%, rgb(92, 153, 102) 83.333%)",
};

export function CookPage() {
  const navigate = useNavigate();
  const session = useCookSuggestion();
  const suggestion = session.data;
  const step = useCookStep(suggestion?.session_id);
  const select = useSelectSuggestion(suggestion?.session_id);
  const interpret = useInterpret();
  const [request, setRequest] = useState("");
  const [sheet, setSheet] = useState<"adjust" | "check" | null>(null);

  const now = new Date();
  const meal = mealName(now);
  const busy = step.isPending || select.isPending || interpret.isPending;
  const failure = session.error ?? step.error ?? select.error ?? interpret.error;

  function showRecipe() {
    setSheet(null);
    select.mutate(undefined, { onSuccess: () => navigate("/cook/recipe") });
  }

  function cookThis() {
    const unsure = suggestion && suggestion.needs_check.length + suggestion.freshness_check.length > 0;
    if (unsure) setSheet("check");
    else showRecipe();
  }

  function nudge(tag: CookTag) {
    step.mutate({ kind: "adjust", body: { tags: [tag] } });
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = request.trim();
    if (!text) return;
    const { adjust } = await interpret.mutateAsync(text);
    step.mutate({ kind: "adjust", body: adjust }, { onSuccess: () => setRequest("") });
  }

  return (
    <div className="flex flex-col gap-[16px]">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-[2px]">
          <p className="text-[13px] font-semibold text-ink-muted">
            {now.toLocaleDateString("en-GB", { weekday: "short" })} · {meal.charAt(0).toUpperCase() + meal.slice(1)}
            {suggestion && ` for ${suggestion.people}`}
          </p>
          <h1 className="font-display text-[28px] leading-[1.2] font-semibold whitespace-nowrap" style={displayFont}>
            What’s for {meal}?
          </h1>
        </div>
        <button
          type="button"
          aria-label="Adjust"
          disabled={!suggestion}
          onClick={() => setSheet("adjust")}
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="sliders-ink" />
        </button>
      </div>

      {session.isPending && <p className="text-[14px] text-ink-muted">Finding something to cook…</p>}
      {failure && (
        <p role="alert" className="text-[13px] text-danger">
          {failure.message}
        </p>
      )}

      {suggestion && (
        <>
          <Constraints suggestion={suggestion} onEdit={() => setSheet("adjust")} />
          <SuggestionCard
            suggestion={suggestion}
            busy={busy}
            onSkip={() => step.mutate({ kind: "next" })}
            onPrevious={() => step.mutate({ kind: "previous" })}
            onCook={cookThis}
          />

          <section className="flex flex-col gap-[10px]">
            <h2 className="text-[15px] font-bold whitespace-nowrap">Not quite? Nudge it</h2>
            <div className="-mx-[20px] flex items-start gap-[8px] overflow-x-auto px-[20px] [scrollbar-width:none]">
              {(Object.keys(COOK_TAG_LABELS) as CookTag[]).map((tag) => (
                <Chip
                  key={tag}
                  selected={suggestion.applied_constraints.tags.includes(tag)}
                  onClick={() => nudge(tag)}
                >
                  {COOK_TAG_LABELS[tag]}
                </Chip>
              ))}
            </div>
            <form
              onSubmit={(event) => void ask(event)}
              className="flex items-center gap-[8px] rounded-pill border border-border bg-surface py-[6px] pr-[6px] pl-[16px]"
            >
              <input
                value={request}
                onChange={(event) => setRequest(event.target.value)}
                aria-label="Describe what you feel like"
                placeholder="e.g. “something warm, not spicy”"
                className="min-w-px flex-1 bg-transparent text-[14px] outline-none placeholder:text-ink-subtle"
              />
              <button
                type="submit"
                aria-label="Send"
                disabled={busy || request.trim() === ""}
                className="flex size-[36px] shrink-0 items-center justify-center rounded-pill bg-dark disabled:opacity-50"
              >
                <Icon name="arrow-up" />
              </button>
            </form>
          </section>

          {sheet === "adjust" && (
            <AdjustSheet
              suggestion={suggestion}
              meal={meal}
              onApply={(body) => step.mutate({ kind: "adjust", body })}
              onClose={() => setSheet(null)}
            />
          )}
          {sheet === "check" && (
            <QuickCheckSheet
              suggestion={suggestion}
              onProceed={showRecipe}
              onUnavailable={() => {
                setSheet(null);
                step.mutate({ kind: "next" });
              }}
              onClose={() => setSheet(null)}
            />
          )}
        </>
      )}
    </div>
  );
}

/** What this session is currently held to; tapping any of it opens the adjust sheet. */
function Constraints({ suggestion, onEdit }: { suggestion: Suggestion; onEdit: () => void }) {
  const { max_minutes: maxMinutes, tags } = suggestion.applied_constraints;
  return (
    <div className="-mx-[20px] flex items-start gap-[8px] overflow-x-auto px-[20px] [scrollbar-width:none]">
      {maxMinutes !== null && (
        <Chip selected onClick={onEdit}>
          ≤ {maxMinutes} min
        </Chip>
      )}
      <Chip onClick={onEdit}>
        {suggestion.people} {suggestion.people === 1 ? "person" : "people"}
      </Chip>
      {tags.map((tag) => (
        <Chip key={tag} selected onClick={onEdit}>
          {COOK_TAG_LABELS[tag]}
        </Chip>
      ))}
    </div>
  );
}

type SuggestionCardProps = {
  suggestion: Suggestion;
  busy: boolean;
  onSkip: () => void;
  onPrevious: () => void;
  onCook: () => void;
};

function SuggestionCard({ suggestion, busy, onSkip, onPrevious, onCook }: SuggestionCardProps) {
  const { recipe } = suggestion;
  const star = useStarRecipe();

  return (
    <article className="flex flex-col overflow-clip rounded-lg border border-border bg-surface shadow-[0px_8px_24px_0px_rgba(89,51,26,0.08)]">
      <div className="flex h-[120px] items-center justify-center" style={heroImage}>
        <span className="opacity-92">
          <Icon name="leaf-hero" />
        </span>
      </div>
      <div className="flex flex-col gap-[12px] p-[16px]">
        <div className="flex items-start gap-[10px]">
          <h2 className="min-w-px flex-1 font-display text-[22px] leading-[1.2] font-semibold" style={displayFont}>
            {recipe.title}
          </h2>
          <button
            type="button"
            aria-label={recipe.starred ? "Remove star" : "Star this recipe"}
            aria-pressed={recipe.starred}
            disabled={star.isPending}
            onClick={() => star.mutate({ recipeId: recipe.id, starred: !recipe.starred })}
            className={`flex size-[36px] shrink-0 items-center justify-center rounded-pill border border-border ${
              recipe.starred ? "bg-warn-soft" : "bg-surface"
            }`}
          >
            <Icon name="star" />
          </button>
        </div>

        <div className="flex flex-wrap items-start gap-[6px]">
          <Tag>
            <Icon name="clock-sm" />
            {recipe.total_minutes} min
          </Tag>
          <Tag>{difficultyLabel(recipe.difficulty)}</Tag>
          {recipe.taste_tags.map((tag) => (
            <Tag key={tag}>{TASTE_TAG_LABELS[tag]}</Tag>
          ))}
        </div>

        <ul className="flex flex-col gap-[6px]">
          {ingredientLines(suggestion).map((line) => (
            <li key={line.text} className="flex items-center gap-[6px]">
              <Icon name={line.tone === "ok" ? "check-green" : "help-sm"} />
              <p className={`text-[13px] ${line.tone === "ok" ? "text-ink-muted" : "font-semibold text-warn"}`}>
                {line.text}
              </p>
            </li>
          ))}
        </ul>

        <div className="flex gap-[10px]">
          <Button variant="secondary" className="min-w-px flex-1" onClick={onSkip} disabled={busy}>
            Not tonight
          </Button>
          <Button className="min-w-px flex-1" onClick={onCook} disabled={busy}>
            Cook this
          </Button>
        </div>
        {suggestion.has_previous && (
          <button
            type="button"
            onClick={onPrevious}
            disabled={busy}
            className="self-center text-[13px] font-semibold text-primary disabled:opacity-50"
          >
            Back to the previous one
          </button>
        )}
      </div>
    </article>
  );
}
