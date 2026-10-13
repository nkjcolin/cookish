import type { Schemas } from "../../api/client";
import type { CookConstraints } from "../../api/cook";
import { useMe } from "../../api/queries";
import { Icon, type IconName } from "../../components/Icon";
import { ALLERGEN_LABELS, DIET_LABELS } from "../../lib/labels";
import { COOK_TAG_LABELS, RELAX_MINUTES } from "./view";

type CookTag = Schemas["CookTag"];

type NoMatchProps = {
  constraints: CookConstraints;
  /** Soft conditions the service says could be relaxed (NO_RESULT details). */
  relaxable: string[];
  busy: boolean;
  onAllowMoreTime: (minutes: number) => void;
  onDropTime: () => void;
  onDropTag: (tag: CookTag) => void;
  onStartOver: () => void;
};

const displayFont = { fontVariationSettings: '"SOFT" 0, "WONK" 1' };

/**
 * Nothing satisfies the session's constraints. The user chooses what to relax; hard
 * rules are never offered.
 */
export function NoMatch(props: NoMatchProps) {
  const { constraints, relaxable, busy } = props;
  const me = useMe();
  const prefs = me.data?.preferences;
  const hardRules = prefs ? [...prefs.diets.map((d) => DIET_LABELS[d]), ...prefs.allergens.map((a) => ALLERGEN_LABELS[a])] : [];
  const canRelaxTime = constraints.maxMinutes !== null && relaxable.includes("max_minutes");
  const canRelaxTags = relaxable.includes("tags");
  const removable = "flex shrink-0 items-center gap-[8px] rounded-pill bg-dark px-[14px] py-[8px] text-[13px] font-semibold whitespace-nowrap text-surface disabled:opacity-50";

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="-mx-[20px] flex items-start gap-[8px] overflow-x-auto px-[20px] [scrollbar-width:none]">
        {constraints.maxMinutes !== null && (
          <button type="button" disabled={busy} onClick={props.onDropTime} className={removable}>
            ≤ {constraints.maxMinutes} min <span aria-hidden>✕</span>
            <span className="sr-only">Remove</span>
          </button>
        )}
        {constraints.tags.map((tag) => (
          <button key={tag} type="button" disabled={busy} onClick={() => props.onDropTag(tag)} className={removable}>
            {COOK_TAG_LABELS[tag]} <span aria-hidden>✕</span>
            <span className="sr-only">Remove</span>
          </button>
        ))}
      </div>

      <div className="flex flex-col items-center gap-[10px] rounded-lg border border-border bg-surface px-[20px] py-[24px]">
        <span className="flex size-[64px] items-center justify-center rounded-pill bg-surface-sunken">
          <Icon name="search-lg" />
        </span>
        <h2 className="text-center font-display text-[22px] font-semibold" style={displayFont}>
          Nothing fits all of that
        </h2>
        <p className="text-center text-[14px] leading-[1.5] text-ink-muted">
          No recipe matches everything you asked for with what’s in your kitchen.
        </p>
      </div>

      <h2 className="text-[17px] font-bold whitespace-nowrap">Relax one thing?</h2>
      <div className="flex flex-col gap-[10px]">
        {canRelaxTime && (
          <RelaxRow
            icon="clock-info"
            tint="bg-info-soft"
            title={`Allow up to ${constraints.maxMinutes! + RELAX_MINUTES} min`}
            detail="Keeps everything else"
            disabled={busy}
            onClick={() => props.onAllowMoreTime(constraints.maxMinutes! + RELAX_MINUTES)}
          />
        )}
        {canRelaxTags &&
          constraints.tags.map((tag) => (
            <RelaxRow
              key={tag}
              icon="pot-warn"
              tint="bg-warn-soft"
              title={`Drop “${COOK_TAG_LABELS[tag].toLowerCase()}”`}
              detail="Keeps everything else"
              disabled={busy}
              onClick={() => props.onDropTag(tag)}
            />
          ))}
        <RelaxRow
          icon="pot-warn"
          tint="bg-warn-soft"
          title="Start over"
          detail="Clears every adjustment"
          disabled={busy}
          onClick={props.onStartOver}
        />
      </div>

      {hardRules.length > 0 && (
        <div className="flex items-center gap-[8px]">
          <Icon name="lock-sm" />
          <p className="min-w-px flex-1 text-[12px] font-semibold text-ink-muted">
            {hardRules.join(" and ")} {hardRules.length === 1 ? "is" : "are"} never relaxed.
          </p>
        </div>
      )}
    </div>
  );
}

type RelaxRowProps = {
  icon: IconName;
  tint: string;
  title: string;
  detail: string;
  disabled: boolean;
  onClick: () => void;
};

function RelaxRow({ icon, tint, title, detail, disabled, onClick }: RelaxRowProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="flex w-full items-center gap-[12px] rounded-md border border-border bg-surface p-[14px] text-left disabled:opacity-50"
    >
      <span className={`flex size-[40px] shrink-0 items-center justify-center rounded-[12px] ${tint}`}>
        <Icon name={icon} />
      </span>
      <span className="flex min-w-px flex-1 flex-col gap-px">
        <span className="text-[15px] font-bold">{title}</span>
        <span className="text-[12px] text-ink-muted">{detail}</span>
      </span>
      <Icon name="chevron-right-sm" />
    </button>
  );
}
