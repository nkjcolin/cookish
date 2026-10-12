export function PlaceholderPage({ title }: { title: string }) {
  return (
    <section>
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="mt-2 text-neutral-500">Not built yet.</p>
    </section>
  );
}
