import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import type { Schemas } from "../api/client";
import { useBasket, useCart, useConfirmBasket, useFinishShopping } from "../api/shop";
import { BottomBar } from "../components/BottomBar";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import type { KitchenChanged } from "../lib/arrival";

const displayFont = { fontVariationSettings: '"SOFT" 0, "WONK" 1' };
type BasketItem = Schemas["BasketItem"];

function hasPurchaseUnit(item: BasketItem) {
  return Boolean(
    item.purchase_unit && item.purchase_unit_measure &&
    item.purchase_unit_size !== null && Number.isFinite(item.purchase_unit_size) && item.purchase_unit_size > 0,
  );
}

function validCount(count: number | null) {
  return count !== null && Number.isInteger(count) && count >= 1 && count <= 50;
}

/** After shopping: only what was actually bought goes into the kitchen. */
export function ConfirmPurchasePage() {
  const navigate = useNavigate();
  const basket = useBasket().data;
  const { inCart } = useCart();
  const confirm = useConfirmBasket(basket?.id);
  const finishShopping = useFinishShopping();
  // Once confirmed the basket is cleared; this screen must then leave, not bounce back to Buy.
  const [done, setDone] = useState(false);
  // Ticks made while shopping carry over; with none made, everything is assumed bought.
  const [bought, setBought] = useState<string[]>(() =>
    inCart.length > 0 ? inCart : (basket?.items.map((item) => item.id) ?? []),
  );
  const [packs, setPacks] = useState<Record<string, string>>({});

  if (done) return null;
  if (!basket) return <Navigate to="/buy" replace />;

  const toggle = (id: string) =>
    setBought((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));
  const count = basket.items.filter((item) => bought.includes(item.id)).length;
  const actualCount = (item: BasketItem) => {
    const entered = packs[item.id];
    return entered === undefined ? item.suggested_packs : entered.trim() === "" ? null : Number(entered);
  };
  const unresolved = basket.items.filter((item) => bought.includes(item.id) && (
    typeof item.countable !== "boolean" ||
    (item.countable && (!hasPurchaseUnit(item) || !validCount(actualCount(item))))
  ));

  function save() {
    if (unresolved.length > 0) return;
    confirm.mutate(
      basket!.items.map((item) => {
        const ticked = bought.includes(item.id);
        const actualPacks = actualCount(item);
        return {
          basket_item_id: item.id,
          bought: ticked,
          ...(ticked && item.countable && actualPacks !== null ? { packs: actualPacks } : {}),
        };
      }),
      {
        onSuccess: (result) => {
          const changed: KitchenChanged = {
            eventId: result.event.id,
            message: `Added to kitchen · ${count} ${count === 1 ? "item" : "items"}`,
          };
          setDone(true);
          navigate("/more/kitchen", { state: changed });
          finishShopping();
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-[16px]">
      <div className="flex items-center justify-between">
        <Link
          to="/buy"
          aria-label="Back"
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="chevron-left" />
        </Link>
        <p className="text-[16px] font-bold whitespace-nowrap">Confirm purchase</p>
        <span className="size-[40px]" />
      </div>

      <div className="flex flex-col gap-[6px]">
        <h1 className="font-display text-[26px] leading-[1.2] font-semibold" style={displayFont}>
          What’s in your bag?
        </h1>
        <p className="text-[14px] text-ink-muted">Only ticked items go into your kitchen. Check the amounts you actually bought.</p>
      </div>

      <Link to="/more/add" className="flex items-center gap-[12px] rounded-md bg-primary-soft p-[14px]">
        <span className="flex size-[40px] shrink-0 items-center justify-center rounded-[12px] bg-surface">
          <Icon name="receipt-primary" />
        </span>
        <span className="flex min-w-px flex-1 flex-col gap-px text-primary">
          <span className="text-[14px] font-bold">Scan receipt instead</span>
          <span className="text-[12px]">We’ll read it for you to review</span>
        </span>
        <Icon name="chevron-right-primary" />
      </Link>

      <ul className="flex flex-col rounded-lg border border-border bg-surface px-[14px] py-[2px]">
        {basket.items.map((item) => {
          const ticked = bought.includes(item.id);
          const itemPacks = actualCount(item);
          const unit = item.purchase_unit;
          const pluralUnit = unit === "piece" ? "pieces" : unit === "pack" ? "packs" : unit === "tray" ? "trays" : `units (${unit})`;
          const measure = item.purchase_unit_measure === "pcs"
            ? item.purchase_unit_size === 1 ? "piece" : "pieces"
            : item.purchase_unit_measure;
          return (
            <li key={item.id} className="flex flex-col gap-[8px] border-b border-border pb-[12px] last:border-b-0">
              <label className="flex min-w-px flex-1 cursor-pointer items-center gap-[12px] py-[12px]">
                <input type="checkbox" className="peer sr-only" checked={ticked} onChange={() => toggle(item.id)} />
                <span
                  className={`flex size-[22px] shrink-0 items-center justify-center rounded-[7px] peer-focus-visible:outline-2 peer-focus-visible:outline-primary ${
                    ticked ? "bg-fresh" : "border-[1.5px] border-border bg-surface"
                  }`}
                >
                  {ticked && <Icon name="check-white" />}
                </span>
                <span className="flex min-w-px flex-1 flex-col gap-[2px]">
                  <span className={`text-[14px] font-bold first-letter:uppercase ${ticked ? "" : "text-ink-subtle"}`}>
                    {item.name}
                  </span>
                  <span className="text-[12px] text-ink-muted">{ticked ? item.amount : "Didn’t buy"}</span>
                </span>
              </label>
              {ticked && item.countable && hasPurchaseUnit(item) && (
                <div className="flex flex-col gap-[6px] pl-[34px]">
                  <p className="text-[12px] text-ink-muted">Per {unit}: {item.purchase_unit_size} {measure}</p>
                  {item.suggested_packs === null ? (
                    <label className="flex flex-col gap-[4px] text-[13px] font-semibold">
                      How many {pluralUnit} did you buy?
                      <input
                        type="number"
                        min={1}
                        max={50}
                        step={1}
                        required
                        aria-label={`Actual ${unit} count for ${item.name}`}
                        value={packs[item.id] ?? ""}
                        onChange={(event) => setPacks({ ...packs, [item.id]: event.target.value })}
                        className="w-[100px] rounded-md border border-border bg-surface px-[10px] py-[8px] text-[14px]"
                      />
                      <span className="text-[12px] font-normal text-ink-muted">Enter a whole number from 1 to 50.</span>
                    </label>
                  ) : (
                    <div className="flex items-center gap-[8px]">
                      <span className="text-[13px] font-semibold">Bought</span>
                      <PackButton
                        label={`One ${unit} fewer of ${item.name}`}
                        disabled={itemPacks === null || itemPacks <= 1}
                        onClick={() => setPacks({ ...packs, [item.id]: String(itemPacks! - 1) })}
                      >
                        −
                      </PackButton>
                      <span className="text-[13px] font-bold whitespace-nowrap" aria-live="polite">
                        × {itemPacks}
                      </span>
                      <PackButton
                        label={`One ${unit} more of ${item.name}`}
                        disabled={itemPacks === null || itemPacks >= 50}
                        onClick={() => setPacks({ ...packs, [item.id]: String(itemPacks! + 1) })}
                      >
                        +
                      </PackButton>
                    </div>
                  )}
                </div>
              )}
              {ticked && typeof item.countable !== "boolean" && (
                <p className="pl-[34px] text-[12px] text-warn">Refresh your shopping list before confirming this item.</p>
              )}
              {ticked && item.countable && !hasPurchaseUnit(item) && (
                <p className="pl-[34px] text-[12px] text-warn">
                  This purchase unit needs checking. Untick this item and <Link to="/more/add" className="font-semibold underline">add it separately</Link>.
                </p>
              )}
            </li>
          );
        })}
      </ul>

      <Link
        to="/more/add"
        className="flex items-center justify-center gap-[6px] rounded-md border border-dashed border-border p-[12px]"
      >
        <Icon name="plus-muted" />
        <span className="text-[14px] font-semibold whitespace-nowrap text-ink-muted">Add something else I bought</span>
      </Link>

      {confirm.isError && (
        <p role="alert" className="text-[13px] text-danger">
          Could not add these: {confirm.error.message}
        </p>
      )}
      {unresolved.length > 0 && (
        <p role="status" className="text-[13px] text-warn">
          Check the quantities for {unresolved.map((item) => item.name).join(", ")} before adding them.
        </p>
      )}

      <BottomBar>
        <Button className="w-full" onClick={save} disabled={count === 0 || unresolved.length > 0 || confirm.isPending}>
          Add {count} {count === 1 ? "item" : "items"} to kitchen
        </Button>
      </BottomBar>
    </div>
  );
}

function PackButton({
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
      className="flex size-[28px] items-center justify-center rounded-pill border border-border bg-surface text-[15px] font-bold disabled:opacity-40"
    >
      {children}
    </button>
  );
}
