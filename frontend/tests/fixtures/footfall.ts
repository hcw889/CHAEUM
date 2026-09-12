import type { Page } from "@playwright/test";
import type { DayType, FootfallResponse } from "../../lib/footfallTypes";
import type { BuildingSummary } from "../../lib/types";

export const buildings: BuildingSummary[] = [
  { id: "b1", name: "객사길 테스트 매물", address: "전주시 객사길 1", risk_grade: "안전", thumbnail_color: "#D8CFC4" },
  { id: "b2", name: "태평동 테스트 매물", address: "전주시 태평동 2", risk_grade: "주의", thumbnail_color: "#C8BFB4" },
];

export function footfallResponse(buildingId = "b1", dayType: DayType = "weekday"): FootfallResponse {
  const scale = (buildingId === "b2" ? 3 : 1) * (dayType === "weekend" ? 2 : 1);
  const building = buildings.find((item) => item.id === buildingId)!;
  const areas: FootfallResponse["areas"] = [
    { id: "north", name: "북쪽 상권", lat: 35.8205, lng: 127.1435, radius_m: 200, profile: "shopping", profile_label: "쇼핑", distance_m: 200, hourly: Array<number>(24).fill(100 * scale), daily_total: 2400 * scale, peak_hour: 0, share_pct: 60.8, is_mock: true, source: "mock", reference_month: null },
    { id: "south", name: "남쪽 상권", lat: 35.814, lng: 127.143, radius_m: 250, profile: "office", profile_label: "업무", distance_m: 650, hourly: Array.from({ length: 24 }, (_, h) => (h === 12 ? 400 : 50) * scale), daily_total: 1550 * scale, peak_hour: 12, share_pct: 39.2, is_mock: true, source: "mock", reference_month: null },
  ];

  return {
    building_id: buildingId, address: building.address, region: "전주시",
    mode: "mock", is_mock: true, source_label: "시연용 가상 유동인구", note: null, measured_count: 0,
    day_type: dayType, date: dayType === "weekday" ? "20260904" : "20260905",
    data_reference_month: "2026-09", description: "테스트용 유동인구",
    center_lat: 35.819, center_lng: 127.143, search_radius_m: 1500, areas,
    summary: { daily_total: 3950 * scale, peak_hour: 12, peak_area_name: "남쪽 상권", top_area_name: "북쪽 상권", walkable_total: 2400 * scale, max_area_daily: 2400 * scale },
  };
}

/** 외부 API·지도 타일과 무관하게 화면 이동과 유동인구 조작을 검증한다. */
export async function mockFootfallApi(page: Page) {
  await page.route("**/api/buildings", (route) => route.fulfill({ json: buildings }));
  await page.route("**/api/buildings/*/footfall?**", (route) => {
    const url = new URL(route.request().url());
    const id = url.pathname.split("/")[3];
    if (!buildings.some((building) => building.id === id)) {
      return route.fulfill({ status: 404, json: { detail: "매물을 찾지 못했습니다." } });
    }
    return route.fulfill({ json: footfallResponse(id, url.searchParams.get("day_type") as DayType) });
  });
  await page.route("https://tile.openstreetmap.org/**", (route) => route.abort());
}
