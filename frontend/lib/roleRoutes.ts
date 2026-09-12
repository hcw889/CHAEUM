import type { Role } from "./types";

/**
 * 온보딩에서 role을 선택했을 때 최초로 이동할 경로.
 * 특정 role 전용 화면이 새로 생기면 이 매핑에 항목만 추가/교체하면 된다.
 *
 * - owner: 매물 입력 → 진단 결과 → 업종 추천 (기존 진단 flow)
 * - founder/brand: 조건 입력 → 매물 추천 (매칭 flow)
 * - official: 공실 현황 대시보드 (지역별 집계 조회)
 */
export const ROLE_ROUTES: Record<Role, string> = {
  owner: "/property/new",
  founder: "/match/new",
  brand: "/match/new",
  official: "/official",
};

export function getRoleRoute(role: Role): string {
  return ROLE_ROUTES[role];
}
