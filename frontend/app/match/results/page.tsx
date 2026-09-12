"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { Wordmark } from "@/components/Logo";
import { RankMedal } from "@/components/RankMedal";
import { ScoreBarBreakdown } from "@/components/ScoreBarBreakdown";
import { SkeletonCardGrid } from "@/components/Skeleton";
import { parseStored, useStoredValue } from "@/lib/browserStore";
import { formatScore } from "@/lib/format";
import { useStoredRole } from "@/lib/role";
import { getRoleCopy } from "@/lib/roleCopy";
import type { MatchCandidate, MatchRequest, ScoreBreakdown } from "@/lib/types";

// matching_agents.PRIORITY_WEIGHTS(backend)와 동일한 값. 결과 화면의 기여도 막대그래프 표시에만 사용.
const PRIORITY_WEIGHTS: Record<string, { budget: number; market_fit: number; condition: number }> = {
  예산절약: { budget: 0.5, market_fit: 0.3, condition: 0.2 },
  매출잠재력: { budget: 0.2, market_fit: 0.6, condition: 0.2 },
  건물안정성: { budget: 0.2, market_fit: 0.2, condition: 0.6 },
};
const DEFAULT_WEIGHTS = { budget: 1 / 3, market_fit: 1 / 3, condition: 1 / 3 };

const AGENT_LABELS: Record<string, string> = {
  budget: "예산 적합도",
  market_fit: "상권 적합도",
  condition: "건물 컨디션",
};
const AGENT_ORDER = ["budget", "market_fit", "condition"];

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
  const matches = useMemo(
    () => parseStored<{ matches: MatchCandidate[] }>(resultRaw)?.matches ?? null,
    [resultRaw],
  );

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

  const breakdown: ScoreBreakdown | null = selectedMatch
    ? AGENT_ORDER.reduce((acc, factor) => {
        const weight = weights[factor as keyof typeof weights];
        const raw = selectedMatch.agent_scores[factor as keyof typeof selectedMatch.agent_scores];
        acc[`${factor}_weight`] = weight;
        acc[`${factor}_raw_score`] = raw;
        acc[`${factor}_contribution`] = Math.round(weight * raw * 10) / 10;
        return acc;
      }, {} as ScoreBreakdown)
    : null;

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

              {m.space_vision && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">
                    노출 {formatScore(m.space_vision.exposure_score)}
                  </span>
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">
                    접근 {formatScore(m.space_vision.accessibility_score)}
                  </span>
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">
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

      {selectedMatch && breakdown && (
        <Card>
          <h2 className="mb-1 font-semibold">{selectedMatch.address}</h2>
          <p className="mb-5 text-sm leading-relaxed text-foreground">{selectedMatch.explanation}</p>
          <ScoreBarBreakdown breakdown={breakdown} factors={AGENT_ORDER} labels={AGENT_LABELS} />

          {selectedMatch.space_vision && (
            <div className="mt-6 border-t border-border pt-6">
              <h3 className="mb-4 text-sm font-semibold text-muted">AI Space Vision 분석</h3>

              {selectedMatch.photo_url && (
                <div className="mb-4 overflow-hidden rounded-lg border border-border">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={selectedMatch.photo_url}
                    alt={`${selectedMatch.address} 상가 외관 사진`}
                    className="aspect-[4/3] w-full object-cover"
                  />
                  <p className="border-t border-border bg-background px-3 py-1.5 text-xs text-muted">
                    BEFORE 원본 사진
                  </p>
                </div>
              )}

              <p className="mb-5 text-sm text-foreground">
                {selectedMatch.space_vision.detected_elements.join(" · ")}
              </p>

              <div className="mb-5 space-y-3">
                {(
                  [
                    ["노출성", selectedMatch.space_vision.exposure_score],
                    ["접근성", selectedMatch.space_vision.accessibility_score],
                    ["팝업 적합도", selectedMatch.space_vision.popup_fit_score],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label}>
                    <div className="mb-1.5 flex justify-between text-sm">
                      <span className="font-medium text-foreground">{label}</span>
                      <span className="text-muted">{formatScore(value)}점</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                      <div
                        className="h-full rounded-full bg-accent transition-all"
                        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <p className="text-sm leading-relaxed text-muted">{selectedMatch.space_vision.visual_summary}</p>
            </div>
          )}

          <Link
            href={`/diagnosis/${selectedMatch.building_id}`}
            className="mt-6 inline-flex w-full items-center justify-center rounded-md bg-accent py-3 font-medium text-accent-foreground transition-opacity hover:opacity-90 sm:w-auto sm:px-8"
          >
            건물 상세 진단 보기 →
          </Link>
        </Card>
      )}
    </main>
  );
}
