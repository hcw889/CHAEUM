"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { Wordmark } from "@/components/Logo";
import { RadialGauge } from "@/components/RadialGauge";
import { RankMedal } from "@/components/RankMedal";
import RoadviewPanel from "@/components/RoadviewPanel";
import { SkeletonCardGrid } from "@/components/Skeleton";
import { Tag } from "@/components/Tag";
import VacancyEvidence from "@/components/VacancyEvidence";
import { parseStored, useStoredValue } from "@/lib/browserStore";
import { formatPercent, formatScore } from "@/lib/format";
import { useStoredRole } from "@/lib/role";
import { getRoleCopy } from "@/lib/roleCopy";
import type { MatchAgentScores, MatchRequest, MatchResponse } from "@/lib/types";

// matching_agents.PRIORITY_WEIGHTS(backend)와 동일한 값. 결과 화면의 기여도 막대그래프 표시에만 사용.
const PRIORITY_WEIGHTS: Record<string, { budget: number; market_fit: number; condition: number }> = {
  예산절약: { budget: 0.5, market_fit: 0.3, condition: 0.2 },
  매출잠재력: { budget: 0.2, market_fit: 0.6, condition: 0.2 },
  건물안정성: { budget: 0.2, market_fit: 0.2, condition: 0.6 },
};
const DEFAULT_WEIGHTS = { budget: 1 / 3, market_fit: 1 / 3, condition: 1 / 3 };

const AGENT_META: { key: keyof MatchAgentScores; label: string; icon: string }[] = [
  { key: "budget", label: "예산 적합도", icon: "💰" },
  { key: "market_fit", label: "상권 적합도", icon: "📍" },
  { key: "condition", label: "건물 컨디션", icon: "🏢" },
];

const RANK_BORDER: Record<string, string> = {
  gold: "border-gold",
  silver: "border-silver",
  bronze: "border-bronze",
};

export default function MatchResultsPage() {
  const router = useRouter();
  const role = useStoredRole();
  const requestRaw = useStoredValue("session", "chaeum_match_request");
  const resultRaw = useStoredValue("session", "chaeum_match_result");
  // raw 문자열 기준으로 memo해 파싱 결과의 identity를 안정시킨다 (아래 useMemo들의 deps).
  const request = useMemo(() => parseStored<MatchRequest>(requestRaw), [requestRaw]);
  const result = useMemo(() => parseStored<MatchResponse>(resultRaw), [resultRaw]);
  const matches = useMemo(() => result?.matches ?? null, [result]);

  // 선택된 매물은 사용자가 고르기 전까지 1순위를 가리킨다 (파생값이라 상태로 두지 않는다).
  const [picked, setPicked] = useState<string | null>(null);
  const selected = picked ?? matches?.[0]?.building_id ?? null;

  // wizard를 거치지 않고 결과 URL로 바로 들어온 경우 입력 화면으로 돌려보낸다.
  useEffect(() => {
    try {
      if (!sessionStorage.getItem("chaeum_match_result")) router.replace("/match/new");
    } catch {
      router.replace("/match/new");
    }
  }, [router]);

  const top3 = useMemo(() => matches?.filter((m) => m.rank) ?? [], [matches]);
  const rest = useMemo(() => matches?.filter((m) => !m.rank) ?? [], [matches]);
  const selectedMatch = matches?.find((m) => m.building_id === selected) ?? null;
  const weights = request ? PRIORITY_WEIGHTS[request.priority] ?? DEFAULT_WEIGHTS : DEFAULT_WEIGHTS;

  const agentWeight = (key: keyof MatchAgentScores) => weights[key];

  if (!matches || !request) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
        <SkeletonCardGrid count={3} />
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/" className="text-lg">
          <Wordmark />
        </Link>
        <Link href="/match/new" className="text-sm text-muted hover:text-foreground">
          조건 다시 입력 →
        </Link>
      </div>

      <h1 className="mb-1 text-2xl font-bold tracking-tight">{getRoleCopy(role).resultsTitle}</h1>
      <p className="mb-6 text-sm text-muted">
        {request.business_type} · {request.region_pref} · 우선순위 &apos;{request.priority}&apos; 기준 추천 매물입니다.
      </p>

      {result?.source_note && (
        <div
          className={`mb-6 rounded-lg border p-4 text-xs leading-relaxed ${
            result.data_mode === "real"
              ? "border-brand-200 bg-brand-50 text-accent-text"
              : "border-amber-200 bg-amber-50 text-amber-800"
          }`}
        >
          <p className="mb-1 font-semibold">
            {result.data_mode === "real" ? "실데이터 기반 공실 추정" : "시연용 목업 데이터"}
            {result.data_mode === "real" && result.total_candidates != null && (
              <> · 조건 만족 매물 {result.total_candidates}건</>
            )}
          </p>
          <p>{result.source_note}</p>
        </div>
      )}

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {top3.map((m) => (
          <button key={m.building_id} onClick={() => setPicked(m.building_id)} className="text-left">
            <Card
              className={`h-full border-2 transition-all ${
                selected === m.building_id ? RANK_BORDER[m.rank ?? ""] : "border-border"
              } ${m.rank === "gold" ? "sm:scale-105" : ""}`}
            >
              <div className="mb-3 flex items-center gap-2.5">
                <RankMedal rank={m.rank} />
                <span className="text-sm font-semibold leading-snug">{m.address}</span>
              </div>
              <p className="text-3xl font-bold tracking-tight">{formatScore(m.final_score)}</p>
              <p className="text-xs text-muted">종합 매칭 점수</p>

              {(m.area_pyeong || m.built_year) && (
                <p className="mt-2 text-xs text-muted">
                  {m.area_pyeong ? `${m.area_pyeong}평` : null}
                  {m.area_pyeong && m.built_year ? " · " : null}
                  {m.built_year ? `${m.built_year}년 준공` : null}
                </p>
              )}

              {m.space_vision && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-text">
                    노출 {formatScore(m.space_vision.exposure_score)}
                  </span>
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-text">
                    접근 {formatScore(m.space_vision.accessibility_score)}
                  </span>
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-text">
                    팝업 {formatScore(m.space_vision.popup_fit_score)}
                  </span>
                </div>
              )}
            </Card>
          </button>
        ))}
      </div>

      {rest.length > 0 && (
        <div className="mb-8 space-y-2">
          {rest.map((m) => (
            <button
              key={m.building_id}
              onClick={() => setPicked(m.building_id)}
              className={`flex w-full items-center justify-between rounded-md border px-4 py-3 text-left transition-colors ${
                selected === m.building_id ? "border-accent bg-accent-soft" : "border-border bg-surface"
              }`}
            >
              <span className="font-medium">{m.address}</span>
              <span className="text-sm text-muted">{formatScore(m.final_score)}점</span>
            </button>
          ))}
        </div>
      )}

      {selectedMatch && (
        <Card>
          <h2 className="mb-1 font-semibold">{selectedMatch.address}</h2>
          <p className="mb-5 text-sm leading-relaxed text-foreground">{selectedMatch.explanation}</p>

          {/* 공실 판정이 추정임을 밝히고 근거/출처를 보여 준다. 목업에서는 렌더되지 않는다. */}
          <VacancyEvidence match={selectedMatch} />

          {/* 실제 상가가 어떻게 생겼는지 카카오 로드뷰로 보여준다. 로드뷰가 없는
              구간은 photo_url(참고 이미지)로 폴백한다. */}
          <div className="mb-6">
            <RoadviewPanel
              key={selectedMatch.building_id}
              lat={selectedMatch.lat}
              lng={selectedMatch.lng}
              address={selectedMatch.address}
              fallbackSrc={selectedMatch.photo_url}
            />
          </div>

          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Why This Match</p>
          <h3 className="mb-4 text-lg font-bold">왜 이 매물?</h3>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {AGENT_META.map((a) => {
              const score = selectedMatch.agent_scores[a.key];
              const weight = agentWeight(a.key);
              return (
                <Card key={a.key} className="bg-background text-center shadow-none">
                  <div className="mb-2 flex items-center justify-center gap-2">
                    <span aria-hidden>{a.icon}</span>
                    <span className="font-semibold">{a.label}</span>
                  </div>
                  <div className="mb-1 flex justify-center">
                    <RadialGauge value={score} label="점수" />
                  </div>
                  <p className="text-xs text-muted">이번 추천에서 가중치 {formatPercent(weight * 100, 0)} 반영</p>
                </Card>
              );
            })}

            {selectedMatch.space_vision && (
              <Card className="bg-background shadow-none">
                <div className="mb-3 flex items-center gap-2">
                  <span aria-hidden>🖼️</span>
                  <span className="font-semibold">AI Space Vision</span>
                </div>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  <Tag>노출 {formatScore(selectedMatch.space_vision.exposure_score)}</Tag>
                  <Tag>접근 {formatScore(selectedMatch.space_vision.accessibility_score)}</Tag>
                  <Tag>팝업 {formatScore(selectedMatch.space_vision.popup_fit_score)}</Tag>
                </div>
                <p className="text-xs leading-relaxed text-muted">{selectedMatch.space_vision.visual_summary}</p>
              </Card>
            )}
          </div>

          {selectedMatch.space_vision && (
            <p className="mt-4 text-xs text-muted">{selectedMatch.space_vision.detected_elements.join(" · ")}</p>
          )}

          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Link
              href={`/diagnosis/${selectedMatch.building_id}`}
              className="inline-flex items-center justify-center rounded-2xl bg-brand-gradient px-6 py-3 font-semibold text-accent-foreground shadow-card transition-all hover:shadow-glow-brand"
            >
              건물 상세 진단 보기 →
            </Link>
            <Link
              href={`/visualize/${selectedMatch.building_id}`}
              className="inline-flex items-center justify-center rounded-2xl border border-border px-6 py-3 font-semibold transition-colors hover:bg-accent-soft"
            >
              주변 유동인구 보기 →
            </Link>
          </div>
        </Card>
      )}
    </main>
  );
}
