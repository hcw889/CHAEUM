import type { ScoreBreakdown } from "@/lib/types";

const FACTOR_LABELS: Record<string, string> = {
  foot_traffic: "유동인구",
  competition_saturation: "경쟁 여유도",
  demographic_fit: "인구통계 적합도",
  building_condition: "건물 컨디션",
};

const FACTOR_ORDER = ["foot_traffic", "competition_saturation", "demographic_fit", "building_condition"];

export function ScoreBarBreakdown({ breakdown }: { breakdown: ScoreBreakdown }) {
  return (
    <div className="space-y-4">
      {FACTOR_ORDER.filter((factor) => `${factor}_contribution` in breakdown).map((factor) => {
        const weight = breakdown[`${factor}_weight`];
        const raw = breakdown[`${factor}_raw_score`];
        const contribution = breakdown[`${factor}_contribution`];
        const maxContribution = weight * 100;
        const pct = maxContribution > 0 ? Math.min(100, (contribution / maxContribution) * 100) : 0;

        return (
          <div key={factor}>
            <div className="mb-1.5 flex flex-col gap-0.5 text-sm sm:flex-row sm:items-baseline sm:justify-between sm:gap-2">
              <span className="font-medium text-foreground">{FACTOR_LABELS[factor] ?? factor}</span>
              <span className="text-muted">
                가중치 {Math.round(weight * 100)}% · 원점수 {raw} · 기여도 {contribution}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-border">
              <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
