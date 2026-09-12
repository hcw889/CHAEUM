import { useStoredValue } from "./browserStore";
import type { Role } from "./types";

const ROLE_KEY = "chaeum_role";

export function saveRole(role: Role) {
  try {
    localStorage.setItem(ROLE_KEY, role);
  } catch {
    // localStorage 접근 불가 시 무시 (private 모드 등)
  }
}

export function loadRole(): Role | null {
  try {
    const value = localStorage.getItem(ROLE_KEY);
    return (value as Role) ?? null;
  } catch {
    return null;
  }
}

/**
 * 저장된 role을 렌더 중에 읽는다. effect + setState 없이 쓰기 위한 훅이며,
 * 서버 렌더에서는 null이고 하이드레이션 후 실제 값으로 바뀐다.
 */
export function useStoredRole(): Role | null {
  return (useStoredValue("local", ROLE_KEY) as Role | null) ?? null;
}
