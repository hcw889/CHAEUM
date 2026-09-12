"use client";

import { AnalysisError, useAnalysis } from "./AnalysisData";

import { Card } from "@/components/Card";
import { DataFreshness } from "@/components/DataFreshness";
import { RiskBadge } from "@/components/RiskBadge";
import { ScoreBarBreakdown } from "@/components/ScoreBarBreakdown";
import { Skeleton, SkeletonCardGrid } from "@/components/Skeleton";
import { formatCurrency, formatScore } from "@/lib/format";

export default function ReportSection() {
  const { report: { data: report, error, retry } } = useAnalysis();
  if (error) return <AnalysisError message={error} onRetry={retry} />;

  return (
    <div>
      {!report ? (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <Skeleton className="mb-2 h-4 w-32" />
              <Skeleton className="mb-2 h-7 w-56" />
              <Skeleton className="h-4 w-64" />
            </div>
          </div>
          <Card className="mb-4">
            <Skeleton className="mb-3 h-3 w-full" />
            <Skeleton className="mb-2 h-3 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </Card>
          <SkeletonCardGrid count={3} />
        </>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-accent-text">Executive Summary</p>
              <h3 className="text-xl font-bold tracking-tight">{report.building.name}</h3>
              <p className="mt-1 text-sm text-muted">{report.building.address}</p>
            </div>
            <button
              onClick={() => window.print()}
              className="no-print rounded-2xl bg-brand-gradient px-5 py-2.5 text-sm font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand"
            >
              PDF 다운로드
            </button>
          </div>

          <div className="mb-6 flex flex-wrap items-center gap-3">
            <RiskBadge grade={report.building.risk_grade} />
            <DataFreshness month={report.building.data_reference_month} />
            <span className="text-xs text-muted">리포트 생성일 {report.generated_at}</span>
          </div>

          <Card className="mb-4">
            <h3 className="mb-3 font-semibold">요약</h3>
            <p className="text-sm leading-relaxed text-foreground">
              {report.building.name}({report.building.address})은 {report.building.built_year}년에 준공된{" "}
              {report.building.floor}층, {report.building.area_pyeong}평 규모의 상가로, 종합 리스크 등급은 &apos;
              {report.building.risk_grade}&apos;입니다. 업종 적합도 분석 결과 <b>{report.top_business.type}</b>이(가){" "}
              {formatScore(report.top_business.fit_score)}점으로 가장 높은 적합도를 보였으며, 예상 임대료는 월{" "}
              {formatCurrency(report.top_business.estimated_rent)}입니다. 인근 상권은 평균 경쟁포화도{" "}
              {formatScore(report.dashboard.avg_competition_saturation)}점, 평균 유동인구 지수{" "}
              {formatScore(report.dashboard.avg_foot_traffic)}점 수준으로 추정됩니다.
            </p>
          </Card>

          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Top Business</p>
              <p className="mb-1 text-sm text-muted">추천 업종</p>
              <p className="text-xl font-semibold">{report.top_business.type}</p>
              <p className="text-xs text-muted">적합도 {formatScore(report.top_business.fit_score)}점</p>
            </Card>
            <Card>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Condition</p>
              <p className="mb-1 text-sm text-muted">건물 컨디션</p>
              <p className="text-xl font-semibold">
                {formatScore(
                  (report.building.diagnosis.aging_score +
                    report.building.diagnosis.accessibility_score +
                    report.building.diagnosis.lighting_score) /
                    3
                )}
                점
              </p>
              <p className="text-xs text-muted">노후도·접근성·채광 평균</p>
            </Card>
            <Card>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Rent</p>
              <p className="mb-1 text-sm text-muted">평균 추정 임대료</p>
              <p className="text-xl font-semibold">{formatScore(report.dashboard.avg_estimated_rent / 10_000)}만원</p>
              <p className="text-xs text-muted">인근 업종 평균 (월)</p>
            </Card>
            <Card>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Foot Traffic</p>
              <p className="mb-1 text-sm text-muted">평균 추정 유동인구 지수</p>
              <p className="text-xl font-semibold">{formatScore(report.dashboard.avg_foot_traffic)}점</p>
              <p className="text-xs text-muted">인근 업종 평균</p>
            </Card>
          </div>

          <Card className="mb-4">
            <h3 className="mb-1 font-semibold">{report.top_business.type} 스코어 근거</h3>
            <p className="mb-5 text-sm text-muted">가중합 방식으로 계산된 세부 항목별 기여도입니다.</p>
            <ScoreBarBreakdown breakdown={report.top_business.score_breakdown} />
          </Card>

          <Card>
            <h3 className="mb-3 font-semibold">필요 인허가 ({report.top_business.type} 기준)</h3>
            <ul className="list-inside list-disc space-y-1 text-sm text-foreground">
              {report.top_business.required_permits.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </Card>

          <p className="mt-8 text-center text-xs text-muted">
            본 리포트는 소상공인시장진흥공단 상가(상권)정보와 국토교통부 건축물대장 공공데이터를 기반으로 생성되었으며,
            임대료·유동인구 등 일부 지표는 추정치를 포함합니다.
          </p>
        </>
      )}
    </div>
  );
}
