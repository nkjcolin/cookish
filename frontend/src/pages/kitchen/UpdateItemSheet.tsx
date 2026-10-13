import { useState } from "react";

import { ApiError, type Schemas } from "../../api/client";
import { useUpdateInventoryItem } from "../../api/queries";
import { Button } from "../../components/Button";
import { Icon } from "../../components/Icon";
import { Level } from "../../components/Level";
import { Sheet } from "../../components/Sheet";
import { freshnessNote, lastConfirmedText } from "./view";

type Batch = Schemas["InventoryItem"];
type RemainingState = Schemas["RemainingState"];
type Storage = Schemas["Storage"];

// "Out" is not offered here: that is what the "Used it up" button records.
const STATE_OPTIONS: RemainingState[] = ["enough", "low", "unknown"];
const STORAGE_OPTIONS: { value: Storage; label: string }[] = [
  { value: "fridge", label: "Fridge" },
  { value: "freezer", label: "Freezer" },
  { value: "pantry", label: "Pantry" },
];
const TITLE_ID = "update-item-title";

type UpdateItemSheetProps = {
  name: string;
  batch: Batch;
  /** How many batches of this ingredient exist; the sheet edits the one to use first. */
  batchCount: number;
  onClose: () => void;
};

export function UpdateItemSheet({ name, batch, batchCount, onClose }: UpdateItemSheetProps) {
  const tracksCount = batch.countable && batch.count !== null;
  const [state, setState] = useState<RemainingState>(batch.remaining_state);
  const [count, setCount] = useState(batch.count ?? 0);
  const [storage, setStorage] = useState<Storage>(batch.storage);
  const update = useUpdateInventoryItem();
  const today = new Date();
  const note = freshnessNote(batch, today);

  function submit(body: Omit<Schemas["InventoryItemUpdate"], "revision">) {
    update.mutate({ itemId: batch.id, body: { revision: batch.revision, ...body } }, { onSuccess: onClose });
  }

  function save() {
    // Saving also confirms the item, so the amount is sent even when it did not change.
    submit({
      ...(tracksCount ? { count } : { remaining_state: state }),
      ...(storage !== batch.storage ? { storage } : {}),
    });
  }

  function usedUp() {
    submit(tracksCount ? { count: 0, remaining_state: "out" } : { remaining_state: "out" });
  }

  return (
    <Sheet labelledBy={TITLE_ID} onClose={onClose}>
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-[2px]">
          <h2
            id={TITLE_ID}
            className="font-display text-[24px] font-semibold"
            style={{ fontVariationSettings: '"SOFT" 0, "WONK" 1' }}
          >
            {name}
          </h2>
          <p className="text-[12px] text-ink-muted">
            {lastConfirmedText(batch, today)}
            {batchCount > 1 && ` · the batch to use first, of ${batchCount}`}
          </p>
        </div>
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="flex size-[36px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="x" />
        </button>
      </div>

      {tracksCount ? (
        <>
          <p className="text-[15px] font-bold">How many are left?</p>
          <div className="flex items-center justify-between rounded-md border border-border px-[14px] py-[12px]">
            <StepButton label="One fewer" onClick={() => setCount((c) => Math.max(0, c - 1))} disabled={count <= 0}>
              −
            </StepButton>
            <p className="text-[15px] font-bold" aria-live="polite">
              {count} {batch.unit}
            </p>
            <StepButton label="One more" onClick={() => setCount((c) => c + 1)}>
              +
            </StepButton>
          </div>
        </>
      ) : (
        <>
          <p className="text-[15px] font-bold">How much is left?</p>
          <div role="radiogroup" aria-label="How much is left?" className="flex flex-col gap-[8px]">
            {STATE_OPTIONS.map((option) => {
              const selected = option === state;
              return (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setState(option)}
                  className={`flex items-center gap-[12px] rounded-md px-[14px] py-[12px] ${
                    selected ? "border-[1.5px] border-primary bg-primary-soft" : "border border-border bg-surface"
                  }`}
                >
                  <span
                    className={`size-[20px] shrink-0 rounded-pill bg-surface ${
                      selected ? "border-6 border-primary" : "border-[1.5px] border-border"
                    }`}
                  />
                  <Level state={option} />
                </button>
              );
            })}
          </div>
        </>
      )}

      <p className="text-[15px] font-bold">Stored in</p>
      <div role="radiogroup" aria-label="Stored in" className="flex gap-[6px]">
        {STORAGE_OPTIONS.map((option) => {
          const selected = option.value === storage;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => setStorage(option.value)}
              className={`flex min-w-px flex-1 items-center justify-center rounded-pill py-[9px] text-[13px] font-bold whitespace-nowrap ${
                selected ? "bg-dark text-surface" : "border border-border bg-surface text-ink"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {note && (
        <div className="flex items-start gap-[10px] rounded-md bg-surface-sunken px-[14px] py-[12px]">
          <Icon name="clock" />
          <p className="min-w-px flex-1 text-[13px] leading-[1.45] text-ink-muted">{note}</p>
        </div>
      )}

      {update.isError && (
        <p role="alert" className="text-[13px] text-danger">
          {update.error instanceof ApiError && update.error.code === "STALE_REVISION"
            ? "This item was changed somewhere else. Close this and try again."
            : `Could not save: ${update.error.message}`}
        </p>
      )}

      <div className="flex gap-[10px]">
        <Button variant="secondary" className="min-w-px flex-1" onClick={usedUp} disabled={update.isPending}>
          Used it up
        </Button>
        <Button className="min-w-px flex-1" onClick={save} disabled={update.isPending}>
          Save
        </Button>
      </div>
    </Sheet>
  );
}

function StepButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="flex size-[36px] items-center justify-center rounded-pill border border-border bg-surface text-[18px] font-bold disabled:opacity-40"
    >
      {children}
    </button>
  );
}
