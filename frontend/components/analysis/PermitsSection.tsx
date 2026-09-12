"use client";

import { useCallback, useState } from "react";
import { Card } from "@/components/Card";
import { SkeletonCardGrid } from "@/components/Skeleton";
import { Tag } from "@/components/Tag";
import { api } from "@/lib/api";
import { AnalysisError, useAnalysis, useAnalysisResource } from "./AnalysisData";

export default function PermitsSection() {
  const { buildingId, candidates: { data: candidates, error, retry } } = useAnalysis();
  const [picked, setPicked] = useState<string | null>(null);
  const businessType = picked ?? candidates?.[0]?.type ?? null;
  if (error) return <AnalysisError message={error} onRetry={retry} />;
  return (
    <div>
      <p className="mb-6 text-sm text-muted">선택한 업종을 창업할 때 필요한 인허가 항목입니다.</p>
      {!candidates ? <SkeletonCardGrid count={2} /> : (
        <>
          <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="인허가 업종 선택">
            {candidates.map((candidate) => (
              <button key={candidate.type} type="button" aria-pressed={businessType === candidate.type} onClick={() => setPicked(candidate.type)}
                className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${businessType === candidate.type ? "border-accent bg-accent-soft text-accent-text" : "border-border bg-surface text-muted"}`}>
                {candidate.type}
              </button>
            ))}
          </div>
          {businessType ? <PermitChecklist key={`${buildingId}:${businessType}`} buildingId={buildingId} businessType={businessType} /> : <p className="text-sm text-muted">인허가를 확인할 업종이 없습니다.</p>}
        </>
      )}
    </div>
  );
}

function PermitChecklist({ buildingId, businessType }: { buildingId: string; businessType: string }) {
  const { data: permits, error, retry } = useAnalysisResource(useCallback(() => api.getPermits(buildingId, businessType), [buildingId, businessType]));
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  if (error) return <AnalysisError message={error} onRetry={retry} />;
  if (!permits) return <SkeletonCardGrid count={2} />;
  const complete = permits.filter((permit) => checked[permit.label] ?? permit.checked);
  const remaining = permits.filter((permit) => !(checked[permit.label] ?? permit.checked));
  return (
    <>
      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Checklist</p>
            <h3 className="text-lg font-bold">{businessType} 필요 인허가</h3>
          </div>
          <span className="rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-accent-text">{complete.length} / {permits.length} 완료</span>
        </div>
        {permits.length === 0 && <p className="text-sm text-muted">등록된 인허가 항목이 없습니다.</p>}
        <ul className="space-y-3">
          {permits.map((permit) => {
            const done = checked[permit.label] ?? permit.checked;
            return (
              <li key={permit.label}>
                <label className="flex cursor-pointer items-center gap-3 rounded-md border border-border px-4 py-3 hover:border-accent">
                  <input type="checkbox" checked={done} onChange={(event) => setChecked((previous) => ({ ...previous, [permit.label]: event.target.checked }))} className="h-4 w-4 shrink-0 accent-[var(--accent)]" />
                  <span className={`min-w-0 flex-1 ${done ? "text-muted line-through" : ""}`}>{permit.label}</span>
                  <Tag tone="neutral">필수</Tag><Tag tone={done ? "done" : "pending"}>{done ? "완료" : "대기"}</Tag>
                </label>
              </li>
            );
          })}
        </ul>
      </Card>
      {permits.length > 0 && (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {[{ title: "완료 항목", items: complete, empty: "아직 완료한 항목이 없습니다." }, { title: "남은 항목", items: remaining, empty: "모든 인허가 항목을 완료했습니다." }].map(({ title, items, empty }) => (
            <Card key={title}>
              <h3 className="mb-3 text-sm font-semibold text-muted">{title}</h3>
              {items.length === 0 ? <p className="text-sm text-muted">{empty}</p> : <ul className="list-inside list-disc space-y-2 text-sm">{items.map((item) => <li key={item.label}>{item.label}</li>)}</ul>}
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
