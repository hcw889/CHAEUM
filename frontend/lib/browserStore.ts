"use client";

import { useSyncExternalStore } from "react";

/**
 * localStorage / sessionStorage 값을 React 상태처럼 읽는다.
 *
 * effect 안에서 setState로 브라우저 저장소를 읽으면 마운트마다 연쇄 렌더가 생기고
 * (react-hooks/set-state-in-effect), SSR 스냅샷도 표현할 수 없다. useSyncExternalStore는
 * "서버 스냅샷 = null, 클라이언트 스냅샷 = 실제 값"을 React가 직접 다루게 해준다.
 */

type StorageKind = "local" | "session";

function getStorage(kind: StorageKind): Storage | null {
  try {
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    // private 모드 등 저장소 접근 불가
    return null;
  }
}

/** 다른 탭에서의 변경만 알림이 온다 (같은 탭 내 변경은 페이지 전환으로 반영된다). */
function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

function readServer(): null {
  return null;
}

export function useStoredValue(kind: StorageKind, key: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => {
      try {
        return getStorage(kind)?.getItem(key) ?? null;
      } catch {
        return null;
      }
    },
    readServer,
  );
}

/** JSON으로 저장된 값을 읽는다. 파싱 실패 시 null. */
export function parseStored<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}
