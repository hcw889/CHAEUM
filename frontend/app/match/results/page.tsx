"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { RankMedal } from "@/components/RankMedal";
import { ScoreBarBreakdown } from "@/components/ScoreBarBreakdown";
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
  const [request, setRequest] = useState<MatchRequest | null>(null);
  const [matches, setMatches] = useState<MatchCandidate[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    try {
      const reqRaw = sessionStorage.getItem("chaeum_match_request");
      const resultRaw = sessionStorage.getItem("chaeum_match_result");
      if (!reqRaw || !resultRaw) {
        router.replace("/match/new");
        return;
      }
      const req: MatchRequest = JSON.parse(reqRaw);
      const result: { matches: MatchCandidate[] } = JSON.parse(resultRaw);
      setRequest(req);
      setMatches(result.matches);
      setSelected(result.matches[0]?.building_id ?? null);
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
        <p className="text-muted">불러오는 중...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          채움
        </Link>
        <Link href="/match/new" className="text-sm text-muted hover:text-foreground">
          조건 다시 입력 →
        </Link>
      </div>

      <h1 className="mb-1 text-2xl font-bold tracking-tight">매물 추천 결과</h1>
      <p className="mb-6 text-sm text-muted">
        {request.business_type} · {request.region_pref} · 우선순위 &apos;{request.priority}&apos; 기준 추천 매물입니다.
      </p>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {top3.map((m) => (
          <button key={m.building_id} onClick={() => setSelected(m.building_id)} className="text-left">
            <Card
              className={`h-full border-2 transition-all ${
                selected === m.building_id ? RANK_BORDER[m.rank ?? ""] : "border-border"
              } ${m.rank === "gold" ? "sm:scale-105" : ""}`}
            >
              <div className="mb-3 flex items-center gap-2.5">
                <RankMedal rank={m.rank} />
                <span className="text-sm font-semibold leading-snug">{m.address}</span>
              </div>
              <p className="text-3xl font-bold tracking-tight">{m.final_score}</p>
              <p className="text-xs text-muted">종합 매칭 점수</p>
            </Card>
          </button>
        ))}
      </div>

      {rest.length > 0 && (
        <div className="mb-8 space-y-2">
          {rest.map((m) => (
            <button
              key={m.building_id}
              onClick={() => setSelected(m.building_id)}
              className={`flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left transition-colors ${
                selected === m.building_id ? "border-accent bg-accent-soft" : "border-border bg-surface"
              }`}
            >
              <span className="font-medium">{m.address}</span>
              <span className="text-sm text-muted">{m.final_score}점</span>
            </button>
          ))}
        </div>
      )}

      {selectedMatch && breakdown && (
        <Card>
          <h2 className="mb-1 font-semibold">{selectedMatch.address}</h2>
          <p className="mb-5 text-sm leading-relaxed text-foreground">{selectedMatch.explanation}</p>
          <ScoreBarBreakdown breakdown={breakdown} factors={AGENT_ORDER} labels={AGENT_LABELS} />

          <Link
            href={`/diagnosis/${selectedMatch.building_id}`}
            className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-accent py-3 font-medium text-accent-foreground transition-opacity hover:opacity-90 sm:w-auto sm:px-8"
          >
            건물 상세 진단 보기 →
          </Link>
        </Card>
      )}
    </main>
  );
}
