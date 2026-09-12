"use client";

import { AnalysisError, useAnalysis } from "./AnalysisData";

import { useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { RadialGauge } from "@/components/RadialGauge";
import { RankMedal } from "@/components/RankMedal";
import { FACTOR_LABELS, INVERTED_FACTORS, ScoreBarBreakdown } from "@/components/ScoreBarBreakdown";
import { SkeletonCardGrid } from "@/components/Skeleton";
import { Tag } from "@/components/Tag";
import { formatCurrency, formatScore } from "@/lib/format";
import type { ScoreBreakdown } from "@/lib/types";

const RANK_BORDER: Record<string, string> = {
  gold: "border-gold",
  silver: "border-silver",
  bronze: "border-bronze",
};

/** score_breakdown 원점수를 "높을수록 좋음" 기준으로 정규화해 상위 2개 강점 라벨을 뽑는다. */
function topStrengthTags(breakdown: ScoreBreakdown, count = 2): string[] {
  return Object.keys(FACTOR_LABELS)
    .map((factor) => {
      const raw = breakdown[`${factor}_raw_score`] ?? 0;
      const goodness = INVERTED_FACTORS.has(factor) ? 100 - raw : raw;
      return { factor, goodness };
    })
    .sort((a, b) => b.goodness - a.goodness)
    .slice(0, count)
    .map(({ factor }) => FACTOR_LABELS[factor]);
}

export default function RankingSection() {
  const { candidates: { data: candidates, error, retry } } = useAnalysis();
  const [picked, setSelected] = useState<string | null>(null);
  const selected = picked ?? candidates?.[0]?.type ?? null;

  const top3 = useMemo(() => candidates?.filter((c) => c.rank) ?? [], [candidates]);
  const rest = useMemo(() => candidates?.filter((c) => !c.rank) ?? [], [candidates]);
  const selectedCandidate = candidates?.find((c) => c.type === selected) ?? null;

  if (error) return <AnalysisError message={error} onRetry={retry} />;

  return (
    <div>

      <p className="mb-6 text-sm text-muted">유동인구·경쟁포화도·인구통계·건물 컨디션을 종합한 적합도 점수입니다.</p>

      {!candidates ? (
        <SkeletonCardGrid count={3} />
      ) : (
        <>
          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {top3.map((c) => (
              <button key={c.type} onClick={() => setSelected(c.type)} className="text-left">
                <Card
                  className={`h-full border-2 transition-all ${
                    selected === c.type ? RANK_BORDER[c.rank ?? ""] : "border-border"
                  } ${c.rank === "gold" ? "sm:scale-105" : ""}`}
                >
                  <div className="mb-3 flex items-center gap-2.5">
                    <RankMedal rank={c.rank} />
                    <span className="text-lg font-semibold">{c.type}</span>
                  </div>
                  <div className="mb-3 flex justify-center">
                    <RadialGauge value={c.fit_score} label="적합도 점수" />
                  </div>
                  <p className="mb-3 text-center text-sm text-muted">예상 임대료 월 {formatCurrency(c.estimated_rent)}</p>
                  <div className="flex flex-wrap justify-center gap-1.5">
                    {topStrengthTags(c.score_breakdown).map((label) => (
                      <Tag key={label}>{label} 강점</Tag>
                    ))}
                  </div>
                </Card>
              </button>
            ))}
          </div>

          {rest.length > 0 && (
            <div className="mb-8 space-y-2">
              {rest.map((c) => (
                <button
                  key={c.type}
                  onClick={() => setSelected(c.type)}
                  className={`flex w-full items-center justify-between rounded-md border px-4 py-3 text-left transition-colors ${
                    selected === c.type ? "border-accent bg-accent-soft" : "border-border bg-surface"
                  }`}
                >
                  <span className="font-medium">{c.type}</span>
                  <span className="text-sm text-muted">{formatScore(c.fit_score)}점</span>
                </button>
              ))}
            </div>
          )}

          {selectedCandidate && (
            <Card>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Score Breakdown</p>
              <h3 className="mb-1 text-lg font-bold">{selectedCandidate.type} 스코어 근거</h3>
              <p className="mb-5 text-sm text-muted">가중합 방식으로 계산된 세부 항목별 기여도입니다.</p>
              <ScoreBarBreakdown breakdown={selectedCandidate.score_breakdown} rank={selectedCandidate.rank} />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
