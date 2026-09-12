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
          {grid.map((q) => (
            <Card key={q.title}>
              <h2 className="mb-3 font-semibold text-accent-text">{q.title}</h2>
              <ul className="space-y-2 text-sm leading-relaxed text-foreground">
                {q.points.map((p, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-muted">·</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
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
        시각화 보기 →
      </Link>
    </main>
  );
}
