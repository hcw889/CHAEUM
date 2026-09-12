"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { InsightBox } from "@/components/InsightBox";
import { SkeletonCardGrid } from "@/components/Skeleton";
import { VerticalStepper } from "@/components/VerticalStepper";
import { api } from "@/lib/api";
import { formatCurrency, formatScore } from "@/lib/format";
import type { DashboardMetrics } from "@/lib/types";

function buildDashboardInsight(metrics: DashboardMetrics): string {
  const saturationNote =
    metrics.avg_competition_saturation >= 60
      ? "경쟁포화도가 높은 편이니 차별화된 컨셉으로 포지셔닝하는 전략이 필요합니다."
      : "경쟁포화도가 낮은 편이라 카테고리 대표 브랜드로 선점하기 좋은 상권입니다.";
  const trafficNote =
    metrics.avg_foot_traffic >= 60
      ? "유동인구 지수도 높아 오프라인 워크인 비중을 늘리는 전략이 유효합니다."
      : "유동인구 지수는 다소 낮아 온라인·배달 채널 비중을 함께 고려해야 합니다.";
  return `${saturationNote} ${trafficNote} 경쟁이 가장 치열한 업종은 '${metrics.top_competition_type}'입니다.`;
}

export default function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getDashboard(id)
      .then(setMetrics)
      .catch((err) => setError(err instanceof Error ? err.message : "불러오기 실패"));
  }, [id]);

  if (error) return <main className="mx-auto max-w-3xl px-6 py-10 text-danger">{error}</main>;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />

      <h1 className="mb-1 text-2xl font-bold tracking-tight">리스크 대시보드</h1>
      <p className="mb-6 text-sm text-muted">인근 상권의 포화도·임대료·유동인구 추정치입니다. (mock 데이터)</p>

      {!metrics ? (
        <SkeletonCardGrid count={3} />
      ) : (
        <div className="flex flex-col gap-6 sm:flex-row">
          <VerticalStepper buildingId={id} />

          <div className="min-w-0 flex-1">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Card>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Competition</p>
                <p className="mb-1 text-sm text-muted">인근 동일업종 평균 경쟁포화도</p>
                <p className="text-3xl font-bold tracking-tight">{formatScore(metrics.avg_competition_saturation)}</p>
                <p className="text-xs text-muted">/ 100</p>
              </Card>
              <Card>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Rent</p>
                <p className="mb-1 text-sm text-muted">평균 추정 임대료</p>
                <p className="text-3xl font-bold tracking-tight">{formatScore(metrics.avg_estimated_rent / 10_000)}</p>
                <p className="text-xs text-muted">만원 / 월 ({formatCurrency(metrics.avg_estimated_rent)})</p>
              </Card>
              <Card>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Foot Traffic</p>
                <p className="mb-1 text-sm text-muted">평균 추정 유동인구 지수</p>
                <p className="text-3xl font-bold tracking-tight">{formatScore(metrics.avg_foot_traffic)}</p>
                <p className="text-xs text-muted">/ 100</p>
              </Card>
              <Card>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Top Competition</p>
                <p className="mb-1 text-sm text-muted">경쟁이 가장 치열한 업종</p>
                <p className="text-3xl font-bold tracking-tight">{metrics.top_competition_type}</p>
              </Card>
            </div>

            <InsightBox headline="상권 리스크 요약" className="mt-4">
              {buildDashboardInsight(metrics)}
            </InsightBox>

            <Link
              href={`/permits/${id}`}
              className="mt-8 inline-flex w-full items-center justify-center rounded-2xl bg-brand-gradient py-3 font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand sm:w-auto sm:px-8"
            >
              인허가 체크리스트 보기 →
            </Link>
          </div>
        </div>
      )}
    </main>
  );
}
