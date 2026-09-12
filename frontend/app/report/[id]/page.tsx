"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { DataFreshness } from "@/components/DataFreshness";
import { RiskBadge } from "@/components/RiskBadge";
import { api } from "@/lib/api";
import type { ReportSummary } from "@/lib/types";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<ReportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getReport(id)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "불러오기 실패"));
  }, [id]);

  if (error) return <main className="mx-auto max-w-3xl px-6 py-10 text-danger">{error}</main>;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <div className="no-print">
        <BuildingPageHeader buildingId={id} />
      </div>

      {!report ? (
        <p className="text-muted">리포트를 생성하는 중...</p>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="mb-1 text-sm font-medium text-accent">Executive Summary</p>
              <h1 className="text-2xl font-bold tracking-tight">{report.building.name}</h1>
              <p className="mt-1 text-sm text-muted">{report.building.address}</p>
            </div>
            <button
              onClick={() => window.print()}
              className="no-print rounded-xl bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition-opacity hover:opacity-90"
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
            <h2 className="mb-3 font-semibold">요약</h2>
            <p className="text-sm leading-relaxed text-foreground">
              {report.building.name}({report.building.address})은 {report.building.built_year}년에 준공된{" "}
              {report.building.floor}층, {report.building.area_pyeong}평 규모의 상가로, 종합 리스크 등급은 &apos;
              {report.building.risk_grade}&apos;입니다. 업종 적합도 분석 결과 <b>{report.top_business.type}</b>이(가){" "}
              {report.top_business.fit_score}점으로 가장 높은 적합도를 보였으며, 예상 임대료는 월{" "}
              {report.top_business.estimated_rent.toLocaleString()}원입니다. 인근 상권은 평균 경쟁포화도{" "}
              {report.dashboard.avg_competition_saturation}점, 평균 유동인구 지수 {report.dashboard.avg_foot_traffic}점
              수준으로 추정됩니다.
            </p>
          </Card>

          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <p className="mb-1 text-sm text-muted">추천 업종</p>
              <p className="text-xl font-semibold">{report.top_business.type}</p>
              <p className="text-xs text-muted">적합도 {report.top_business.fit_score}점</p>
            </Card>
            <Card>
              <p className="mb-1 text-sm text-muted">건물 컨디션</p>
              <p className="text-xl font-semibold">
                {Math.round(
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
              <p className="mb-1 text-sm text-muted">평균 추정 임대료</p>
              <p className="text-xl font-semibold">{Math.round(report.dashboard.avg_estimated_rent / 10000)}만원</p>
              <p className="text-xs text-muted">인근 업종 평균 (월)</p>
            </Card>
          </div>

          <Card>
            <h2 className="mb-3 font-semibold">필요 인허가 ({report.top_business.type} 기준)</h2>
            <ul className="list-inside list-disc space-y-1 text-sm text-foreground">
              {report.top_business.required_permits.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </Card>

          <p className="mt-8 text-center text-xs text-muted">
            본 리포트는 채움(Chaeum) MVP의 mock 데이터를 기반으로 생성되었으며, 실제 서비스에서는 실시간 데이터 연동
            결과로 대체됩니다.
          </p>
        </>
      )}
    </main>
  );
}
