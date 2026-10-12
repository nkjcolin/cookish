export function PlaceholderPage({ title }: { title: string }) {
  return (
    <section>
      <h1 className="text-[16px] font-bold">{title}</h1>
      <p className="mt-[8px] text-[14px] text-ink-muted">Not built yet.</p>
    </section>
  );
}
