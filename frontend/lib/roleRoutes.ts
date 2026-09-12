import type { Role } from "./types";

/**
 * 온보딩에서 role을 선택했을 때 최초로 이동할 경로.
 * 특정 role 전용 화면이 새로 생기면 이 매핑에 항목만 추가/교체하면 된다.
 *
 * - owner: 매물 입력 → 진단 결과 → 업종 추천 (기존 진단 flow)
 * - founder/brand: 조건 입력 → 매물 추천 (매칭 flow, 두 role이 동일 화면을 공유)
 * - official: 공실 현황 대시보드 (지역별 집계 조회)
 *
 * 매칭 flow로 갈 때는 `?role=`을 붙여 보낸다. 목적지 화면이 첫 렌더부터 role을
 * 알 수 있어야 role별 문구가 깜빡이지 않기 때문이다 (lib/roleContext.tsx 참고).
 */
export const ROLE_ROUTES: Record<Role, string> = {
  owner: "/property/new",
  founder: "/match/new",
  brand: "/match/new",
  official: "/official",
};

const ROLE_QUERY_ROUTES = new Set(["/match/new"]);

export function getRoleRoute(role: Role): string {
  const path = ROLE_ROUTES[role];
  return ROLE_QUERY_ROUTES.has(path) ? `${path}?role=${role}` : path;
}
