"use client";

import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { StepNav } from "@/components/StepNav";
import { AnalysisProvider } from "./AnalysisData";
import DiagnosisSection from "./DiagnosisSection";
import RankingSection from "./RankingSection";
import DashboardSection from "./DashboardSection";
import PermitsSection from "./PermitsSection";
import StrategySection from "./StrategySection";
import FootfallSection from "./FootfallSection";
import ReportSection from "./ReportSection";
import "./analysis.css";

const SECTIONS = [
  { id: "diagnosis", title: "진단 결과", Component: DiagnosisSection },
  { id: "ranking", title: "업종 적합도 순위", Component: RankingSection },
  { id: "dashboard", title: "리스크 대시보드", Component: DashboardSection },
  { id: "permits", title: "인허가 체크리스트", Component: PermitsSection },
  { id: "strategy", title: "전략 그리드", Component: StrategySection },
  { id: "visualize", title: "유동인구 시각화", Component: FootfallSection },
  { id: "report", title: "종합 리포트", Component: ReportSection },
];

export default function BuildingAnalysis({ buildingId }: { buildingId: string }) {
  return (
    <AnalysisProvider key={buildingId} buildingId={buildingId}>
      <main className="building-analysis mx-auto w-full max-w-5xl flex-1 px-4 pb-16 pt-6 sm:px-6 sm:pt-8">
        <BuildingPageHeader buildingId={buildingId} />
        <div className="no-print mb-5 mt-8">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent-text">Building Insights</p>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">건물 종합 분석</h1>
          <p className="mt-2 text-sm text-muted">진단부터 실행 전략까지 한 번에 살펴보세요. 메뉴를 누르면 해당 내용으로 이동합니다.</p>
        </div>
        <StepNav buildingId={buildingId} />
        <div className="analysis-sections">
          {SECTIONS.map(({ id, title, Component }, index) => (
            <section key={id} id={id} aria-labelledby={`${id}-title`} className="analysis-section" tabIndex={-1}>
              <div className="mb-6 flex items-center gap-3">
                <span aria-hidden className="no-print flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-surface text-xs font-semibold text-accent-text">{String(index + 1).padStart(2, "0")}</span>
                <h2 id={`${id}-title`} className="text-xl font-bold tracking-tight sm:text-2xl">{title}</h2>
              </div>
              <Component />
            </section>
          ))}
        </div>
      </main>
    </AnalysisProvider>
  );
}
