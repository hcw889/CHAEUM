"use client";

import { useSearchParams } from "next/navigation";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { saveRole, useStoredRole } from "./role";
import { ROLE_LABELS, type Role } from "./types";

/**
 * 매칭 flow에서 쓰는 role 컨텍스트.
 *
 * role은 두 곳에서 올 수 있다.
 *   1) URL 쿼리(`/match/new?role=brand`) — 온보딩에서 붙여 보내는 값. 첫 렌더부터
 *      확정되므로 role별 문구가 깜빡이지 않고, 링크 하나로 진입/테스트가 가능하다.
 *   2) localStorage — 새로고침이나 직접 URL 진입처럼 쿼리가 없는 경우의 폴백.
 *
 * 어느 쪽에서도 못 읽으면 기존 동작과 같게 "founder"로 둔다.
 */

const RoleContext = createContext<Role>("founder");

export function isRole(value: string | null | undefined): value is Role {
  return value != null && value in ROLE_LABELS;
}

/** 쿼리 > localStorage > founder 순으로 role을 해석한다. */
export function useResolvedRole(): Role {
  const queryRole = useSearchParams().get("role");
  // localStorage는 서버 렌더에서 읽을 수 없어 하이드레이션 후에 채워진다.
  // 쿼리가 있으면 그쪽이 이기므로 첫 렌더부터 role이 확정된다.
  const storedRole = useStoredRole();

  useEffect(() => {
    // 쿼리로 직접 진입한 경우에도 이후 화면(결과·시각화)이 같은 role을 보도록
    // 저장해 둔다. 온보딩을 거치지 않은 딥링크가 유일한 role 소스일 수 있다.
    if (isRole(queryRole)) saveRole(queryRole);
  }, [queryRole]);

  return isRole(queryRole) ? queryRole : storedRole ?? "founder";
}

export function RoleProvider({ role, children }: { role: Role; children: ReactNode }) {
  return <RoleContext.Provider value={role}>{children}</RoleContext.Provider>;
}

/** 컴포넌트 트리 어디서든 현재 role을 읽는다 (prop drilling 없이 문구 분기용). */
export function useRole(): Role {
  return useContext(RoleContext);
}
