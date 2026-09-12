"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { DataFreshness } from "@/components/DataFreshness";
import { InsightBox } from "@/components/InsightBox";
import { levelOf } from "@/components/ScoreMeter";
import { RadialGauge } from "@/components/RadialGauge";
import { RiskBadge } from "@/components/RiskBadge";
import { Skeleton, SkeletonCardGrid } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { formatScore } from "@/lib/format";
import type { Building, RiskGrade } from "@/lib/types";

const SUB_SCORE_ROWS: { key: keyof Building["diagnosis"]; icon: string; label: string }[] = [
  { key: "aging_score", icon: "🏚️", label: "노후도" },
  { key: "accessibility_score", icon: "🚏", label: "접근성" },
  { key: "lighting_score", icon: "☀️", label: "채광" },
];

const RISK_GRADE_ICON: Record<RiskGrade, string> = { 안전: "🛡️", 주의: "⚠️", 위험: "🚨" };

/** 실제 세부 점수만으로 강점/약점을 뽑아내는 진단 요약 문장 — 새 데이터를 만들지 않고 기존 점수를 재구성. */
function buildDiagnosisInsight(building: Building): { headline: string; body: string } {
  const rows = SUB_SCORE_ROWS.map((r) => ({ label: r.label, score: building.diagnosis[r.key] }));
  const strongest = rows.reduce((a, b) => (b.score > a.score ? b : a));
  const weakest = rows.reduce((a, b) => (b.score < a.score ? b : a));

  if (strongest.label === weakest.label) {
    return {
      headline: `전 항목이 고르게 ${levelOf(strongest.score).label} 수준입니다.`,
      body: "노후도·접근성·채광 세부 점수 간 편차가 크지 않아 특정 항목을 보완하기보다 현재 컨디션을 유지하는 전략이 유효합니다.",
    };
  }

  return {
    headline: `${strongest.label}은(는) 강점, ${weakest.label}은(는) 보완이 필요합니다.`,
    body: `${strongest.label} 점수(${formatScore(strongest.score)}점)가 가장 높아 강점으로 어필할 수 있는 반면, ${weakest.label} 점수(${formatScore(
      weakest.score,
    )}점)는 상대적으로 낮아 업종 선정·전략 수립 시 보완 계획을 함께 고려하는 것이 좋습니다.`,
  };
}

export default function DiagnosisPage() {
  const { id } = useParams<{ id: string }>();
  const [building, setBuilding] = useState<Building | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getBuilding(id)
      .then(setBuilding)
      .catch((err) => setError(err instanceof Error ? err.message : "불러오기 실패"));
  }, [id]);

  if (error) return <ErrorState message={error} />;
  if (!building) return <LoadingState id={id} />;

  const overall =
    (building.diagnosis.aging_score + building.diagnosis.accessibility_score + building.diagnosis.lighting_score) / 3;
  const insight = buildDiagnosisInsight(building);

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />

      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{building.name}</h1>
          <p className="mt-1 text-sm text-muted">{building.address}</p>
          <p className="mt-1 text-sm text-muted">
            {building.floor}층 · {building.area_pyeong}평 · {building.built_year}년 준공
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <RiskBadge grade={building.risk_grade} />
          <DataFreshness month={building.data_reference_month} />
        </div>
      </div>

      <Card>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Risk Radar</p>
        <h2 className="mb-6 text-lg font-bold sm:text-xl">건물 컨디션 종합 진단</h2>

        <div className="mb-6 flex justify-center">
          <RadialGauge variant="semi" value={overall} label="종합 점수" />
        </div>

        <ul className="divide-y divide-border border-y border-border">
          {SUB_SCORE_ROWS.map((row) => {
            const score = building.diagnosis[row.key];
            const level = levelOf(score);
            return (
              <li key={row.key} className="flex items-center justify-between gap-3 py-3">
                <span className="flex items-center gap-2.5 text-sm font-medium text-foreground">
                  <span aria-hidden>{row.icon}</span>
                  {row.label}
                </span>
                <span className="flex items-center gap-3">
                  <span className="text-sm text-muted">{formatScore(score)}점</span>
                  <span
                    className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                    style={{ color: level.color, backgroundColor: "color-mix(in srgb, currentColor 14%, transparent)" }}
                  >
                    {level.label}
                  </span>
                </span>
              </li>
            );
          })}
          <li className="flex items-center justify-between gap-3 py-3">
            <span className="flex items-center gap-2.5 text-sm font-medium text-foreground">
              <span aria-hidden>{RISK_GRADE_ICON[building.risk_grade]}</span>
              종합 리스크 등급
            </span>
            <RiskBadge grade={building.risk_grade} />
          </li>
        </ul>

        <InsightBox headline={insight.headline} className="mt-6">
          {insight.body}
        </InsightBox>
      </Card>

      <Link
        href={`/ranking/${id}`}
        className="mt-8 inline-flex w-full items-center justify-center rounded-2xl bg-brand-gradient py-3 font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand sm:w-auto sm:px-8"
      >
        업종 적합도 순위 보기 →
      </Link>
    </main>
  );
}

function LoadingState({ id }: { id: string }) {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <Skeleton className="mb-2 h-7 w-48" />
          <Skeleton className="mb-1.5 h-4 w-64" />
          <Skeleton className="h-4 w-40" />
        </div>
        <div className="flex flex-col items-end gap-2">
          <Skeleton className="h-6 w-16" />
          <Skeleton className="h-6 w-32" />
        </div>
      </div>
      <Skeleton className="mb-3 h-4 w-24" />
      <SkeletonCardGrid count={3} />
    </main>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <p className="text-danger">{message}</p>
      <Link href="/property/new" className="mt-4 inline-block text-sm text-accent-text">
        ← 매물 입력으로 돌아가기
      </Link>
    </main>
  );
}
