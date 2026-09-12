"use client";

import { useState } from "react";
import { Tag } from "@/components/Tag";
import { VACANCY_CONFIDENCE_LABEL, type MatchCandidate } from "@/lib/types";

/**
 * 공실 추정 근거 패널.
 *
 * 매칭 결과의 매물은 소상공인시장진흥공단 상가(상권)정보 API와 국토교통부
 * 건축HUB 건축물대장정보 API를 조인해 "추정"한 공실이다. 두 API 모두 공실
 * 여부를 직접 제공하지 않으므로, 사용자가 확정 정보로 오해하지 않도록
 * 판정 근거·신뢰도·출처를 항상 같이 보여 준다.
 *
 * 목업 데이터(vacancy 없음)에서는 아무것도 렌더하지 않는다.
 */

const CONFIDENCE_TONE: Record<string, "done" | "neutral" | "pending"> = {
  high: "done",
  medium: "neutral",
  low: "pending",
};

/** data_sources 값이 "추정값"으로 시작하면 실데이터와 시각적으로 구분한다. */
function isEstimated(label: string) {
  return label.startsWith("추정값");
}

/** 출처 배지에 띄울 필드 라벨. data_sources의 키와 맞춘다. */
const FIELD_LABELS: Record<string, string> = {
  built_year: "준공연도",
  area_pyeong: "전용면적",
  floor: "층",
  register_purpose: "대장 용도",
  structure: "구조",
  elevators: "승강기",
  address: "소재지",
  nearby_stores: "인근 점포",
  competition_saturation_index: "경쟁포화도",
  aging_score: "노후도 점수",
  accessibility_score: "접근성 점수",
  lighting_score: "채광 점수",
  vacancy: "공실 판정",
  foot_traffic_index: "유동인구 지수",
  demographic_fit_index: "인구통계 적합도",
  estimated_rent: "추정 월세",
};

// 화면이 배지로 도배되지 않게 중요한 순서대로만 보여 주고 나머지는 접어 둔다.
const PRIMARY_FIELDS = ["vacancy", "built_year", "area_pyeong", "competition_saturation_index"];

export default function VacancyEvidence({ match }: { match: MatchCandidate }) {
  const [showBasis, setShowBasis] = useState(false);
  const [showAllSources, setShowAllSources] = useState(false);

  const vacancy = match.vacancy;
  const sources = match.data_sources ?? {};
  const sourceKeys = Object.keys(sources).filter((key) => key in FIELD_LABELS);

  if (!vacancy && sourceKeys.length === 0) return null;

  const visibleKeys = showAllSources
    ? sourceKeys
    : sourceKeys.filter((key) => PRIMARY_FIELDS.includes(key));

  return (
    <section className="mb-6 rounded-lg border border-border bg-background p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
          Data Provenance
        </span>
        {vacancy && (
          <Tag tone={CONFIDENCE_TONE[vacancy.confidence] ?? "neutral"}>
            공실 추정 · 신뢰도 {VACANCY_CONFIDENCE_LABEL[vacancy.confidence]}
          </Tag>
        )}
      </div>

      {vacancy && (
        <>
          <dl className="mb-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
            <div>
              <dt className="text-muted">판정 방식</dt>
              <dd className="font-medium">{vacancy.method}</dd>
            </div>
            <div>
              <dt className="text-muted">건축물대장 용도</dt>
              <dd className="font-medium">{vacancy.register_purpose || "미기재"}</dd>
            </div>
            <div>
              <dt className="text-muted">해당 층 영업 점포</dt>
              <dd className="font-medium">{vacancy.floor_store_count}건</dd>
            </div>
            <div>
              <dt className="text-muted">건물 전체 영업 점포</dt>
              <dd className="font-medium">{vacancy.building_store_count}건</dd>
            </div>
          </dl>

          <button
            type="button"
            onClick={() => setShowBasis((open) => !open)}
            aria-expanded={showBasis}
            className="text-xs font-medium text-accent-text underline-offset-2 hover:underline"
          >
            {showBasis ? "판정 근거 접기" : `판정 근거 ${vacancy.basis.length}건 보기`}
          </button>

          {showBasis && (
            <ul className="mt-2 space-y-1 border-l-2 border-border pl-3 text-xs leading-relaxed text-muted">
              {vacancy.basis.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}

          {vacancy.unknown_floor_store_count > 0 && (
            <p className="mt-2 text-xs leading-relaxed text-amber-700">
              이 건물에는 층 표기가 없는 사업자 {vacancy.unknown_floor_store_count}건이 있어, 실제로는
              영업 중인 층일 수 있습니다.
            </p>
          )}
        </>
      )}

      {(match.nearby_store_count != null || (match.nearby_stores?.length ?? 0) > 0) && (
        <p className="mt-3 text-xs leading-relaxed text-muted">
          {match.nearby_store_count != null && (
            <>
              반경 300m 내 영업 점포 {match.nearby_store_count}건
              {match.competitor_count != null && <> · 동일 업종 {match.competitor_count}건</>}
            </>
          )}
          {(match.nearby_stores?.length ?? 0) > 0 && (
            <>
              {match.nearby_store_count != null && " · "}
              같은 건물 영업 중: {match.nearby_stores!.join(", ")}
            </>
          )}
        </p>
      )}

      {visibleKeys.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <ul className="space-y-1.5">
            {visibleKeys.map((key) => (
              <li key={key} className="flex flex-wrap items-baseline gap-x-2 text-xs">
                <span className="min-w-[84px] font-medium">{FIELD_LABELS[key]}</span>
                <span className={isEstimated(sources[key]) ? "text-slate-500" : "text-accent-text"}>
                  {sources[key]}
                </span>
              </li>
            ))}
          </ul>

          {sourceKeys.length > visibleKeys.length && (
            <button
              type="button"
              onClick={() => setShowAllSources(true)}
              className="mt-2 text-xs font-medium text-accent-text underline-offset-2 hover:underline"
            >
              출처 {sourceKeys.length - visibleKeys.length}건 더 보기
            </button>
          )}
        </div>
      )}
    </section>
  );
}
