import cart from "../assets/icons/cart.svg";
import camera from "../assets/icons/camera.svg";
import cartActive from "../assets/icons/cart-active.svg";
import checkWhite from "../assets/icons/check-white.svg";
import chevronLeft from "../assets/icons/chevron-left.svg";
import chevronRight from "../assets/icons/chevron-right.svg";
import chevronRightSm from "../assets/icons/chevron-right-sm.svg";
import clock from "../assets/icons/clock.svg";
import fridge from "../assets/icons/fridge.svg";
import grid from "../assets/icons/grid.svg";
import help from "../assets/icons/help.svg";
import lock from "../assets/icons/lock.svg";
import mic from "../assets/icons/mic.svg";
import pencil from "../assets/icons/pencil.svg";
import plus from "../assets/icons/plus.svg";
import gridActive from "../assets/icons/grid-active.svg";
import pot from "../assets/icons/pot.svg";
import potActive from "../assets/icons/pot-active.svg";
import potInk from "../assets/icons/pot-ink.svg";
import receipt from "../assets/icons/receipt.svg";
import refresh from "../assets/icons/refresh.svg";
import search from "../assets/icons/search.svg";
import sliders from "../assets/icons/sliders.svg";
import undo from "../assets/icons/undo.svg";
import users from "../assets/icons/users.svg";
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
