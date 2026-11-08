import { useState } from "react";

import { ApiError, type Schemas } from "../../api/client";
import { useDeleteInventoryItem, useUpdateInventoryItem } from "../../api/queries";
import { Button } from "../../components/Button";
import { readCount } from "../../components/CountInput";
import { Icon } from "../../components/Icon";
import { LEVEL_LABELS } from "../../components/Level";
import { Sheet } from "../../components/Sheet";

type Batch = Schemas["InventoryItem"];
type State = Schemas["RemainingState"];
const TITLE_ID = "stock-correction-title";

export function StockCorrectionSheet({ batch, action, onClose, onSaved }: {
  batch: Batch;
  action: "edit" | "remove";
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const update = useUpdateInventoryItem();
  const remove = useDeleteInventoryItem();
  const [text, setText] = useState(batch.count === null ? "" : String(batch.count));
  const [unit, setUnit] = useState(batch.unit ?? "");
  const [state, setState] = useState<State>(batch.remaining_state === "out" ? "unknown" : batch.remaining_state);
  const quantity = readCount(text);
  const pending = update.isPending || remove.isPending;
  const error = update.error ?? remove.error;

  function saved(message: string) {
    onSaved(message);
    onClose();
  }

  function save() {
    if (quantity === null || !unit.trim()) return;
    update.mutate({
      itemId: batch.id,
      body: {
        revision: batch.revision,
        count: quantity,
        unit: unit.trim(),
        remaining_state: quantity === 0 ? "out" : batch.countable ? "enough" : state,
      },
    }, { onSuccess: () => saved("Quantity updated. Undo the new history entry to reverse this correction.") });
  }

  return (
    <Sheet labelledBy={TITLE_ID} onClose={() => { if (!pending) onClose(); }}>
      <div className="flex items-center justify-between gap-[12px]">
        <h2 id={TITLE_ID} className="font-display text-[24px] font-semibold">
          {action === "remove" ? "Remove item" : "Edit quantity remaining"}
        </h2>
        <button type="button" aria-label="Close" disabled={pending} onClick={onClose}
          className="flex size-[36px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface">
          <Icon name="x" />
        </button>
      </div>
      <p className="text-[15px] font-bold">{batch.display_name}</p>
      {action === "remove" ? (
        <p className="text-[14px] text-ink-muted">
          Remove this batch from your kitchen? Earlier history stays unchanged.
          You can undo the new removal entry to restore it.
        </p>
      ) : (
        <>
          <p className="text-[13px] text-ink-muted">
            Enter what remains in this batch now. This records a new correction and does not change the original submission.
          </p>
          <label className="flex flex-col gap-[6px] text-[13px] font-semibold">
            Quantity remaining
            <input type="number" min={0} step="any" value={text} autoFocus
              onChange={(event) => setText(event.target.value)}
              className="rounded-md border border-border bg-surface px-[12px] py-[10px] text-[15px]" />
          </label>
          <label className="flex flex-col gap-[6px] text-[13px] font-semibold">
            Unit
            <input value={unit} maxLength={16} placeholder="For example: pcs, g or kg"
              onChange={(event) => setUnit(event.target.value)}
              className="rounded-md border border-border bg-surface px-[12px] py-[10px] text-[15px]" />
          </label>
          <p className="text-[12px] text-ink-muted">
            Enter 0 if none is left. Changing the unit does not convert the amount.
          </p>
          {!batch.countable && quantity !== 0 && (
            <label className="flex flex-col gap-[6px] text-[13px] font-semibold">
              How much is left?
              <select value={state} onChange={(event) => setState(event.target.value as State)}
                className="rounded-md border border-border bg-surface px-[12px] py-[10px] text-[14px]">
                {(["enough", "low", "unknown"] as const).map((value) =>
                  <option key={value} value={value}>{LEVEL_LABELS[value]}</option>)}
              </select>
            </label>
          )}
        </>
      )}
      {error && (
        <p role="alert" className="text-[13px] text-danger">
          {error instanceof ApiError && error.code === "STALE_REVISION"
            ? "This batch changed elsewhere. Close this and open it again to load the current amount."
            : error.message}
        </p>
      )}
      <div className="flex gap-[10px]">
        <Button variant="secondary" onClick={onClose} disabled={pending} className="min-w-px flex-1">Cancel</Button>
        {action === "remove" ? (
          <Button className="min-w-px flex-1" disabled={pending}
            onClick={() => remove.mutate({ itemId: batch.id, revision: batch.revision }, {
              onSuccess: () => saved("Item removed. Undo the new removal entry to restore it."),
            })}>Remove item</Button>
        ) : (
          <Button className="min-w-px flex-1" disabled={pending || quantity === null || !unit.trim()}
            onClick={save}>Save quantity</Button>
        )}
      </div>
    </Sheet>
  );
}
