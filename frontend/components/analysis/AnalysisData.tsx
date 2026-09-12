"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { Building, BusinessFitCandidate, DashboardMetrics, ReportSummary } from "@/lib/types";

/** Keep each request for this building mounted while the reader moves between sections. */
export function useAnalysisResource<T>(load: () => Promise<T>) {
  const pending = useRef<Promise<T> | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ data: T | null; error: string | null }>({ data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    // React Strict Mode replays effects; reuse the in-flight request as well as its result.
    pending.current ??= load();
    pending.current.then(
      (data) => { if (!cancelled) setState({ data, error: null }); },
      (error) => { if (!cancelled) setState({ data: null, error: error instanceof Error ? error.message : "불러오기 실패" }); },
    );
    return () => { cancelled = true; };
  }, [load, attempt]);

  const retry = useCallback(() => {
    pending.current = null;
    setState({ data: null, error: null });
    setAttempt((value) => value + 1);
  }, []);

  return useMemo(() => ({ ...state, retry }), [state, retry]);
}

type Resource<T> = ReturnType<typeof useAnalysisResource<T>>;
interface AnalysisData {
  buildingId: string;
  building: Resource<Building>;
  candidates: Resource<BusinessFitCandidate[]>;
  dashboard: Resource<DashboardMetrics>;
  report: Resource<ReportSummary>;
}
const Context = createContext<AnalysisData | null>(null);

// The parent keys this provider by buildingId so data and local controls reset together.
export function AnalysisProvider({ buildingId, children }: { buildingId: string; children: ReactNode }) {
  const building = useAnalysisResource(useCallback(() => api.getBuilding(buildingId), [buildingId]));
  const candidates = useAnalysisResource(useCallback(() => api.getBusinessFit(buildingId), [buildingId]));
  const dashboard = useAnalysisResource(useCallback(() => api.getDashboard(buildingId), [buildingId]));
  const report = useAnalysisResource(useCallback(() => api.getReport(buildingId), [buildingId]));
  const value = useMemo(() => ({ buildingId, building, candidates, dashboard, report }), [buildingId, building, candidates, dashboard, report]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAnalysis() {
  const data = useContext(Context);
  if (!data) throw new Error("AnalysisProvider is required");
  return data;
}

export function AnalysisError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-border bg-surface p-6">
      <p className="font-semibold">이 정보를 불러오지 못했습니다.</p>
      <p className="mt-2 break-words text-sm text-muted">{message}</p>
      <button type="button" onClick={onRetry} className="mt-4 rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-accent-soft">다시 불러오기</button>
    </div>
  );
}
