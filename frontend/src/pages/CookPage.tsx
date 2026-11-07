import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, type Schemas } from "../api/client";
import {
  mergeConstraints,
  useCookStep,
  useCookSuggestion,
  useInterpret,
  useRestartCook,
  useSelectSuggestion,
  useStarRecipe,
  type CookConstraints,
} from "../api/cook";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { Icon } from "../components/Icon";
import { RecipeImage } from "../components/RecipeImage";
import { Tag } from "../components/Tag";
import { UndoToast } from "../components/UndoToast";
import { useArrivalState } from "../lib/arrival";
import { AdjustSheet } from "./cook/AdjustSheet";
import { FeedbackCard } from "./cook/FeedbackCard";
import { NoMatch } from "./cook/NoMatch";
import { QuickCheckSheet } from "./cook/QuickCheckSheet";
import {
  COOK_TAG_LABELS,
  TASTE_TAG_LABELS,
  availableNudges,
  difficultyLabel,
  ingredientLines,
  mealName,
  type CookedState,
} from "./cook/view";

type Suggestion = Schemas["Suggestion"];
type CookTag = Schemas["CookTag"];

const displayFont = { fontVariationSettings: '"SOFT" 0, "WONK" 1' };

export function CookPage() {
  const navigate = useNavigate();
  const session = useCookSuggestion();
  const suggestion = session.data;
  const step = useCookStep(suggestion?.session_id);
  const select = useSelectSuggestion(suggestion?.session_id);
  const interpret = useInterpret();
  const restart = useRestartCook();
  // Set when the service has nothing that satisfies the session (NO_RESULT).
  const [noMatch, setNoMatch] = useState<{ constraints: CookConstraints; relaxable: string[] } | null>(null);
  const [request, setRequest] = useState("");
  const [sheet, setSheet] = useState<"adjust" | "check" | null>(null);
  // Set when arriving from a meal that was just confirmed.
  const cooked = useArrivalState<CookedState>();
  const [askRating, setAskRating] = useState(cooked !== null);
  const [showToast, setShowToast] = useState(cooked !== null);

  const now = new Date();
  const meal = mealName(now);
  const busy = step.isPending || select.isPending || interpret.isPending || restart.isPending;
  const nudges = suggestion ? availableNudges(suggestion) : [];
  // "Nothing fits" is a state of its own (see NoMatch), not an error to report.
  const unlessNoResult = (error: Error | null) => (relaxableOf(error) ? null : error);
  const failure =
    session.error ?? unlessNoResult(step.error) ?? select.error ?? interpret.error ?? unlessNoResult(restart.error);

  /** Runs a step; when nothing fits, shows what could be relaxed instead of an error. */
  function run(next: Parameters<typeof step.mutate>[0]) {
    step.mutate(next, {
      onSuccess: () => setNoMatch(null),
      onError: (error) => {
        const relaxable = relaxableOf(error);
        if (!suggestion || !relaxable) return;
        setNoMatch({ constraints: mergeConstraints(suggestion, next.kind === "adjust" ? next.body : null), relaxable });
      },
    });
  }

  /** Tries again with fewer constraints; if that still fits nothing, offers to relax more. */
  function relax(constraints: CookConstraints) {
    restart.mutate(constraints, {
      onSuccess: () => setNoMatch(null),
      onError: (error) => {
        const relaxable = relaxableOf(error);
        if (relaxable) setNoMatch({ constraints, relaxable });
      },
    });
  }

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
    run({ kind: "adjust", body: { tags: [tag] } });
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = request.trim();
    if (!text) return;
    try {
      const { adjust } = await interpret.mutateAsync(text);
      run({ kind: "adjust", body: adjust });
      setRequest("");
    } catch {
      // The mutation error is shown above; keep the request available to edit.
    }
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
          disabled={!suggestion || busy}
          onClick={() => setSheet("adjust")}
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="sliders-ink" />
        </button>
      </div>

      {cooked && askRating && (
        <FeedbackCard recordId={cooked.recordId} title={cooked.title} onDone={() => setAskRating(false)} />
      )}

      {session.isPending && <p className="text-[14px] text-ink-muted">Finding something to cook…</p>}
      {failure && (
        <p role="alert" className="text-[13px] text-danger">
          {failure.message}
        </p>
      )}

      {suggestion && noMatch && (
        <NoMatch
          constraints={noMatch.constraints}
          relaxable={noMatch.relaxable}
          busy={busy}
          onAllowMoreTime={(minutes) =>
            // The adjustment that failed was never applied, so everything it asked for is sent again.
            run({ kind: "adjust", body: { tags: noMatch.constraints.tags, people: noMatch.constraints.people, max_minutes: minutes } })
          }
          onDropTime={() => relax({ ...noMatch.constraints, maxMinutes: null })}
          onDropTag={(tag) => relax({ ...noMatch.constraints, tags: noMatch.constraints.tags.filter((t) => t !== tag) })}
          onStartOver={() => relax({ people: noMatch.constraints.people, tags: [], maxMinutes: null })}
        />
      )}

      {suggestion && !noMatch && (
        <>
          <Constraints
            suggestion={suggestion}
            busy={busy}
            onEdit={() => setSheet("adjust")}
            onReset={() => relax({ people: suggestion.people, tags: [], maxMinutes: null })}
          />
          <SuggestionCard
            suggestion={suggestion}
            busy={busy}
            onSkip={() => run({ kind: "next" })}
            onPrevious={() => run({ kind: "previous" })}
            onCook={cookThis}
            onPreview={() => navigate("/cook/preview")}
          />

          <section aria-label="Recipe nudges" className="flex flex-col gap-[10px]">
            <h2 className="text-[15px] font-bold whitespace-nowrap">Not quite? Nudge it</h2>
            <div className="-mx-[20px] flex items-start gap-[8px] overflow-x-auto px-[20px] [scrollbar-width:none]">
              {nudges.map((tag) => (
                <Chip
                  key={tag}
                  suggested
                  disabled={busy}
                  onClick={() => nudge(tag)}
                >
                  {COOK_TAG_LABELS[tag]}
                </Chip>
              ))}
            </div>
            {nudges.length === 0 && (
              <p className="text-[13px] text-ink-muted">No nudges fit this recipe right now. Try Not tonight or Adjust.</p>
            )}
            <form
              onSubmit={(event) => void ask(event)}
              className="flex items-center gap-[8px] rounded-pill border border-border bg-surface py-[6px] pr-[6px] pl-[16px]"
            >
              <input
                value={request}
                onChange={(event) => setRequest(event.target.value)}
                aria-label="Describe what you feel like"
                placeholder="e.g. “less oil”"
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
              onApply={(body) => run({ kind: "adjust", body })}
              onClose={() => setSheet(null)}
            />
          )}
          {sheet === "check" && (
            <QuickCheckSheet
              suggestion={suggestion}
              onProceed={showRecipe}
              onUnavailable={() => {
                setSheet(null);
                run({ kind: "next" });
              }}
              onClose={() => setSheet(null)}
            />
          )}
        </>
      )}

      {cooked && showToast && (
        <UndoToast
          eventId={cooked.eventId}
          message={`Kitchen updated · ${cooked.itemCount} ${cooked.itemCount === 1 ? "item" : "items"}`}
          onDismiss={() => setShowToast(false)}
        />
      )}
    </div>
  );
}

/** The soft conditions a NO_RESULT error says could be relaxed; null for any other error. */
function relaxableOf(error: unknown): string[] | null {
  if (!(error instanceof ApiError) || error.code !== "NO_RESULT") return null;
  return Array.isArray(error.details.relaxable) ? (error.details.relaxable as string[]) : [];
}

type ConstraintsProps = { suggestion: Suggestion; busy: boolean; onEdit: () => void; onReset: () => void };

/** What this session is currently held to; tapping any of it opens the adjust sheet. */
function Constraints({ suggestion, busy, onEdit, onReset }: ConstraintsProps) {
  const { max_minutes: maxMinutes, tags } = suggestion.applied_constraints;
  const adjusted = maxMinutes !== null || tags.length > 0;
  return (
    <div className="-mx-[20px] flex items-start gap-[8px] overflow-x-auto px-[20px] [scrollbar-width:none]">
      {maxMinutes !== null && (
        <Chip selected disabled={busy} onClick={onEdit}>
          ≤ {maxMinutes} min
        </Chip>
      )}
      <Chip disabled={busy} onClick={onEdit}>
        {suggestion.people} {suggestion.people === 1 ? "person" : "people"}
      </Chip>
      {tags.map((tag) => (
        <Chip key={tag} selected disabled={busy} onClick={onEdit}>
          {COOK_TAG_LABELS[tag]}
        </Chip>
      ))}
      {adjusted && (
        <button
          type="button"
          onClick={onReset}
          disabled={busy}
          className="shrink-0 self-center px-[4px] text-[13px] font-semibold whitespace-nowrap text-primary disabled:opacity-50"
        >
          Reset
        </button>
      )}
    </div>
  );
}

type SuggestionCardProps = {
  suggestion: Suggestion;
  busy: boolean;
  onSkip: () => void;
  onPrevious: () => void;
  onCook: () => void;
  onPreview: () => void;
};

function SuggestionCard({ suggestion, busy, onSkip, onPrevious, onCook, onPreview }: SuggestionCardProps) {
  const { recipe } = suggestion;
  const star = useStarRecipe();
  const missingEssentials = suggestion.ingredients.some((line) => line.essential && line.status === "missing");

  return (
    <article className="flex flex-col overflow-clip rounded-lg border border-border bg-surface shadow-[0px_8px_24px_0px_rgba(89,51,26,0.08)]">
      <RecipeImage recipeId={recipe.id} title={recipe.title} className="h-[180px]" />
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
          <Button className="min-w-px flex-1" onClick={missingEssentials ? onPreview : onCook} disabled={busy}>
            {missingEssentials ? "View recipe" : "Cook this"}
          </Button>
        </div>
        {!missingEssentials && (
          <button
            type="button"
            onClick={onPreview}
            disabled={busy}
            className="self-center text-[13px] font-semibold text-primary disabled:opacity-50"
          >
            View recipe
          </button>
        )}
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
