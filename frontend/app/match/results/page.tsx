"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Wordmark } from "@/components/Logo";
import { RankMedal } from "@/components/RankMedal";
import MatchDetailDialog from "@/components/match/MatchDetailDialog";
import MatchMap from "@/components/match/MatchMap";
import { api } from "@/lib/api";
import { parseStored, useStoredValue } from "@/lib/browserStore";
import { formatScore } from "@/lib/format";
import { hasMapLocation, RANK_NUMBERS } from "@/lib/matchMap";
import { useStoredRole } from "@/lib/role";
import { getRoleCopy } from "@/lib/roleCopy";
import type { BuildingLocation, MatchCandidate, MatchRequest, MatchResponse } from "@/lib/types";

export default function MatchResultsPage() {
  const router = useRouter();
  const role = useStoredRole();
  const requestRaw = useStoredValue("session", "chaeum_match_request");
  const resultRaw = useStoredValue("session", "chaeum_match_result");
  const request = useMemo(() => parseStored<MatchRequest>(requestRaw), [requestRaw]);
  const result = useMemo(() => parseStored<MatchResponse>(resultRaw), [resultRaw]);
  const matches = useMemo(() => result?.matches ?? null, [result]);

  // 매물 카드나 지도 마커를 선택하면 상세 팝업을 연다.
  const [picked, setPicked] = useState<string | null>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [locations, setLocations] = useState<{
    source: MatchCandidate[]; reloadKey: number; data: Record<string, BuildingLocation>; failed?: boolean;
  } | null>(null);
  const needsLocations = matches?.some((match) => match.location === undefined) ?? false;

  useEffect(() => {
    if (!requestRaw || !resultRaw) {
      // SSR 스냅샷이 null인 첫 렌더에서는 실제 저장소를 한 번 더 확인한다.
      try {
        if (!parseStored<MatchRequest>(sessionStorage.getItem("chaeum_match_request"))
          || !parseStored<{ matches: MatchCandidate[] }>(sessionStorage.getItem("chaeum_match_result"))) {
          router.replace("/match/new");
        }
      } catch { router.replace("/match/new"); }
    } else if (!request || !matches) {
      router.replace("/match/new");
    }
  }, [requestRaw, resultRaw, request, matches, router]);

  useEffect(() => {
    if (!needsLocations || !matches) return;
    let cancelled = false;
    api.listBuildingLocations().then((data) => {
      if (!cancelled) setLocations({ source: matches, reloadKey, data });
    }).catch(() => {
      if (!cancelled) setLocations({ source: matches, reloadKey, data: {}, failed: true });
    });
    return () => { cancelled = true; };
  }, [needsLocations, matches, reloadKey]);

  const currentLocations = locations?.source === matches && locations.reloadKey === reloadKey ? locations : null;
  const resolved = useMemo(() => (matches ?? []).map((match) => (
    match.location !== undefined ? match : { ...match, location: currentLocations?.data[match.building_id] ?? null }
  )), [matches, currentLocations]);
  const top3 = useMemo(() => resolved.filter((match) => match.rank).slice(0, 3), [resolved]);
  const rest = useMemo(() => resolved.filter((match) => !top3.includes(match)), [resolved, top3]);
  const selectedMatch = resolved.find((match) => match.building_id === picked) ?? null;
  const openMatch = useCallback((id: string) => {
    trigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setPicked(id);
  }, []);
  const closeMatch = useCallback(() => {
    setPicked(null);
    requestAnimationFrame(() => {
      if (trigger.current?.isConnected) trigger.current.focus({ preventScroll: true });
    });
  }, []);
  const loadingLocations = needsLocations && !currentLocations;
  const hasApproximate = top3.some((match) => match.location?.is_approximate);
  const missingLocations = top3.filter((match) => !hasMapLocation(match)).length;

  if (!matches || !request) {
    return <main className="flex min-h-dvh items-center justify-center text-sm text-muted" role="status">추천 결과를 불러오고 있습니다…</main>;
  }

  return (
    <main className="w-full flex-1 px-4 pb-5 pt-4 sm:px-6 lg:px-8">
      <header className="mb-4 flex items-center justify-between gap-4">
        <Link href="/" className="text-lg"><Wordmark /></Link>
        <Link href="/match/new" className="rounded-full border border-border bg-surface px-4 py-2 text-xs font-semibold text-muted hover:text-foreground">조건 다시 입력 →</Link>
      </header>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{getRoleCopy(role).resultsTitle}</h1>
          <p className="mt-1 text-xs text-muted sm:text-sm">{request.business_type} · {request.region_pref} · {request.priority} 기준</p>
        </div>
        <p className="text-xs text-muted">지도 위 매물을 눌러 추천 이유를 확인해 보세요.</p>
      </div>

      {result?.source_note && (
        <div
          className={`mb-6 rounded-lg border p-4 text-xs leading-relaxed ${
            result.data_mode === "real"
              ? "border-brand-200 bg-brand-50 text-accent-text"
              : "border-amber-200 bg-amber-50 text-amber-800"
          }`}
        >
          <p className="mb-1 font-semibold">
            {result.data_mode === "real" ? "공공데이터 기반 공실 추정" : "공실 추정 매물"}
            {result.data_mode === "real" && result.total_candidates != null && (
              <> · 조건 만족 매물 {result.total_candidates}건</>
            )}
          </p>
          <p>{result.source_note}</p>
        </div>
      )}

      {resolved.length === 0 ? (
        <div className="rounded-2xl border border-border bg-surface p-10 text-center">
          <p className="font-semibold">추천할 매물을 찾지 못했습니다.</p>
          <Link href="/match/new" className="mt-3 inline-block text-sm text-accent-text underline">조건 다시 입력</Link>
        </div>
      ) : (
        <section className="match-results-stage" aria-label="추천 매물">
          <MatchMap matches={top3} onSelect={openMatch} loading={loadingLocations} />
          <div className="match-overview-badge rounded-full border border-border bg-surface px-4 py-2 text-xs font-bold shadow-sm">
            추천 TOP 3
          </div>
          <div className="match-overview-cards">
            {top3.map((match) => (
              <button
                key={match.building_id}
                type="button"
                className="match-summary-card"
                aria-label={`추천 ${RANK_NUMBERS[match.rank!]}위 카드 상세 보기`}
                aria-haspopup="dialog"
                onClick={() => openMatch(match.building_id)}
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <RankMedal rank={match.rank} />
                  <span className="text-2xl font-black text-accent-text">
                    {formatScore(match.final_score)}<span className="ml-1 text-xs font-normal text-muted">점</span>
                  </span>
                </div>
                <p className="truncate text-sm font-semibold">{match.address}</p>
                {(match.area_pyeong || match.built_year) && (
                  <p className="mt-2 text-xs text-muted">
                    {match.area_pyeong ? `${match.area_pyeong}평` : null}
                    {match.area_pyeong && match.built_year ? " · " : null}
                    {match.built_year ? `${match.built_year}년 준공` : null}
                  </p>
                )}
                <p className="mt-2 flex items-center justify-between text-[11px] text-muted">
                  <span>{hasMapLocation(match) ? "위치와 추천 근거 확인" : loadingLocations ? "위치 확인 중 · 추천 근거 보기" : "위치 미확인 · 추천 근거 보기"}</span>
                  <span aria-hidden>↗</span>
                </p>
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted">
        {hasApproximate && <p>대표 좌표로 표시한 매물입니다. 실제 건물 위치와 다를 수 있습니다.</p>}
        {loadingLocations && <p role="status">저장된 추천 매물의 위치를 확인하고 있습니다…</p>}
        {!loadingLocations && missingLocations > 0 && (
          <p role="status">
            위치를 확인하지 못한 매물 {missingLocations}건은 추천 카드에서 상세를 볼 수 있습니다.
            {currentLocations?.failed && <button type="button" onClick={() => setReloadKey((key) => key + 1)} className="ml-2 text-accent-text underline">위치 다시 불러오기</button>}
          </p>
        )}
      </div>

      {rest.length > 0 && (
        <details className="mt-5 rounded-2xl border border-border bg-surface p-4">
          <summary className="cursor-pointer text-sm font-semibold">다른 추천 매물 {rest.length}개 보기</summary>
          <div className="mt-3 space-y-2">
            {rest.map((match) => (
              <button
                key={match.building_id}
                type="button"
                onClick={() => openMatch(match.building_id)}
                aria-haspopup="dialog"
                className="flex w-full items-center justify-between gap-3 rounded-md border border-border px-4 py-3 text-left transition-colors hover:bg-accent-soft"
              >
                <span className="font-medium">{match.address}</span>
                <span className="shrink-0 text-sm text-muted">{formatScore(match.final_score)}점</span>
              </button>
            ))}
          </div>
        </details>
      )}
      {selectedMatch && <MatchDetailDialog key={selectedMatch.building_id} match={selectedMatch} priority={request.priority} onClose={closeMatch} />}
    </main>
  );
}
