"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import FootfallPanel from "@/components/footfall/FootfallPanel";

export default function VisualizePage() {
  const { id } = useParams<{ id: string }>();

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />
      <h1 className="mb-2 text-2xl font-bold">유동인구 시각화</h1>
      <p className="mb-6 text-sm leading-relaxed text-muted">
        선택한 매물 주변의 유동인구를 지도와 구역별 수치로 비교해 보세요.
        평일·주말과 시간대를 바꾸면 주변 상권의 흐름을 확인할 수 있습니다.
      </p>

      <FootfallPanel key={id} buildingId={id} />

      <Link
        href={`/report/${id}`}
        className="mt-6 inline-flex w-full items-center justify-center rounded-2xl bg-brand-gradient py-3 font-semibold text-accent-foreground shadow-card transition-all hover:shadow-glow-brand sm:w-auto sm:px-8"
      >
        리포트 보기 →
      </Link>
    </main>
  );
}
