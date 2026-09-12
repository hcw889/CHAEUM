"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BeforeAfterSlider } from "@/components/BeforeAfterSlider";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { api } from "@/lib/api";
import type { Building, BusinessFitCandidate } from "@/lib/types";

export default function VisualizePage() {
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

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />

      <h1 className="mb-1 text-2xl font-bold tracking-tight">시각화</h1>
      <p className="mb-6 text-sm text-muted">
        슬라이더를 움직여 현재 모습과 추천 업종 적용 후 모습을 비교해보세요. 실제 diffusion 이미지 생성 연동 전까지는
        플레이스홀더로 대체됩니다.
      </p>

      {!building || !top ? (
        <p className="text-muted">불러오는 중...</p>
      ) : (
        <>
          <Card>
            <BeforeAfterSlider
              before={
                <div
                  className="flex h-full w-full flex-col items-center justify-center gap-2 text-white"
                  style={{ backgroundColor: building.thumbnail_color }}
                >
                  <span className="text-4xl">🏚️</span>
                  <span className="rounded-full bg-black/30 px-3 py-1 text-xs">{building.name}</span>
                </div>
              }
              after={
                <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-accent text-accent-foreground">
                  <span className="text-4xl">✨</span>
                  <span className="rounded-full bg-black/15 px-3 py-1 text-xs">{top.type} 적용 컨셉</span>
                </div>
              }
            />
          </Card>

          <p className="mt-4 text-center text-xs text-muted">
            * 위 이미지는 목업 플레이스홀더이며, 실제 서비스에서는 업로드 사진 기반 diffusion 모델 결과로 대체될 예정입니다.
          </p>

          <Link
            href={`/report/${id}`}
            className="mt-8 inline-flex w-full items-center justify-center rounded-xl bg-accent py-3 font-medium text-accent-foreground transition-opacity hover:opacity-90 sm:w-auto sm:px-8"
          >
            리포트 보기 →
          </Link>
        </>
      )}
    </main>
  );
}
