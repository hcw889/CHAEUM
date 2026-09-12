import type { Page } from "@playwright/test";
import type { Building, BusinessFitCandidate, DashboardMetrics } from "../../lib/types";
import { buildings } from "./footfall";

const breakdown = Object.fromEntries(["foot_traffic", "competition_saturation", "demographic_fit", "building_condition"].flatMap((key) => [
  [`${key}_weight`, 0.25], [`${key}_raw_score`, 80], [`${key}_contribution`, 20],
]));
export const candidates: BusinessFitCandidate[] = [
  { type: "카페", fit_score: 80, rank: "gold", score_breakdown: breakdown, estimated_rent: 1000000, required_permits: ["영업신고", "위생교육"] },
  { type: "학원", fit_score: 70, rank: "silver", score_breakdown: breakdown, estimated_rent: 900000, required_permits: ["학원 등록"] },
  { type: "편의점", fit_score: 60, rank: "bronze", score_breakdown: breakdown, estimated_rent: 800000, required_permits: ["사업자 등록"] },
];
export const metrics: DashboardMetrics = { avg_competition_saturation: 30, avg_estimated_rent: 900000, avg_foot_traffic: 80, top_competition_type: "카페" };

export function analysisBuilding(id = "b1"): Building {
  return { ...buildings.find((building) => building.id === id)!, floor: 1, area_pyeong: 30, built_year: 2005, diagnosis: { aging_score: 75, accessibility_score: 85, lighting_score: 80 }, data_reference_month: "2026-09" };
}

export async function mockAnalysisApi(page: Page) {
  await page.route("**/api/buildings/**", (route) => {
    const url = new URL(route.request().url());
    const [, , , id, resource] = url.pathname.split("/");
    if (resource === "footfall") return route.fallback();
    if (!buildings.some((building) => building.id === id)) return route.fulfill({ status: 404, json: { detail: "없는 매물입니다." } });
    if (!resource) return route.fulfill({ json: analysisBuilding(id) });
    if (resource === "business-fit") return route.fulfill({ json: candidates });
    if (resource === "dashboard") return route.fulfill({ json: metrics });
    if (resource === "report") return route.fulfill({ json: { building: analysisBuilding(id), top_business: candidates[0], dashboard: metrics, generated_at: "2026-09-13" } });
    if (resource === "permits") return route.fulfill({ json: (candidates.find((candidate) => candidate.type === url.searchParams.get("business_type"))?.required_permits ?? []).map((label) => ({ label, checked: false })) });
    return route.fallback();
  });
}
