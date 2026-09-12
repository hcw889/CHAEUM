"use client";

import { AnalysisError, useAnalysis } from "./AnalysisData";

import { Card } from "@/components/Card";
import { Skeleton } from "@/components/Skeleton";
import { buildStrategyGrid, type StrategyQuadrant } from "@/lib/strategyTemplates";

const QUADRANT_META: Record<string, { icon: string; eyebrow: string }> = {
  "입지 전략": { icon: "📍", eyebrow: "Location Strategy" },
  포지셔닝: { icon: "🎯", eyebrow: "Positioning" },
  "채널 전략": { icon: "📡", eyebrow: "Channel Strategy" },
  "가격 전략": { icon: "💰", eyebrow: "Pricing Strategy" },
};

export default function StrategySection() {
  const { building: buildingResource, candidates: candidateResource } = useAnalysis();
  const building = buildingResource.data;
  const top = candidateResource.data?.[0] ?? null;
  if (buildingResource.error) return <AnalysisError message={buildingResource.error} onRetry={buildingResource.retry} />;
  if (candidateResource.error) return <AnalysisError message={candidateResource.error} onRetry={candidateResource.retry} />;
  if (candidateResource.data?.length === 0) return <p className="text-sm text-muted">추천 업종이 없어 전략을 만들 수 없습니다.</p>;

  const grid: StrategyQuadrant[] = building && top ? buildStrategyGrid(building, top) : [];

  return (
    <div>

      <p className="mb-6 text-sm text-muted">
        {top ? `추천 업종 "${top.type}" 기준으로 생성된 실행 전략입니다.` : "불러오는 중..."}
      </p>

      {grid.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {grid.map((q) => {
            const meta = QUADRANT_META[q.title] ?? { icon: "📌", eyebrow: q.title };
            const [benefit, ...rest] = [...q.points].reverse();
            const bodyPoints = rest.reverse();
            return (
              <Card key={q.title}>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{meta.eyebrow}</p>
                <h3 className="mb-3 flex items-center gap-2 text-lg font-bold">
                  <span aria-hidden>{meta.icon}</span>
                  {q.title}
                </h3>
                <ul className="mb-4 space-y-2 text-sm leading-relaxed text-foreground">
                  {bodyPoints.map((p, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-muted">·</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
                <div className="rounded-md border border-amber-100 bg-amber-50 p-3">
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-amber-700">Expected Benefit</p>
                  <p className="text-sm leading-relaxed text-amber-900">{benefit}</p>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <Skeleton className="mb-3 h-4 w-20" />
              <Skeleton className="mb-2 h-3 w-full" />
              <Skeleton className="mb-2 h-3 w-5/6" />
              <Skeleton className="h-3 w-3/4" />
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
