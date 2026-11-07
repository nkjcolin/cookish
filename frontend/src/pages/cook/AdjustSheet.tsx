import { useState, type FormEvent } from "react";

import type { Schemas } from "../../api/client";
import { useInterpret } from "../../api/cook";
import { useMe } from "../../api/queries";
import { Button } from "../../components/Button";
import { Chip } from "../../components/Chip";
import { Icon } from "../../components/Icon";
import { Sheet } from "../../components/Sheet";
import { SheetHeader } from "../../components/SheetHeader";
import { Tag } from "../../components/Tag";
import { ALLERGEN_LABELS, DIET_LABELS, EQUIPMENT_LABELS, summarise } from "../../lib/labels";
import { COOK_TAG_LABELS, availableNudges, describeAdjust } from "./view";

type CookTag = Schemas["CookTag"];
type CookAdjust = Schemas["CookAdjust"];

const TIME_LIMITS = [15, 30, 45, 60];
const TITLE_ID = "adjust-title";
const sectionTitle = "text-[12px] font-bold tracking-[0.72px] text-ink-muted uppercase";

type AdjustSheetProps = {
  suggestion: Schemas["Suggestion"];
  meal: string;
  onApply: (adjust: CookAdjust) => void;
  onClose: () => void;
};

export function AdjustSheet({ suggestion, meal, onApply, onClose }: AdjustSheetProps) {
  const applied = suggestion.applied_constraints;
  const me = useMe();
  const interpret = useInterpret();
  const [people, setPeople] = useState(suggestion.people);
  const [maxMinutes, setMaxMinutes] = useState(applied.max_minutes);
  const [tags, setTags] = useState<CookTag[]>([]);
  const [request, setRequest] = useState("");
  const [understood, setUnderstood] = useState<string | null>(null);
  const nudges = availableNudges(suggestion);

  const prefs = me.data?.preferences;
  const always = prefs
    ? [
        ...prefs.diets.map((d) => DIET_LABELS[d]),
        ...prefs.allergens.map((a) => ALLERGEN_LABELS[a]),
        ...(prefs.equipment.length > 0 ? [summarise(prefs.equipment.map((e) => EQUIPMENT_LABELS[e]), 99)] : []),
      ]
    : [];

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = request.trim();
    if (!text) return;
    try {
      const { adjust } = await interpret.mutateAsync(text);
      // A typed request may combine nudges; the service validates the combination.
      setTags(adjust.tags ?? []);
      if (adjust.max_minutes != null) setMaxMinutes(adjust.max_minutes);
      if (adjust.people != null) setPeople(adjust.people);
      setUnderstood(describeAdjust(adjust));
    } catch {
      // The mutation error is shown below; leave the pending adjustment unchanged.
    }
  }

  function apply() {
    // Adjustments accumulate on the server, so only what changed here is sent.
    const adjust: CookAdjust = { tags };
    if (people !== suggestion.people) adjust.people = people;
    if (maxMinutes !== null && maxMinutes !== applied.max_minutes) adjust.max_minutes = maxMinutes;
    const changed = adjust.tags!.length > 0 || adjust.people !== undefined || adjust.max_minutes !== undefined;
    if (changed) onApply(adjust);
    onClose();
  }

  return (
    <Sheet labelledBy={TITLE_ID} onClose={onClose}>
      <SheetHeader id={TITLE_ID} title={`Adjust ${meal}`} onClose={onClose} />

      {always.length > 0 && (
        <div className="flex flex-col gap-[8px] rounded-md bg-surface-sunken px-[14px] py-[12px]">
          <div className="flex items-center gap-[6px]">
            <Icon name="lock-sm" />
            <p className="text-[12px] font-bold whitespace-nowrap text-ink-muted">Always applied</p>
          </div>
          <p className="text-[13px] font-semibold">{always.join(" · ")}</p>
        </div>
      )}

      <div className="flex flex-col gap-[8px]">
        <p className={sectionTitle}>Cooking for</p>
        <div className="flex items-center gap-[16px]">
          <StepButton label="One fewer" disabled={interpret.isPending || people <= 1} onClick={() => setPeople(people - 1)}>
            −
          </StepButton>
          <p className="text-[15px] font-bold" aria-live="polite">
            {people} {people === 1 ? "person" : "people"}
          </p>
          <StepButton label="One more" disabled={interpret.isPending || people >= 12} onClick={() => setPeople(people + 1)}>
            +
          </StepButton>
        </div>
      </div>

      <div className="flex flex-col gap-[8px]">
        <p className={sectionTitle}>Time</p>
        <div className="flex flex-wrap content-start items-start gap-[8px]">
          {TIME_LIMITS.map((minutes) => (
            <Chip
              key={minutes}
              selected={maxMinutes === minutes}
              disabled={interpret.isPending || (applied.max_minutes !== null && minutes > applied.max_minutes)}
              onClick={() => setMaxMinutes(minutes)}
            >
              ≤ {minutes} min
            </Chip>
          ))}
        </div>
        {applied.max_minutes !== null && (
          <p className="text-[12px] text-ink-muted">Current limit: {applied.max_minutes} min. For more time, change your cooking limit in Preferences.</p>
        )}
      </div>

      {applied.tags.length > 0 && (
        <div className="flex flex-col gap-[8px]">
          <p className={sectionTitle}>Already applied</p>
          <div className="flex flex-wrap gap-[8px]">
            {applied.tags.map((tag) => <Tag key={tag}>{COOK_TAG_LABELS[tag]}</Tag>)}
          </div>
          <p className="text-[12px] text-ink-muted">Use Reset on the suggestion to remove these.</p>
        </div>
      )}

      <section aria-label="Choose a nudge" className="flex flex-col gap-[8px]">
        <p className={sectionTitle}>Nudge</p>
        <p className="text-[12px] text-ink-muted">Choose one change to try next.</p>
        <div className="flex flex-wrap content-start items-start gap-[8px]">
          {nudges.map((tag) => (
            <Chip
              key={tag}
              selected={tags.includes(tag)}
              disabled={interpret.isPending}
              onClick={() => {
                setTags(tags.length === 1 && tags[0] === tag ? [] : [tag]);
                setUnderstood(null);
              }}
            >
              {COOK_TAG_LABELS[tag]}
            </Chip>
          ))}
        </div>
        {nudges.length === 0 && (
          <p className="text-[13px] text-ink-muted">No nudges fit this recipe right now. You can still adjust the people or time.</p>
        )}
      </section>

      <form
        onSubmit={(event) => void ask(event)}
        className="flex items-center gap-[8px] rounded-pill border-[1.5px] border-primary bg-surface py-[6px] pr-[6px] pl-[16px]"
      >
        <input
          value={request}
          onChange={(event) => setRequest(event.target.value)}
          aria-label="Describe what you feel like"
          placeholder="e.g. “less oil”"
          className="min-w-px flex-1 bg-transparent text-[14px] font-medium outline-none placeholder:text-ink-subtle"
        />
        <button
          type="submit"
          aria-label="Send"
          disabled={interpret.isPending || request.trim() === ""}
          className="flex size-[36px] shrink-0 items-center justify-center rounded-pill bg-primary disabled:opacity-50"
        >
          <Icon name="arrow-up" />
        </button>
      </form>

      {understood && (
        <div className="flex items-center gap-[8px]">
          <Icon name="sparkle-sm" />
          <p className="min-w-px flex-1 text-[12px] font-semibold text-primary">Understood as: {understood}</p>
        </div>
      )}
      {interpret.isError && (
        <p role="alert" className="text-[13px] text-danger">
          Could not read that: {interpret.error.message}. Use the chips above instead.
        </p>
      )}

      <Button className="w-full shrink-0" onClick={apply} disabled={interpret.isPending}>
        Update suggestion
      </Button>
    </Sheet>
  );
}

function StepButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="flex size-[36px] items-center justify-center rounded-pill border border-border bg-surface text-[18px] font-bold disabled:opacity-40"
    >
      {children}
    </button>
  );
}
