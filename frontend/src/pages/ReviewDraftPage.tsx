import { useCallback, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAddInventoryItems } from "../api/queries";
import { BottomBar } from "../components/BottomBar";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { PhotoPreviewDialog } from "../components/PhotoPreviewDialog";
import { StorageTag } from "../components/Tag";
import { forgetImagePreview, getImagePreview } from "../lib/imagePreview";
import { draftLabel, isUncertain, toInventoryItems, type ReviewState } from "./add/draft";

/** Rows shown before the rest are folded behind "+ N more". */
const VISIBLE_ROWS = 6;

export function ReviewDraftPage() {
  const review = useLocation().state as ReviewState | null;
  if (!review) return <Navigate to="/more/add" replace />;
  return <ReviewDraft review={review} />;
}

function ReviewDraft({ review }: { review: ReviewState }) {
  const navigate = useNavigate();
  const addItems = useAddInventoryItems();
  const { items, source } = review;
  const [included, setIncluded] = useState(() => items.map(() => true));
  const [answered, setAnswered] = useState(() => items.map((item) => !isUncertain(item)));
  const [showAll, setShowAll] = useState(false);
  const [previewUrl] = useState(() => getImagePreview(review.imageJobId));
  const [previewOpen, setPreviewOpen] = useState(false);
  const closePreview = useCallback(() => setPreviewOpen(false), []);

  const kind = source === "receipt" ? "receipt" : "photo";
  const question = answered.findIndex((done) => !done);
  const chosen = items.filter((_, index) => included[index]);
  const rows = showAll ? items : items.slice(0, VISIBLE_ROWS);

  function setAt(list: boolean[], index: number, value: boolean): boolean[] {
    return list.map((current, i) => (i === index ? value : current));
  }

  function answer(index: number, keep: boolean) {
    setAnswered((list) => setAt(list, index, true));
    setIncluded((list) => setAt(list, index, keep));
  }

  function save() {
    addItems.mutate({ source, items: toInventoryItems(chosen) }, { onSuccess: () => {
      if (review.imageJobId) forgetImagePreview(review.imageJobId);
      navigate("/more/kitchen");
    } });
  }

  return (
    <div className="flex flex-col gap-[16px]">
      <div className="flex items-center justify-between">
        <Link
          to="/more/add"
          aria-label="Back"
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="chevron-left" />
        </Link>
        <h1 className="text-[16px] font-bold whitespace-nowrap">Review {kind}</h1>
        <span className="size-[40px]" />
      </div>

      <button
        type="button"
        aria-label={kind === "receipt" ? "Your receipt" : "Your photo"}
        aria-haspopup="dialog"
        aria-expanded={previewOpen}
        disabled={!previewUrl}
        onClick={() => setPreviewOpen(true)}
        className="flex items-center gap-[12px] rounded-md border border-border bg-surface p-[12px] text-left"
      >
        <span className="flex h-[60px] w-[48px] shrink-0 items-center justify-center rounded-[8px] bg-surface-sunken">
          <Icon name={kind === "receipt" ? "receipt" : "camera"} />
        </span>
        <span className="flex min-w-px flex-1 flex-col gap-[2px]">
          <span className="text-[14px] font-bold">{kind === "receipt" ? "Your receipt" : "Your photo"}</span>
          <span className="text-[12px] text-ink-muted">
            {previewUrl ? "Tap to enlarge. Items are added only when you confirm."
              : "Preview unavailable after a reload or returning to a saved job. Your extracted items are still available."}
          </span>
        </span>
      </button>

      {previewOpen && previewUrl && <PhotoPreviewDialog src={previewUrl} onClose={closePreview} />}

      {question !== -1 && (
        <div className="flex flex-col gap-[10px] rounded-md bg-warn-soft p-[14px]">
          <div className="flex items-center gap-[8px]">
            <Icon name="help" />
            <p className="min-w-px flex-1 text-[14px] font-bold text-warn">
              Is “{items[question]!.raw_text ?? items[question]!.display_name}” {items[question]!.display_name.toLowerCase()}?
            </p>
          </div>
          <div className="flex gap-[8px]">
            <button
              type="button"
              onClick={() => answer(question, true)}
              className="min-w-px flex-1 rounded-pill bg-dark py-[8px] text-[13px] font-bold whitespace-nowrap text-surface"
            >
              Yes, {items[question]!.display_name.toLowerCase()}
            </button>
            <button
              type="button"
              onClick={() => answer(question, false)}
              className="min-w-px flex-1 rounded-pill border border-border bg-surface py-[8px] text-[13px] font-bold whitespace-nowrap"
            >
              Something else
            </button>
          </div>
        </div>
      )}

      <p className="text-[15px] font-bold">
        {items.length} food {items.length === 1 ? "item" : "items"} found
      </p>

      {items.length > 0 && (
        <ul className="flex flex-col rounded-lg border border-border bg-surface px-[14px] py-[2px]">
          {rows.map((item, index) => (
            <li key={`${item.display_name}-${index}`} className="border-b border-border last:border-b-0">
              <label className="flex cursor-pointer items-center gap-[12px] py-[11px]">
                <input
                  type="checkbox"
                  className="peer sr-only"
                  checked={included[index]}
                  onChange={(event) => setIncluded((list) => setAt(list, index, event.target.checked))}
                />
                <span
                  className={`flex size-[22px] shrink-0 items-center justify-center rounded-[7px] peer-focus-visible:outline-2 peer-focus-visible:outline-primary ${
                    included[index] ? "bg-fresh" : "border-[1.5px] border-border bg-surface"
                  }`}
                >
                  {included[index] && <Icon name="check-white" />}
                </span>
                <span className="flex min-w-px flex-1 flex-col gap-px">
                  <span className="text-[14px] font-bold">{draftLabel(item)}</span>
                  {item.raw_text && <span className="text-[11px] text-ink-subtle">“{item.raw_text}”</span>}
                </span>
                {item.storage && <StorageTag storage={item.storage} />}
              </label>
            </li>
          ))}
        </ul>
      )}

      {!showAll && items.length > VISIBLE_ROWS && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="self-start text-[13px] font-semibold whitespace-nowrap text-primary"
        >
          + {items.length - VISIBLE_ROWS} more
        </button>
      )}

      {addItems.isError && (
        <p role="alert" className="text-[13px] text-danger">
          Could not add these: {addItems.error.message}
        </p>
      )}

      <BottomBar>
        <Button className="w-full" onClick={save} disabled={chosen.length === 0 || addItems.isPending}>
          Add {chosen.length} {chosen.length === 1 ? "item" : "items"} to kitchen
        </Button>
      </BottomBar>
    </div>
  );
}
