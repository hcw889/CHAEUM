import type {
  Building,
  BuildingSummary,
  BusinessFitCandidate,
  DashboardMetrics,
  MatchRequest,
  MatchResponse,
  PermitChecklistItem,
  PropertyInput,
  ReportSummary,
} from "./types";

import type { RegionStatsResponse } from "./regionTypes";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API 요청 실패 (${res.status}): ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getRegionStats: () => request<RegionStatsResponse>("/api/regions/stats"),
  listBuildings: () => request<BuildingSummary[]>("/api/buildings"),
  getBuilding: (id: string) => request<Building>(`/api/buildings/${id}`),
  diagnoseBuilding: (payload: PropertyInput) =>
    request<Building>("/api/buildings/diagnose", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getBusinessFit: (id: string) => request<BusinessFitCandidate[]>(`/api/buildings/${id}/business-fit`),
  getDashboard: (id: string) => request<DashboardMetrics>(`/api/buildings/${id}/dashboard`),
  getPermits: (id: string, businessType: string) =>
    request<PermitChecklistItem[]>(`/api/buildings/${id}/permits?business_type=${encodeURIComponent(businessType)}`),
  getReport: (id: string) => request<ReportSummary>(`/api/buildings/${id}/report`),
  listBusinessTypes: () => request<string[]>("/api/business-types"),
  matchBuildings: (payload: MatchRequest) =>
    request<MatchResponse>("/api/match", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
