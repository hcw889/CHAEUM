"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { Skeleton } from "@/components/Skeleton";
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

      <h1 className="mb-1 text-2xl font-bold tracking-tight">인허가 체크리스트</h1>
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
                  businessType === c.type ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface text-muted"
                }`}
              >
                {c.type}
              </button>
            ))}
          </div>

          <Card>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold">{businessType} 필요 인허가</h2>
              <span className="text-sm text-muted">
                {doneCount} / {permits.length} 완료
              </span>
            </div>
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
                    <span className={checked[p.label] ? "text-muted line-through" : ""}>{p.label}</span>
                  </label>
                </li>
              ))}
            </ul>
          </Card>

          <Link
            href={`/strategy/${id}`}
            className="mt-8 inline-flex w-full items-center justify-center rounded-md bg-accent py-3 font-medium text-accent-foreground transition-opacity hover:opacity-90 sm:w-auto sm:px-8"
          >
            전략 그리드 보기 →
          </Link>
        </>
      )}
    </main>
  );
}
