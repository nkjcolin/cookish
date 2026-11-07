import { useState } from "react";

import { ApiError, type Schemas } from "../../api/client";
import { useInventoryIngredient, useUpdateInventoryItem } from "../../api/queries";
import { Button } from "../../components/Button";
import { CountInput, readCount } from "../../components/CountInput";
import { Icon } from "../../components/Icon";
import { Level } from "../../components/Level";
import { Segmented } from "../../components/Segmented";
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
  const tracksCount = batch.countable;
  const [state, setState] = useState<RemainingState>(batch.remaining_state);
  const [enteredCount, setEnteredCount] = useState<string | null>(null);
  const ingredient = useInventoryIngredient(batch);
  const unit = ingredient.data?.default_unit;
  const countText = enteredCount ?? (unit === batch.unit && batch.count !== null ? String(batch.count) : "");
  const count = readCount(countText);
  const [storage, setStorage] = useState<Storage>(batch.storage);
  const update = useUpdateInventoryItem();
  const today = new Date();
  const note = freshnessNote(batch, today);

  function submit(body: Omit<Schemas["InventoryItemUpdate"], "revision">) {
    update.mutate({ itemId: batch.id, body: { revision: batch.revision, ...body } }, { onSuccess: onClose });
  }

  function save() {
    if (tracksCount && (!unit || count === null)) return;
    // Saving also confirms the item, so the amount is sent even when it did not change.
    submit({
      ...(tracksCount ? { count, unit, remaining_state: count === 0 ? "out" : "enough" } : { remaining_state: state }),
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
          {unit ? (
            <CountInput name={name} unit={unit} category={batch.category} value={countText} onChange={setEnteredCount} />
          ) : ingredient.isPending ? (
            <p className="text-[13px] text-ink-muted">Checking the amount unit…</p>
          ) : (
            <div role="alert" className="flex flex-col gap-[6px] text-[13px] text-danger">
              <p>Could not find the unit for this ingredient. Try again before entering an amount.</p>
              <button type="button" className="self-start font-semibold underline" onClick={() => void ingredient.refetch()}>Try again</button>
            </div>
          )}
          {unit && batch.count !== null && batch.unit !== unit && (
            <p className="text-[12px] text-ink-muted">The saved amount uses {batch.unit ?? "an unknown unit"}. Enter the amount in {unit}; we cannot convert it automatically.</p>
          )}
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
      <Segmented label="Stored in" options={STORAGE_OPTIONS} value={storage} onChange={setStorage} />

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
        <Button className="min-w-px flex-1" onClick={save} disabled={update.isPending || (tracksCount && (!unit || count === null))}>
          Save
        </Button>
      </div>
    </Sheet>
  );
}
