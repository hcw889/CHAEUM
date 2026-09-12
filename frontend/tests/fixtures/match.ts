import type { Page } from "@playwright/test";
import type { MatchCandidate, MatchRequest } from "../../lib/types";

export const matchRequest: MatchRequest = {
  business_type: "카페", budget: { deposit: 10000000, monthly_rent: 1000000 },
  region_pref: "상관없음", priority: "매출잠재력",
};

export const mapMatches: MatchCandidate[] = [
  {
    building_id: "b1", address: "전주시 객사길 1", final_score: 71.8, rank: "gold",
    agent_scores: { budget: 39, market_fit: 79, condition: 83 },
    explanation: "방문 고객과 건물 상태가 계획한 카페에 적합합니다.",
    location: { lat: 35.818, lng: 127.143, is_approximate: true },
    space_vision: { exposure_score: 59, accessibility_score: 60, popup_fit_score: 60, detected_elements: ["쇼윈도 2개", "간판 있음", "유동인구 보통"], visual_summary: "외부 노출성은 다소 제한적입니다. 접근성은 무난한 수준입니다." },
  },
  {
    building_id: "b2", address: "전주시 태평동 2", final_score: 66.6, rank: "silver",
    agent_scores: { budget: 76, market_fit: 61, condition: 74 },
    explanation: "주거지와 가까워 단골 고객 확보를 기대할 수 있습니다.",
    location: { lat: 35.826, lng: 127.138, is_approximate: true },
  },
  {
    building_id: "b3", address: "전주시 경원동 3", final_score: 60.6, rank: "bronze",
    agent_scores: { budget: 86, market_fit: 51, condition: 64 },
    explanation: "임대 예산 안에서 시작할 수 있는 매물입니다.",
    location: { lat: 35.818, lng: 127.152, is_approximate: true },
  },
  {
    building_id: "b4", address: "전주시 노송동 4", final_score: 55, rank: null,
    agent_scores: { budget: 60, market_fit: 50, condition: 65 },
    explanation: "추가로 비교할 수 있는 매물입니다.",
    location: { lat: 35.8235, lng: 127.1487, is_approximate: true },
  },
];

export async function seedMatchResults(page: Page, matches = mapMatches) {
  await page.addInitScript(({ request, matches }) => {
    sessionStorage.setItem("chaeum_match_request", JSON.stringify(request));
    sessionStorage.setItem("chaeum_match_result", JSON.stringify({ matches }));
  }, { request: matchRequest, matches });
}

/** 지도 타일 네트워크와 무관하게 마커·지도 배치·모달 동작을 검증한다. */
export async function mockMapTiles(page: Page) {
  await page.route("https://tile.openstreetmap.org/**", (route) => route.fulfill({
    contentType: "image/gif",
    body: Buffer.from("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7", "base64"),
  }));
}
