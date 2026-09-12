import { formatPercent, formatScore } from "@/lib/format";
import type { RankLabel, ScoreBreakdown } from "@/lib/types";

export const FACTOR_LABELS: Record<string, string> = {
  foot_traffic: "유동인구",
  competition_saturation: "경쟁 여유도",
  demographic_fit: "인구통계 적합도",
  building_condition: "건물 컨디션",
};

const FACTOR_ORDER = ["foot_traffic", "competition_saturation", "demographic_fit", "building_condition"];

// 원점수가 높을수록 오히려 나쁜(포화될수록 불리한) 지표 — 랭크색이 아닌 위험도색으로 표시.
export const INVERTED_FACTORS = new Set(["competition_saturation"]);

function barColor(factor: string, raw: number, rank?: RankLabel): string {
  if (INVERTED_FACTORS.has(factor)) {
    if (raw >= 70) return "bg-danger";
    if (raw >= 40) return "bg-caution";
    return "bg-brand-400";
  }
  return rank === "gold" ? "bg-brand-400" : "bg-slate-400";
}

interface ScoreBarBreakdownProps {
  breakdown: ScoreBreakdown;
  /** 기본값(진단 flow 업종 적합도 근거)을 대체할 때만 지정. 순서/라벨을 함께 바꿀 때 사용. */
  factors?: string[];
  labels?: Record<string, string>;
  /** TOP3 카드 랭크에 맞춰 바 색을 분기할 때만 지정 (1위=brand-400, 그 외=slate-400). */
  rank?: RankLabel;
}

export function ScoreBarBreakdown({ breakdown, factors = FACTOR_ORDER, labels = FACTOR_LABELS, rank }: ScoreBarBreakdownProps) {
  return (
    <div className="space-y-4">
      {factors
        .filter((factor) => `${factor}_contribution` in breakdown)
        .map((factor) => {
          const weight = breakdown[`${factor}_weight`];
          const raw = breakdown[`${factor}_raw_score`];
          const contribution = breakdown[`${factor}_contribution`];
          const maxContribution = weight * 100;
          const pct = maxContribution > 0 ? Math.min(100, (contribution / maxContribution) * 100) : 0;

          return (
            <div key={factor}>
              <div className="mb-1.5 flex flex-col gap-0.5 text-sm sm:flex-row sm:items-baseline sm:justify-between sm:gap-2">
                <span className="font-medium text-foreground">{labels[factor] ?? factor}</span>
                <span className="text-muted">
                  가중치 {formatPercent(weight * 100, 0)} · 원점수 {formatScore(raw)} · 기여도 {formatScore(contribution)}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                <div
                  className={`h-full rounded-full transition-all ${barColor(factor, raw, rank)}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
    </div>
  );
}
