import type {
  Building,
  BuildingLocation,
  BuildingSummary,
  BusinessFitCandidate,
  DashboardMetrics,
  MatchOptions,
  MatchRequest,
  MatchResponse,
  PermitChecklistItem,
  PropertyInput,
  ReportSummary,
} from "./types";

import type { RegionStatsResponse } from "./regionTypes";
import type { DayType, FootfallResponse } from "./footfallTypes";

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
  listBuildingLocations: () => request<Record<string, BuildingLocation>>("/api/buildings/locations"),
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
  // 매칭 입력 화면의 선택지. 실데이터에서는 매물이 존재하는 지역만 내려온다.
  getMatchOptions: () => request<MatchOptions>("/api/match/options"),
  getFootfall: (id: string, dayType: DayType) =>
    request<FootfallResponse>(`/api/buildings/${id}/footfall?day_type=${dayType}`),
};
