export function DataFreshness({ month }: { month: string }) {
  return (
    <div className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1 text-xs text-muted">
      <span aria-hidden>●</span>
      데이터 기준월: {month.replace("-", ".")}
    </div>
  );
}
