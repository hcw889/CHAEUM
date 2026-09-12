"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { Skeleton } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { buildStrategyGrid, type StrategyQuadrant } from "@/lib/strategyTemplates";
import type { Building, BusinessFitCandidate } from "@/lib/types";

const QUADRANT_META: Record<string, { icon: string; eyebrow: string }> = {
  "입지 전략": { icon: "📍", eyebrow: "Location Strategy" },
  포지셔닝: { icon: "🎯", eyebrow: "Positioning" },
  "채널 전략": { icon: "📡", eyebrow: "Channel Strategy" },
  "가격 전략": { icon: "💰", eyebrow: "Pricing Strategy" },
};

export default function StrategyPage() {
  const { id } = useParams<{ id: string }>();
  const [building, setBuilding] = useState<Building | null>(null);
  const [top, setTop] = useState<BusinessFitCandidate | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getBuilding(id), api.getBusinessFit(id)])
      .then(([b, candidates]) => {
        setBuilding(b);
        setTop(candidates[0]);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "불러오기 실패"));
  }, [id]);

  if (error) return <main className="mx-auto max-w-3xl px-6 py-10 text-danger">{error}</main>;

  const grid: StrategyQuadrant[] = building && top ? buildStrategyGrid(building, top) : [];

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />

      <h1 className="mb-1 text-2xl font-bold tracking-tight">전략 그리드</h1>
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
                <h2 className="mb-3 flex items-center gap-2 text-lg font-bold">
                  <span aria-hidden>{meta.icon}</span>
                  {q.title}
                </h2>
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

      <Link
        href={`/visualize/${id}`}
        className="mt-8 inline-flex w-full items-center justify-center rounded-2xl bg-brand-gradient py-3 font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand sm:w-auto sm:px-8"
      >
        주변 유동인구 보기 →
      </Link>
    </main>
  );
}
