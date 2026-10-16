import { useState } from "react";

import { useUndoStockEvent } from "../api/queries";
import { Toast } from "./Toast";

type UndoToastProps = {
  /** The stock event that was just applied. */
  eventId: string;
  message: string;
  onDismiss: () => void;
};

/** "Kitchen updated · 3 items — Undo": every inventory change can be taken back at once. */
export function UndoToast({ eventId, message, onDismiss }: UndoToastProps) {
  const undo = useUndoStockEvent();
  const [undone, setUndone] = useState(false);

  if (undone) return <Toast onDismiss={onDismiss}>Undone. Your kitchen is as it was.</Toast>;

  return (
    <Toast
      onDismiss={onDismiss}
      action={{
        label: undo.isError ? "Try again" : "Undo",
        disabled: undo.isPending,
        onClick: () => undo.mutate(eventId, { onSuccess: () => setUndone(true) }),
      }}
    >
      {undo.isError ? "Could not undo that" : message}
    </Toast>
  );
}
