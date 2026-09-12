import { formatScore } from "@/lib/format";

export function levelOf(score: number): { label: string; color: string } {
  if (score >= 75) return { label: "양호", color: "var(--safe)" };
  if (score >= 50) return { label: "보통", color: "var(--caution)" };
  return { label: "취약", color: "var(--danger)" };
}

export function ScoreMeter({ label, score }: { label: string; score: number }) {
  const level = levelOf(score);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-muted">{label}</span>
        <span className="text-xs font-medium" style={{ color: level.color }}>
          {level.label}
        </span>
      </div>
      <div className="mb-1.5 flex items-baseline gap-1">
        <span className="text-2xl font-bold tracking-tight">{formatScore(score)}</span>
        <span className="text-sm text-muted">/100</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, backgroundColor: level.color }} />
      </div>
    </div>
  );
}
