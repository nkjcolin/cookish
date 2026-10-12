import { Link } from "react-router-dom";

// Placeholder until screen D1 is built from the design.
export function MorePage() {
  return (
    <section className="flex flex-col gap-[14px]">
      <h1 className="text-[16px] font-bold">More</h1>
      <Link to="/more/kitchen" className="rounded-lg border border-border bg-surface p-[14px] text-[14px] font-bold">
        My Kitchen
      </Link>
    </section>
  );
}
