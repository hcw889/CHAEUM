"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { Skeleton } from "@/components/Skeleton";
import { Tag } from "@/components/Tag";
import { api } from "@/lib/api";
import type { BusinessFitCandidate, PermitChecklistItem } from "@/lib/types";

export default function PermitsPage() {
  const { id } = useParams<{ id: string }>();
  const [candidates, setCandidates] = useState<BusinessFitCandidate[] | null>(null);
  const [businessType, setBusinessType] = useState<string | null>(null);
  const [permits, setPermits] = useState<PermitChecklistItem[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getBusinessFit(id)
      .then((data) => {
        setCandidates(data);
        setBusinessType(data[0]?.type ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "불러오기 실패"));
  }, [id]);

  useEffect(() => {
    if (!businessType) return;
    api
      .getPermits(id, businessType)
      .then((items) => {
        setPermits(items);
        setChecked({});
      })
      .catch(() => setPermits([]));
  }, [id, businessType]);

  if (error) return <main className="mx-auto max-w-3xl px-6 py-10 text-danger">{error}</main>;

  const doneCount = Object.values(checked).filter(Boolean).length;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />

      <div className="mb-1 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight">인허가 체크리스트</h1>
        {candidates && (
          <span className="inline-flex items-center rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-accent-text">
            {doneCount} / {permits.length} 완료
          </span>
        )}
      </div>
      <p className="mb-6 text-sm text-muted">선택한 업종을 창업할 때 필요한 인허가 항목입니다.</p>

      {!candidates ? (
        <>
          <div className="mb-5 flex flex-wrap gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-20 rounded-full" />
            ))}
          </div>
          <Card>
            <Skeleton className="mb-4 h-5 w-32" />
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="mb-3 h-11 w-full" />
            ))}
          </Card>
        </>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap gap-2">
            {candidates.map((c) => (
              <button
                key={c.type}
                onClick={() => setBusinessType(c.type)}
                className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
                  businessType === c.type ? "border-accent bg-accent-soft text-accent-text" : "border-border bg-surface text-muted"
                }`}
              >
                {c.type}
              </button>
            ))}
          </div>

          <Card>
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Checklist</p>
            <h2 className="mb-4 text-lg font-bold">{businessType} 필요 인허가</h2>
            <ul className="space-y-3">
              {permits.map((p) => (
                <li key={p.label}>
                  <label className="flex cursor-pointer items-center gap-3 rounded-md border border-border px-4 py-3 hover:border-accent">
                    <input
                      type="checkbox"
                      checked={!!checked[p.label]}
                      onChange={(e) => setChecked((prev) => ({ ...prev, [p.label]: e.target.checked }))}
                      className="h-4 w-4 accent-[var(--accent)]"
                    />
                    <span className={`flex-1 ${checked[p.label] ? "text-muted line-through" : ""}`}>{p.label}</span>
                    <Tag tone="neutral">필수</Tag>
                    <Tag tone={checked[p.label] ? "done" : "pending"}>{checked[p.label] ? "완료" : "대기"}</Tag>
                  </label>
                </li>
              ))}
            </ul>
          </Card>

          {permits.length > 0 && (
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Card>
                <p className="mb-3 text-sm font-semibold text-muted">완료 항목</p>
                {permits.filter((p) => checked[p.label]).length === 0 ? (
                  <p className="text-sm text-muted">아직 완료한 항목이 없습니다.</p>
                ) : (
                  <ul className="space-y-2 text-sm text-foreground">
                    {permits
                      .filter((p) => checked[p.label])
                      .map((p) => (
                        <li key={p.label} className="flex items-center gap-2">
                          <span aria-hidden className="text-accent-text">✓</span>
                          {p.label}
                        </li>
                      ))}
                  </ul>
                )}
              </Card>
              <Card>
                <p className="mb-3 text-sm font-semibold text-muted">남은 항목</p>
                {permits.filter((p) => !checked[p.label]).length === 0 ? (
                  <p className="text-sm text-muted">모든 인허가 항목을 완료했습니다.</p>
                ) : (
                  <ul className="space-y-2 text-sm text-foreground">
                    {permits
                      .filter((p) => !checked[p.label])
                      .map((p) => (
                        <li key={p.label} className="flex items-center gap-2">
                          <span aria-hidden className="text-muted">·</span>
                          {p.label}
                        </li>
                      ))}
                  </ul>
                )}
              </Card>
            </div>
          )}

          <Link
            href={`/strategy/${id}`}
            className="mt-8 inline-flex w-full items-center justify-center rounded-2xl bg-brand-gradient py-3 font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand sm:w-auto sm:px-8"
          >
            전략 그리드 보기 →
          </Link>
        </>
      )}
    </main>
  );
}
