"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/Skeleton";
import { useAnalysis } from "./AnalysisData";

const FootfallPanel = dynamic(() => import("@/components/footfall/FootfallPanel"), {
  ssr: false,
  loading: () => <Skeleton className="h-[440px] w-full rounded-lg" />,
});

export default function FootfallSection() {
  const { buildingId } = useAnalysis();
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!container.current) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true);
        observer.disconnect();
      }
    }, { rootMargin: "600px" });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={container}>
      <p className="mb-6 text-sm leading-relaxed text-muted">선택한 매물 주변의 유동인구를 지도와 구역별 수치로 비교해 보세요. 평일·주말과 시간대를 바꾸면 주변 상권의 흐름을 확인할 수 있습니다.</p>
      {visible ? <FootfallPanel buildingId={buildingId} /> : <Skeleton className="h-[440px] w-full rounded-lg" />}
    </div>
  );
}
