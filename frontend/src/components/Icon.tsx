import cart from "../assets/icons/cart.svg";
import cartActive from "../assets/icons/cart-active.svg";
import chevronLeft from "../assets/icons/chevron-left.svg";
import grid from "../assets/icons/grid.svg";
import gridActive from "../assets/icons/grid-active.svg";
import pot from "../assets/icons/pot.svg";
import potActive from "../assets/icons/pot-active.svg";
import refresh from "../assets/icons/refresh.svg";
import search from "../assets/icons/search.svg";

// Each entry places an exported SVG inside its icon box exactly as the design does:
// `inset` positions the artwork, `bleed` leaves room for the stroke around it.
const icons = {
  "chevron-left": { src: chevronLeft, size: 20, inset: "25% 37.5%", bleed: "-9.5% -19%" },
  search: { src: search, size: 20, inset: "16.67% 12.5% 12.5% 16.67%", bleed: "-6.71%" },
  refresh: { src: refresh, size: 20, inset: "12.5%", bleed: "-6.67%" },
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
