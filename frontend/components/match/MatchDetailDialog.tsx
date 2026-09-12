"use client";

import Link from "next/link";
import { useEffect, useId, useMemo, useRef } from "react";
import { RadialGauge } from "@/components/RadialGauge";
import { RankMedal } from "@/components/RankMedal";
import { Tag } from "@/components/Tag";
import VacancyEvidence from "@/components/VacancyEvidence";
import RoadviewPanel from "@/components/RoadviewPanel";
import { formatPercent, formatScore } from "@/lib/format";
import type { MatchAgentScores, MatchCandidate } from "@/lib/types";
import MatchMap from "./MatchMap";

const PRIORITY_WEIGHTS: Record<string, MatchAgentScores> = {
  예산절약: { budget: 0.5, market_fit: 0.3, condition: 0.2 },
  매출잠재력: { budget: 0.2, market_fit: 0.6, condition: 0.2 },
  건물안정성: { budget: 0.2, market_fit: 0.2, condition: 0.6 },
};
const AGENTS: { key: keyof MatchAgentScores; label: string; icon: string }[] = [
  { key: "budget", label: "예산 적합도", icon: "💰" },
  { key: "market_fit", label: "상권 적합도", icon: "📍" },
  { key: "condition", label: "건물 컨디션", icon: "🏢" },
];

export default function MatchDetailDialog({ match, priority, onClose }: {
  match: MatchCandidate;
  priority: string;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const selected = useMemo(() => [match], [match]);
  const weights = PRIORITY_WEIGHTS[priority] ?? { budget: 1 / 3, market_fit: 1 / 3, condition: 1 / 3 };

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const previousOverflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      element.close();
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  return (
    <dialog
      ref={dialog}
      className="match-detail-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const focusable = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )).filter((element) => element.getClientRects().length > 0);
        const first = focusable[0];
        const last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <article className="match-detail-shell">
        <header className="match-detail-header">
          <RankMedal rank={match.rank} />
          <div className="min-w-0 flex-1">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted">YOUR NEXT PLACE</p>
            <h2 id={titleId} className="text-base font-bold sm:text-lg">{match.address}</h2>
          </div>
          <div className="hidden shrink-0 text-right sm:block">
            <p className="text-[11px] text-muted">종합 매칭 점수</p>
            <p className="text-2xl font-black text-accent-text">{formatScore(match.final_score)}<span className="ml-1 text-xs font-normal text-muted">점</span></p>
          </div>
          <button type="button" className="match-detail-close" aria-label="매물 상세 닫기" onClick={onClose} autoFocus>×</button>
        </header>

        <div className="match-detail-content">
          <div className="match-detail-map">
            <MatchMap matches={selected} detail />
            <div className="match-detail-map-caption">
              <span className="mb-2 block text-[10px] font-bold uppercase tracking-[0.15em] text-accent-text">LOCATION CLOSE-UP</span>
              <p className="text-sm font-semibold">{match.address}</p>
              <p className="mt-1 text-xs text-muted">
                {match.location?.is_approximate ? "시연용 대표 위치 · 실제 건물 위치와 다를 수 있습니다." : "선택한 매물 주변을 확대해 살펴보세요."}
              </p>
            </div>
          </div>

          <div className="match-detail-copy">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">Why This Match</p>
            <h3 className="mt-1 text-xl font-bold">왜 이 매물?</h3>
            <p className="mb-5 mt-2 text-sm leading-relaxed text-muted">{match.explanation}</p>

            <VacancyEvidence match={match} />

            <div className="match-reasons-grid">
              {AGENTS.map((agent) => (
                <section key={agent.key} className="match-reason-card text-center" aria-label={agent.label}>
                  <h4 className="mb-3 flex items-center justify-center gap-2 text-sm font-semibold">
                    <span aria-hidden>{agent.icon}</span>{agent.label}
                  </h4>
                  <div className="mb-3 flex justify-center"><RadialGauge value={match.agent_scores[agent.key]} label="점수" /></div>
                  <p className="text-[11px] text-muted">이번 추천에서 가중치 {formatPercent(weights[agent.key] * 100, 0)} 반영</p>
                </section>
              ))}
              <section className="match-reason-card" aria-label="AI Space Vision">
                <h4 className="mb-4 flex items-center gap-2 text-sm font-semibold"><span aria-hidden>🖼️</span>AI Space Vision</h4>
                {match.space_vision ? (
                  <>
                    <div className="mb-3 flex flex-wrap gap-1.5">
                      <Tag>노출 {formatScore(match.space_vision.exposure_score)}</Tag>
                      <Tag>접근 {formatScore(match.space_vision.accessibility_score)}</Tag>
                      <Tag>팝업 {formatScore(match.space_vision.popup_fit_score)}</Tag>
                    </div>
                    <p className="text-xs leading-relaxed text-muted">{match.space_vision.visual_summary}</p>
                  </>
                ) : <p className="text-xs leading-relaxed text-muted">이 매물의 공간 분석 정보는 아직 제공되지 않습니다.</p>}
              </section>
            </div>

            {match.space_vision && <p className="mt-4 text-xs leading-relaxed text-muted">{match.space_vision.detected_elements.join(" · ")}</p>}
            <div className="mt-6">
              <RoadviewPanel lat={match.lat} lng={match.lng} address={match.address} fallbackSrc={match.photo_url} />
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href={`/diagnosis/${match.building_id}`} className="match-detail-primary">건물 상세 진단 보기 →</Link>
              <Link href={`/visualize/${match.building_id}`} className="match-detail-secondary">주변 유동인구 보기 →</Link>
            </div>
          </div>
        </div>
      </article>
    </dialog>
  );
}
