import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import type { Schemas } from "../api/client";
import { useAddInventoryItems, useParsedItems, useParseImage } from "../api/queries";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { Icon, type IconName } from "../components/Icon";
import { Level } from "../components/Level";
import { StorageTag, Tag } from "../components/Tag";
import { compressImage } from "../lib/image";
import { listen, speechIsSupported } from "../lib/speech";
import { draftLabel, toInventoryItems, type ReviewState } from "./add/draft";

type DraftItem = Schemas["DraftItem"];
type ItemSource = Schemas["ItemSource"];

const QUICK_ADD = ["Eggs", "Rice", "Onion", "Garlic", "Tofu", "Chicken thigh"];
const TYPING_PAUSE_MS = 600;

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function AddIngredientsPage() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [spoken, setSpoken] = useState(false);
  const [listening, setListening] = useState(false);
  const stopListening = useRef<() => void>(() => {});
  const receiptInput = useRef<HTMLInputElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);

  const parsed = useParsedItems(useDebounced(text.trim(), TYPING_PAUSE_MS), spoken ? "voice" : "typed");
  const parseImage = useParseImage();
  const addItems = useAddInventoryItems();

  useEffect(() => () => stopListening.current(), []);

  const draft: DraftItem[] = text.trim().length > 1 ? (parsed.data?.items ?? []) : [];
  const source: ItemSource = spoken ? "voice" : "manual";
  const reading = parseImage.isPending || (text.trim().length > 1 && parsed.isFetching);
  const failure = parseImage.error ?? parsed.error ?? addItems.error;

  function type(value: string) {
    setText(value);
    setSpoken(false);
  }

  async function readImage(file: File | undefined, kind: Schemas["ImageKind"]) {
    if (!file) return;
    const result = await parseImage.mutateAsync({
      kind,
      media_type: "image/jpeg",
      image_base64: await compressImage(file),
    });
    const review: ReviewState = { items: result.items, source: kind };
    navigate("/more/add/review", { state: review });
  }

  function toggleListening() {
    if (listening) return stopListening.current();
    setSpoken(true);
    setListening(true);
    stopListening.current = listen({ onTranscript: setText, onEnd: () => setListening(false) });
  }

  function save() {
    addItems.mutate({ source, items: toInventoryItems(draft) }, { onSuccess: () => navigate("/more/kitchen") });
  }

  return (
    <div className="flex flex-col gap-[16px]">
      <div className="flex items-center justify-between">
        <Link
          to="/more"
          aria-label="Back"
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="chevron-left" />
        </Link>
        <h1 className="text-[16px] font-bold whitespace-nowrap">Add Ingredients</h1>
        <span className="size-[40px]" />
      </div>

      <div className="flex flex-col gap-[10px]">
        <MethodRow
          icon="receipt"
          tint="bg-primary-soft"
          title="Scan a receipt"
          detail="Best right after shopping"
          recommended
          onClick={() => receiptInput.current?.click()}
        />
        <MethodRow
          icon="camera"
          tint="bg-info-soft"
          title="Photo of groceries or fridge"
          detail="We draft a list — you confirm"
          onClick={() => photoInput.current?.click()}
        />
        {speechIsSupported() && (
          <MethodRow
            icon="mic"
            tint="bg-fresh-soft"
            title={listening ? "Listening… tap to stop" : "Say it"}
            detail="“Bought eggs and a cabbage”"
            onClick={toggleListening}
          />
        )}
        <input
          ref={receiptInput}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          aria-label="Receipt photo"
          onChange={(event) => void readImage(event.target.files?.[0], "receipt")}
        />
        <input
          ref={photoInput}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          aria-label="Photo of groceries or fridge"
          onChange={(event) => void readImage(event.target.files?.[0], "photo")}
        />
      </div>

      <section className="flex flex-col gap-[10px] rounded-lg border border-border bg-surface p-[16px]">
        <label htmlFor="typed-items" className="text-[15px] font-bold">
          Or just type it
        </label>
        <div className="flex items-center gap-[8px] rounded-md border-[1.5px] border-primary bg-bg px-[14px] py-[12px]">
          <Icon name="pencil" />
          <textarea
            id="typed-items"
            rows={2}
            value={text}
            onChange={(event) => type(event.target.value)}
            placeholder="half a cabbage, 6 eggs, some spring onion"
            className="min-w-px flex-1 resize-none bg-transparent text-[14px] font-medium outline-none placeholder:text-ink-subtle"
          />
        </div>

        {reading && <p className="text-[12px] text-ink-muted">Reading…</p>}
        {failure && (
          <p role="alert" className="text-[13px] text-danger">
            {failure.message}. You can still type items one by one.
          </p>
        )}

        {draft.length > 0 && (
          <>
            <p className="text-[11px] font-bold text-ink-muted uppercase">We’ll add</p>
            <ul className="flex flex-col gap-[8px]">
              {draft.map((item, index) => (
                <li key={`${item.display_name}-${index}`} className="flex items-center gap-[10px]">
                  <p className="min-w-px flex-1 text-[14px] font-semibold">{draftLabel(item)}</p>
                  {item.count === null && <Level state="enough" />}
                  {item.storage && <StorageTag storage={item.storage} />}
                </li>
              ))}
            </ul>
            <Button className="w-full" onClick={save} disabled={addItems.isPending}>
              Add {draft.length} {draft.length === 1 ? "item" : "items"}
            </Button>
          </>
        )}
      </section>

      <section className="flex flex-col gap-[8px]">
        <h2 className="text-[15px] font-bold">Quick add</h2>
        <div className="flex flex-wrap content-start items-start gap-[8px]">
          {QUICK_ADD.map((name) => (
            <Chip key={name} onClick={() => type(text.trim() ? `${text.trim()}, ${name.toLowerCase()}` : name.toLowerCase())}>
              + {name}
            </Chip>
          ))}
        </div>
      </section>
    </div>
  );
}


type MethodRowProps = {
  icon: IconName;
  tint: string;
  title: string;
  detail: string;
  recommended?: boolean;
  onClick: () => void;
};

function MethodRow({ icon, tint, title, detail, recommended = false, onClick }: MethodRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-[12px] rounded-md bg-surface p-[14px] text-left ${
        recommended ? "border-[1.5px] border-primary" : "border border-border"
      }`}
    >
      <span className={`flex size-[44px] shrink-0 items-center justify-center rounded-[12px] ${tint}`}>
        <Icon name={icon} />
      </span>
      <span className="flex min-w-px flex-1 flex-col gap-[2px]">
        <span className="text-[15px] font-bold">{title}</span>
        <span className="text-[12px] text-ink-muted">{detail}</span>
      </span>
      {recommended ? <Tag tone="primary">Recommended</Tag> : <Icon name="chevron-right" />}
    </button>
  );
}
