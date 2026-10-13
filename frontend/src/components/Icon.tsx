import cart from "../assets/icons/cart.svg";
import arrowUp from "../assets/icons/arrow-up.svg";
import box from "../assets/icons/box.svg";
import camera from "../assets/icons/camera.svg";
import cartActive from "../assets/icons/cart-active.svg";
import checkFreshSm from "../assets/icons/check-fresh-sm.svg";
import checkGreen from "../assets/icons/check-green.svg";
import checkToast from "../assets/icons/check-toast.svg";
import checkWhite from "../assets/icons/check-white.svg";
import chevronLeft from "../assets/icons/chevron-left.svg";
import chevronRight from "../assets/icons/chevron-right.svg";
import chevronRightPrimary from "../assets/icons/chevron-right-primary.svg";
import chevronRightSm from "../assets/icons/chevron-right-sm.svg";
import clock from "../assets/icons/clock.svg";
import clockInfo from "../assets/icons/clock-info.svg";
import clockSm from "../assets/icons/clock-sm.svg";
import fridge from "../assets/icons/fridge.svg";
import grid from "../assets/icons/grid.svg";
import help from "../assets/icons/help.svg";
import helpSm from "../assets/icons/help-sm.svg";
import leaf from "../assets/icons/leaf.svg";
import leafHero from "../assets/icons/leaf-hero.svg";
import lock from "../assets/icons/lock.svg";
import lockSm from "../assets/icons/lock-sm.svg";
import mic from "../assets/icons/mic.svg";
import pencil from "../assets/icons/pencil.svg";
import plus from "../assets/icons/plus.svg";
import plusMuted from "../assets/icons/plus-muted.svg";
import gridActive from "../assets/icons/grid-active.svg";
import pot from "../assets/icons/pot.svg";
import potActive from "../assets/icons/pot-active.svg";
import potHero from "../assets/icons/pot-hero.svg";
import potInk from "../assets/icons/pot-ink.svg";
import potWarn from "../assets/icons/pot-warn.svg";
import receipt from "../assets/icons/receipt.svg";
import receiptPrimary from "../assets/icons/receipt-primary.svg";
import refresh from "../assets/icons/refresh.svg";
import refreshSm from "../assets/icons/refresh-sm.svg";
import search from "../assets/icons/search.svg";
import searchLg from "../assets/icons/search-lg.svg";
import sliders from "../assets/icons/sliders.svg";
import slidersInk from "../assets/icons/sliders-ink.svg";
import sparkleSm from "../assets/icons/sparkle-sm.svg";
import star from "../assets/icons/star.svg";
import starLg from "../assets/icons/star-lg.svg";
import thumbDown from "../assets/icons/thumb-down.svg";
import thumbUp from "../assets/icons/thumb-up.svg";
import undo from "../assets/icons/undo.svg";
import undoSm from "../assets/icons/undo-sm.svg";
import users from "../assets/icons/users.svg";
import usersSm from "../assets/icons/users-sm.svg";
import x from "../assets/icons/x.svg";

// Each entry places an exported SVG inside its icon box exactly as the design does:
// `inset` positions the artwork, `bleed` leaves room for the stroke around it.
const icons = {
  "chevron-left": { src: chevronLeft, size: 20, inset: "25% 37.5%", bleed: "-9.5% -19%" },
  search: { src: search, size: 20, inset: "16.67% 12.5% 12.5% 16.67%", bleed: "-6.71%" },
  refresh: { src: refresh, size: 20, inset: "12.5%", bleed: "-6.67%" },
  x: { src: x, size: 18, inset: "25%", bleed: "-10.56%" },
  clock: { src: clock, size: 16, inset: "12.5%", bleed: "-9.17%" },
  plus: { src: plus, size: 24, inset: "20.83%", bleed: "-8.57%" },
  fridge: { src: fridge, size: 24, inset: "8.33% 20.83%", bleed: "-4.75% -6.79%" },
  sliders: { src: sliders, size: 18, inset: "8.33% 12.5%", bleed: "-6.33% -7.04%" },
  "chevron-right": { src: chevronRight, size: 18, inset: "25% 37.5%", bleed: "-10.56% -21.11%" },
  undo: { src: undo, size: 18, inset: "29.17% 12.5%", bleed: "-12.67% -7.04%" },
  receipt: { src: receipt, size: 22, inset: "8.33% 16.67%", bleed: "-5.18% -6.48%" },
  camera: { src: camera, size: 22, inset: "16.67% 8.33%", bleed: "-6.48% -5.18%" },
  mic: { src: mic, size: 22, inset: "8.33% 20.83%", bleed: "-5.18% -7.4%" },
  help: { src: help, size: 16, inset: "12.5%", bleed: "-9.17%" },
  "check-white": { src: checkWhite, size: 14, inset: "25% 16.67% 29.17% 16.67%", bleed: "-23.38% -16.07%" },
  lock: { src: lock, size: 16, inset: "12.5% 16.67%", bleed: "-9.17% -10.31%" },
  users: { src: users, size: 18, inset: "12.5% 8.33%", bleed: "-7.04% -6.33%" },
  "pot-ink": { src: potInk, size: 18, inset: "8.33% 8.33% 12.5% 8.33%", bleed: "-6.67% -6.33%" },
  "chevron-right-sm": { src: chevronRightSm, size: 16, inset: "25% 37.5%", bleed: "-11.87% -23.75%" },
  "sliders-ink": { src: slidersInk, size: 20, inset: "8.33% 12.5%", bleed: "-5.7% -6.33%" },
  "leaf-hero": { src: leafHero, size: 61, inset: "8.33% 12.5% 12.5% 8.33%", bleed: "-1.66%" },
  star: { src: star, size: 18, inset: "11.67% 11.67% 15.42% 11.67%", bleed: "-7.24% -6.88%" },
  "clock-sm": { src: clockSm, size: 13, inset: "12.5%", bleed: "-11.28%" },
  "check-green": { src: checkGreen, size: 14, inset: "25% 16.67% 29.17% 16.67%", bleed: "-20.26% -13.93%" },
  "help-sm": { src: helpSm, size: 14, inset: "12.5%", bleed: "-10.48%" },
  "arrow-up": { src: arrowUp, size: 18, inset: "20.83%", bleed: "-9.05%" },
  "lock-sm": { src: lockSm, size: 14, inset: "12.5% 16.67%", bleed: "-10.48% -11.79%" },
  "sparkle-sm": { src: sparkleSm, size: 14, inset: "8.38%", bleed: "-8.58%" },
  leaf: { src: leaf, size: 20, inset: "8.33% 12.5% 12.5% 8.33%", bleed: "-6%" },
  box: { src: box, size: 20, inset: "8.34% 12.5% 8.33% 12.5%", bleed: "-5.7% -6.33%" },
  "refresh-sm": { src: refreshSm, size: 13, inset: "12.5%", bleed: "-11.28%" },
  "users-sm": { src: usersSm, size: 16, inset: "12.5% 8.33%", bleed: "-7.92% -7.12% -7.92% -7.13%" },
  "check-fresh-sm": { src: checkFreshSm, size: 13, inset: "25% 16.67% 29.17% 16.67%", bleed: "-18.46% -12.69%" },
  "pot-hero": { src: potHero, size: 84, inset: "8.33% 8.33% 12.5% 8.33%", bleed: "-0.98% -0.93%" },
  "star-lg": { src: starLg, size: 20, inset: "11.67% 11.67% 15.42% 11.67%", bleed: "-6.51% -6.2%" },
  "undo-sm": { src: undoSm, size: 14, inset: "29.17% 12.5%", bleed: "-18.86% -10.48%" },
  "thumb-down": { src: thumbDown, size: 18, inset: "8.33% 8.33% 8.33% 9.04%", bleed: "-6.67% -6.72%" },
  "thumb-up": { src: thumbUp, size: 18, inset: "8.33% 9.04% 8.33% 8.33%", bleed: "-6.67% -6.72%" },
  "check-toast": { src: checkToast, size: 18, inset: "25% 16.67% 29.17% 16.67%", bleed: "-14.55% -10%" },
  "search-lg": { src: searchLg, size: 28, inset: "16.67% 12.5% 12.5% 16.67%", bleed: "-4.54%" },
  "clock-info": { src: clockInfo, size: 20, inset: "12.5%", bleed: "-6.33%" },
  "pot-warn": { src: potWarn, size: 20, inset: "8.33% 8.33% 12.5% 8.33%", bleed: "-6% -5.7%" },
  "receipt-primary": { src: receiptPrimary, size: 20, inset: "8.33% 16.67%", bleed: "-5.7% -7.12% -5.7% -7.13%" },
  "chevron-right-primary": { src: chevronRightPrimary, size: 18, inset: "25% 37.5%", bleed: "-10.56% -21.11%" },
  "plus-muted": { src: plusMuted, size: 16, inset: "20.83%", bleed: "-11.79%" },
  pencil: { src: pencil, size: 16, inset: "8.29% 8.2% 8.33% 8.33%", bleed: "-7.12% -7.11%" },
  pot: { src: pot, size: 22, inset: "8.33% 8.33% 12.5% 8.33%", bleed: "-5.17% -4.91%" },
  "pot-active": { src: potActive, size: 22, inset: "8.33% 8.33% 12.5% 8.33%", bleed: "-6.03% -5.73%" },
  cart: { src: cart, size: 22, inset: "8.54% 7.96% 8.33% 8.54%", bleed: "-4.92% -4.9%" },
  "cart-active": { src: cartActive, size: 22, inset: "8.54% 7.96% 8.33% 8.54%", bleed: "-5.74% -5.72%" },
  grid: { src: grid, size: 22, inset: "12.5%", bleed: "-5.45%" },
  "grid-active": { src: gridActive, size: 22, inset: "12.5%", bleed: "-6.36%" },
} as const;

export type IconName = keyof typeof icons;

export function Icon({ name }: { name: IconName }) {
  const { src, size, inset, bleed } = icons[name];
  return (
    <span className="relative block shrink-0 overflow-clip" style={{ width: size, height: size }} aria-hidden>
      <span className="absolute" style={{ inset }}>
        <span className="absolute" style={{ inset: bleed }}>
          <img alt="" className="block size-full max-w-none" src={src} />
        </span>
      </span>
    </span>
  );
}
