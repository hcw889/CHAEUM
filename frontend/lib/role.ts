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
