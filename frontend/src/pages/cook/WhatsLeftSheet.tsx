import { useState } from "react";

import type { Schemas } from "../../api/client";
import { useConfirmCook } from "../../api/cook";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { LEVEL_LABELS } from "../../components/Level";
import { Segmented } from "../../components/Segmented";
import { Sheet } from "../../components/Sheet";
import { SheetHeader } from "../../components/SheetHeader";

type Outcome = Schemas["ConsumptionOutcome"];
type Proposed = Schemas["ProposedConsumption"];

const OUTCOMES: { value: Outcome; label: string }[] = [
  { value: "used_up", label: "All used" },
  { value: "running_low", label: "Low" },
  { value: "still_enough", label: "Enough" },
  { value: "not_used", label: "Didn’t use" },
];
const TITLE_ID = "whats-left-title";

type Answer = { count: number } | { outcome: Outcome };

function proposedAnswer(line: Proposed): Answer {
  if (line.proposed_count !== null) return { count: line.proposed_count };
  return { outcome: line.proposed_outcome ?? "still_enough" };
}

function was(item: Schemas["InventoryItem"]): string {
  if (item.count !== null) return `${item.count} ${item.unit ?? ""}`.trim();
  return LEVEL_LABELS[item.remaining_state];
}

type WhatsLeftSheetProps = {
  record: Schemas["CookRecord"];
  onDone: (result: Schemas["CookConfirmResult"]) => void;
  onClose: () => void;
};

/** After cooking: the service proposes what was used and the user corrects it. */
export function WhatsLeftSheet({ record, onDone, onClose }: WhatsLeftSheetProps) {
  const lines = record.proposed_consumption;
  const [answers, setAnswers] = useState<Answer[]>(() => lines.map(proposedAnswer));
  const confirm = useConfirmCook(record.id);

  const setAnswer = (index: number, answer: Answer) =>
    setAnswers((current) => current.map((a, i) => (i === index ? answer : a)));

  function save() {
    confirm.mutate(
      lines.map(({ item }, index) => {
        const answer = answers[index]!;
        const base = { inventory_item_id: item.id, revision: item.revision };
        return "count" in answer ? { ...base, new_count: answer.count } : { ...base, outcome: answer.outcome };
      }),
      { onSuccess: onDone },
    );
  }

  return (
    <Sheet labelledBy={TITLE_ID} onClose={onClose}>
      <SheetHeader id={TITLE_ID} title="Nice! What’s left?" onClose={onClose} />
      <p className="text-[14px] leading-[1.45] text-ink-muted">
        We’ll update your kitchen with your answers — nothing is deducted automatically.
      </p>

      {lines.map(({ item }, index) => {
        const answer = answers[index]!;
        return (
          <div key={item.id} className="flex flex-col gap-[10px] rounded-md border border-border bg-surface p-[14px]">
            <div className="flex items-center justify-between whitespace-nowrap">
              <p className="text-[15px] font-bold">{item.display_name}</p>
              <p className="text-[12px] text-ink-muted">was: {was(item)}</p>
            </div>
            {"count" in answer ? (
              <div className="flex items-center justify-between">
                <StepButton
                  label={`One fewer ${item.display_name}`}
                  disabled={answer.count <= 0}
                  onClick={() => setAnswer(index, { count: answer.count - 1 })}
                >
                  −
                </StepButton>
                <p className="text-[15px] font-bold" aria-live="polite">
                  {answer.count} {item.unit} left
                </p>
                <StepButton
                  label={`One more ${item.display_name}`}
                  onClick={() => setAnswer(index, { count: answer.count + 1 })}
                >
                  +
                </StepButton>
              </div>
            ) : (
              <Segmented
                label={`How much ${item.display_name} is left?`}
                options={OUTCOMES}
                value={answer.outcome}
                onChange={(outcome) => setAnswer(index, { outcome })}
              />
            )}
          </div>
        );
      })}

      <p className="text-[12px] leading-[1.45] text-ink-muted">Pantry staples are not tracked per meal.</p>
      {confirm.isError && (
        <p role="alert" className="text-[13px] text-danger">
          Could not update your kitchen: {confirm.error.message}
        </p>
      )}

      <Button className="w-full shrink-0" onClick={save} disabled={confirm.isPending}>
        Update kitchen
      </Button>
      <div className="flex items-center justify-center gap-[6px]">
        <Icon name="undo-sm" />
        <p className="text-[12px] font-semibold whitespace-nowrap text-ink-muted">
          You can undo this from the Kitchen history
        </p>
      </div>
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
