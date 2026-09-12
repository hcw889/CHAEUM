"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { RankMedal } from "@/components/RankMedal";
import { ScoreBarBreakdown } from "@/components/ScoreBarBreakdown";
import { SkeletonCardGrid } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { formatCurrency, formatScore } from "@/lib/format";
import type { BusinessFitCandidate } from "@/lib/types";

const RANK_BORDER: Record<string, string> = {
  gold: "border-gold",
  silver: "border-silver",
  bronze: "border-bronze",
};

export default function RankingPage() {
  const { id } = useParams<{ id: string }>();
  const [candidates, setCandidates] = useState<BusinessFitCandidate[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getBusinessFit(id)
      .then((data) => {
        setCandidates(data);
        setSelected(data[0]?.type ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "불러오기 실패"));
  }, [id]);

  const top3 = useMemo(() => candidates?.filter((c) => c.rank) ?? [], [candidates]);
  const rest = useMemo(() => candidates?.filter((c) => !c.rank) ?? [], [candidates]);
  const selectedCandidate = candidates?.find((c) => c.type === selected) ?? null;

  if (error) return <main className="mx-auto max-w-3xl px-6 py-10 text-danger">{error}</main>;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />

      <h1 className="mb-1 text-2xl font-bold tracking-tight">업종 적합도 순위</h1>
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
                  <p className="text-3xl font-bold tracking-tight">{formatScore(c.fit_score)}</p>
                  <p className="mb-3 text-xs text-muted">적합도 점수</p>
                  <p className="text-sm text-muted">예상 임대료 월 {formatCurrency(c.estimated_rent)}</p>
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
              <h2 className="mb-1 font-semibold">{selectedCandidate.type} 스코어 근거</h2>
              <p className="mb-5 text-sm text-muted">가중합 방식으로 계산된 세부 항목별 기여도입니다.</p>
              <ScoreBarBreakdown breakdown={selectedCandidate.score_breakdown} />
            </Card>
          )}

          <Link
            href={`/dashboard/${id}`}
            className="mt-8 inline-flex w-full items-center justify-center rounded-2xl bg-brand-gradient py-3 font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand sm:w-auto sm:px-8"
          >
            리스크 대시보드 보기 →
          </Link>
        </>
      )}
    </main>
  );
}
