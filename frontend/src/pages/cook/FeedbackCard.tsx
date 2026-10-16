import type { Schemas } from "../../api/client";
import { useRateCook } from "../../api/cook";
import { Chip } from "../../components/Chip";
import { Icon } from "../../components/Icon";

type Rating = Schemas["Rating"];

type FeedbackCardProps = {
  recordId: string;
  title: string;
  onDone: () => void;
};

/** Asked once, after the meal is cooked: like, maybe or dislike. Skipping is fine. */
export function FeedbackCard({ recordId, title, onDone }: FeedbackCardProps) {
  const rate = useRateCook();
  const send = (rating: Rating) => rate.mutate({ recordId, rating }, { onSuccess: onDone });
  const thumb = "flex size-[40px] shrink-0 items-center justify-center rounded-pill disabled:opacity-50";

  return (
    <section className="flex flex-col gap-[12px] rounded-lg border border-border bg-surface p-[16px]">
      <div className="flex items-center gap-[12px]">
        <div className="flex min-w-px flex-1 flex-col gap-[2px]">
          <h2 className="text-[15px] font-bold">How was the {title.toLowerCase()}?</h2>
          <p className="text-[12px] text-ink-muted">Helps tomorrow’s pick — one tap is enough.</p>
        </div>
        <button
          type="button"
          aria-label="Didn’t like it"
          disabled={rate.isPending}
          onClick={() => send("dislike")}
          className={`${thumb} bg-surface-sunken`}
        >
          <Icon name="thumb-down" />
        </button>
        <button
          type="button"
          aria-label="Liked it"
          disabled={rate.isPending}
          onClick={() => send("like")}
          className={`${thumb} bg-fresh-soft`}
        >
          <Icon name="thumb-up" />
        </button>
      </div>
      <div className="flex flex-wrap content-start items-start gap-[8px]">
        <Chip onClick={() => send("maybe")}>It was okay</Chip>
        <Chip onClick={onDone}>Skip</Chip>
      </div>
      {rate.isError && (
        <p role="alert" className="text-[13px] text-danger">
          Could not save that: {rate.error.message}
        </p>
      )}
    </section>
  );
}
