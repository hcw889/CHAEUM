"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { DataFreshness } from "@/components/DataFreshness";
import { RiskBadge } from "@/components/RiskBadge";
import { ScoreMeter } from "@/components/ScoreMeter";
import { api } from "@/lib/api";
import type { Building } from "@/lib/types";

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

      <h2 className="mb-3 text-sm font-semibold text-muted">세부 진단 항목</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <ScoreMeter label="노후도" score={building.diagnosis.aging_score} />
        </Card>
        <Card>
          <ScoreMeter label="접근성" score={building.diagnosis.accessibility_score} />
        </Card>
        <Card>
          <ScoreMeter label="채광" score={building.diagnosis.lighting_score} />
        </Card>
      </div>

      <Link
        href={`/ranking/${id}`}
        className="mt-8 inline-flex w-full items-center justify-center rounded-xl bg-accent py-3 font-medium text-accent-foreground transition-opacity hover:opacity-90 sm:w-auto sm:px-8"
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
      <p className="text-muted">진단 결과를 불러오는 중...</p>
    </main>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <p className="text-danger">{message}</p>
      <Link href="/property/new" className="mt-4 inline-block text-sm text-accent">
        ← 매물 입력으로 돌아가기
      </Link>
    </main>
  );
}
