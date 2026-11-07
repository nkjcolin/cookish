import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, type Schemas } from "../api/client";
import { useAdjustBasket, useBasket, useCart } from "../api/shop";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { Icon } from "../components/Icon";
import { Tag } from "../components/Tag";
import { AdjustBasketSheet } from "./buy/AdjustBasketSheet";
import { SHOP_TAG_LABELS, groupByAisle } from "./buy/view";
import { TASTE_TAG_LABELS, difficultyLabel } from "./cook/view";

type Basket = Schemas["Basket"];
type ShopTag = Schemas["ShopTag"];
type View = "list" | "meals";

const displayFont = { fontVariationSettings: '"SOFT" 0, "WONK" 1' };

export function BuyPage() {
  const navigate = useNavigate();
  const session = useBasket();
  const basket = session.data;
  const adjust = useAdjustBasket(basket?.session_id);
  const { inCart, toggle } = useCart();
  const [view, setView] = useState<View>("list");
  const [adjusting, setAdjusting] = useState(false);

  // Every meal Shop could plan can already be cooked from the kitchen: nothing to buy.
  const allStocked = session.error instanceof ApiError && session.error.details.all_stocked === true;
  const failure = allStocked ? adjust.error : (session.error ?? adjust.error);
  const ticked = basket ? basket.items.filter((item) => inCart.includes(item.id)).length : 0;

  return (
    <div className="flex flex-col gap-[12px] pb-[78px]">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-[2px] whitespace-nowrap">
          <p className="text-[13px] font-semibold text-ink-muted">On the way home{basket && ` · for ${basket.people}`}</p>
          <h1 className="font-display text-[28px] leading-[1.2] font-semibold" style={displayFont}>
            What to buy
          </h1>
        </div>
        <button
          type="button"
          aria-label="Adjust basket"
          disabled={!basket}
          onClick={() => setAdjusting(true)}
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="sliders-ink" />
        </button>
      </div>

      {session.isPending && <p className="text-[14px] text-ink-muted">Putting a basket together…</p>}
      {failure && (
        <p role="alert" className="text-[13px] text-danger">
          {failure.message}
        </p>
      )}
      {allStocked && (
        <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-surface p-[16px]">
          <p className="text-[15px] font-bold">Nothing to buy right now</p>
          <p className="text-[14px] text-ink-muted">
            Your kitchen already has what your usual meals need. Cook can suggest one to make tonight.
          </p>
          <Button className="w-full" onClick={() => navigate("/cook")}>
            See what to cook
          </Button>
        </div>
      )}

      {basket && (
        <>
          <div className="rounded-lg bg-dark px-[18px] py-[14px]">
            <p className="font-display text-[26px] leading-[1.15] font-semibold text-surface" style={displayFont}>
              {basket.items.length} {basket.items.length === 1 ? "item" : "items"} · {basket.meals}{" "}
              {basket.meals === 1 ? "meal" : "meals"}
            </p>
          </div>

          {basket.applied_tags.length > 0 && (
            <div className="flex flex-wrap content-start items-start gap-[8px]">
              {basket.applied_tags.map((tag) => (
                <Chip key={tag} selected onClick={() => setAdjusting(true)}>
                  {SHOP_TAG_LABELS[tag]}
                </Chip>
              ))}
            </div>
          )}

          <div className="-mx-[20px] flex items-start gap-[8px] overflow-x-auto px-[20px] [scrollbar-width:none]">
            {(Object.keys(SHOP_TAG_LABELS) as ShopTag[])
              .filter((tag) => !basket.applied_tags.includes(tag))
              .map((tag) => (
                <Chip key={tag} suggested onClick={() => adjust.mutate({ tags: [tag] })}>
                  {SHOP_TAG_LABELS[tag]}
                </Chip>
              ))}
          </div>

          <div role="tablist" className="flex gap-[4px] rounded-md bg-surface-sunken p-[4px]">
            <ViewTab active={view === "list"} onClick={() => setView("list")}>
              Shopping list ({basket.items.length})
            </ViewTab>
            <ViewTab active={view === "meals"} onClick={() => setView("meals")}>
              Meals ({basket.planned_meals.length})
            </ViewTab>
          </div>

          {view === "list" ? (
            <ShoppingList basket={basket} inCart={inCart} onToggle={toggle} />
          ) : (
            <Meals basket={basket} />
          )}

          <div className="fixed inset-x-0 bottom-[84px] z-10 mx-auto flex max-w-[390px] items-center gap-[12px] bg-bg px-[20px] py-[12px]">
            <div className="flex shrink-0 flex-col whitespace-nowrap">
              <p className="text-[16px] font-bold">
                {ticked} of {basket.items.length}
              </p>
              <p className="text-[12px] text-ink-muted">in your cart</p>
            </div>
            <Button className="min-w-px flex-1" onClick={() => navigate("/buy/confirm")}>
              I’m done shopping
            </Button>
          </div>

          {adjusting && (
            <AdjustBasketSheet
              basket={basket}
              onApply={(body) => adjust.mutate(body)}
              onClose={() => setAdjusting(false)}
            />
          )}
        </>
      )}
    </div>
  );
}

function ViewTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`flex min-w-px flex-1 items-center justify-center rounded-[10px] py-[9px] text-[14px] whitespace-nowrap ${
        active ? "bg-surface font-bold text-ink shadow-[0px_1px_3px_0px_rgba(0,0,0,0.08)]" : "font-medium text-ink-muted"
      }`}
    >
      {children}
    </button>
  );
}

type ShoppingListProps = { basket: Basket; inCart: string[]; onToggle: (itemId: string) => void };

function ShoppingList({ basket, inCart, onToggle }: ShoppingListProps) {
  return groupByAisle(basket.items).map((aisle) => (
    <section key={aisle.title} className="flex flex-col gap-[12px]">
      <h2 className="text-[12px] font-bold tracking-[0.72px] text-ink-muted uppercase">{aisle.title}</h2>
      <ul className="flex flex-col rounded-lg border border-border bg-surface px-[14px] py-[2px]">
        {aisle.items.map((item) => {
          const ticked = inCart.includes(item.id);
          return (
            <li key={item.id} className="border-b border-border last:border-b-0">
              <label className="flex cursor-pointer items-center gap-[12px] py-[12px]">
                <input type="checkbox" className="peer sr-only" checked={ticked} onChange={() => onToggle(item.id)} />
                <span
                  className={`flex size-[22px] shrink-0 items-center justify-center rounded-[7px] peer-focus-visible:outline-2 peer-focus-visible:outline-primary ${
                    ticked ? "bg-fresh" : "border-[1.5px] border-border bg-surface"
                  }`}
                >
                  {ticked && <Icon name="check-white" />}
                </span>
                <span className="flex min-w-px flex-1 flex-col gap-[2px]">
                  <span className={`text-[14px] font-bold first-letter:uppercase ${ticked ? "text-ink-subtle line-through" : ""}`}>
                    {item.name}
                  </span>
                  <span className="text-[12px] text-ink-muted">{item.amount}</span>
                </span>
                {item.needs_check && <Tag tone="warn">Check at home</Tag>}
              </label>
            </li>
          );
        })}
      </ul>
    </section>
  ));
}

/** Example meals the basket covers. They explain the list; nothing is scheduled. */
function Meals({ basket }: { basket: Basket }) {
  return (
    <ul className="flex flex-col gap-[10px]">
      {basket.planned_meals.map((meal, index) => (
        <li key={meal.id} className="flex items-center gap-[12px] rounded-md border border-border bg-surface p-[14px]">
          <span className="flex size-[26px] shrink-0 items-center justify-center rounded-pill bg-primary-soft text-[13px] font-bold text-primary">
            {index + 1}
          </span>
          <div className="flex min-w-px flex-1 flex-col gap-[6px]">
            <p className="text-[15px] font-bold">{meal.title}</p>
            <div className="flex flex-wrap items-start gap-[6px]">
              <Tag>
                <Icon name="clock-sm" />
                {meal.total_minutes} min
              </Tag>
              <Tag>{difficultyLabel(meal.difficulty)}</Tag>
              {meal.taste_tags.map((tag) => (
                <Tag key={tag}>{TASTE_TAG_LABELS[tag]}</Tag>
              ))}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
