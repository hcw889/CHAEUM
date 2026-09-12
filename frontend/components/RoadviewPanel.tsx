"use client";

import { useEffect, useRef, useState } from "react";

// 카카오 지도 SDK는 @types 패키지가 없어, 이 컴포넌트가 실제로 쓰는 표면만
// 최소한으로 선언한다.
interface KakaoLatLng {
  getLat(): number;
  getLng(): number;
}

interface KakaoRoadview {
  getPosition(): KakaoLatLng;
  setPanoId(panoId: number, position: KakaoLatLng): void;
  setViewpoint(viewpoint: { pan: number; tilt: number; zoom: number }): void;
  relayout(): void;
}

interface KakaoRoadviewClient {
  getNearestPanoId(
    position: KakaoLatLng,
    radius: number,
    callback: (panoId: number | null) => void,
  ): void;
}

interface KakaoAddressResult {
  x: string; // 경도
  y: string; // 위도
}

interface KakaoMaps {
  load(callback: () => void): void;
  LatLng: new (lat: number, lng: number) => KakaoLatLng;
  Roadview: new (container: HTMLElement) => KakaoRoadview;
  RoadviewClient: new () => KakaoRoadviewClient;
  event: {
    addListener(target: object, type: string, handler: () => void): void;
    removeListener(target: object, type: string, handler: () => void): void;
  };
  services: {
    Geocoder: new () => {
      addressSearch(
        address: string,
        callback: (result: KakaoAddressResult[], status: string) => void,
      ): void;
    };
    Status: { OK: string };
  };
}

declare global {
  interface Window {
    kakao?: { maps: KakaoMaps };
  }
}

// SDK는 앱 전체에서 한 번만 로드한다. 매물을 바꿔 누를 때마다 script 태그가
// 늘어나는 것을 막는다.
let sdkPromise: Promise<void> | null = null;

class RoadviewSetupError extends Error {}

function loadKakaoSdk(): Promise<void> {
  if (sdkPromise) return sdkPromise;
  const key = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY?.trim();
  if (!key && !window.kakao?.maps) return Promise.reject(new RoadviewSetupError("로드뷰 연결 미설정"));
  let script: HTMLScriptElement | undefined;
  sdkPromise = new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => fail(), 15000);
    const fail = () => { window.clearTimeout(timeout); reject(new Error("Kakao SDK 로드 실패")); };
    const initialize = () => {
      try {
        const maps = window.kakao?.maps;
        if (!maps) { fail(); return; }
        maps.load(() => {
          if (!maps.Roadview || !maps.RoadviewClient || !maps.services?.Geocoder) { fail(); return; }
          window.clearTimeout(timeout);
          resolve();
        });
      } catch { fail(); }
    };
    if (window.kakao?.maps) { initialize(); return; }
    script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key!)}&libraries=services&autoload=false`;
    script.async = true;
    script.onload = initialize;
    script.onerror = fail;
    document.head.appendChild(script);
  }).catch((error: unknown) => {
    script?.remove();
    sdkPromise = null;
    throw error;
  });
  return sdkPromise;
}

/** 두 좌표 사이의 방위각(도). 촬영 지점에서 매물 쪽으로 시점을 돌리는 데 쓴다. */
function bearing(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const p1 = toRad(lat1);
  const p2 = toRad(lat2);
  const dl = toRad(lng2 - lng1);
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

type Status = "loading" | "ready" | "unavailable" | "error" | "unconfigured";

interface Props { lat?: number; lng?: number; address: string }

function validCoordinates(lat?: number, lng?: number): boolean {
  return Number.isFinite(lat) && Math.abs(lat!) <= 90 && Number.isFinite(lng) && Math.abs(lng!) <= 180;
}

/**
 * 매물 위치의 카카오 로드뷰. 좌표·주소 변경과 재시도 시 내부 뷰를 새로 생성한다.
 * 연결 실패를 임시 사진으로 대체하지 않고 원인 안내와 외부 지도 링크를 제공한다.
 */
export default function RoadviewPanel(props: Props) {
  const [attempt, setAttempt] = useState(0);
  return <RoadviewSession key={`${props.lat}:${props.lng}:${props.address}:${attempt}`} {...props} onRetry={() => setAttempt((value) => value + 1)} />;
}

function RoadviewSession({ lat, lng, address, onRetry }: Props & { onRetry: () => void }) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;
    let roadview: KakaoRoadview | undefined;
    let onInit: (() => void) | undefined;
    let resize: ResizeObserver | undefined;
    const element = container.current;
    const timeout = window.setTimeout(() => {
      if (!cancelled) { cancelled = true; setStatus("error"); }
    }, 20000);
    const finish = (next: Status) => {
      if (cancelled) return;
      window.clearTimeout(timeout);
      setStatus(next);
    };

    loadKakaoSdk()
      .then(() => {
        if (cancelled || !container.current) return;
        const { maps } = window.kakao!;

        const start = (position: KakaoLatLng) => {
          const client = new maps.RoadviewClient();

          // 반경을 넓혀가며 가장 가까운 파노라마를 찾는다. 이면도로 매물은
          // 50m로는 촬영 지점이 안 걸리는 경우가 있다.
          const tryRadius = (radii: number[]) => {
            if (!radii.length) {
              finish("unavailable");
              return;
            }
            const [radius, ...rest] = radii;
            client.getNearestPanoId(position, radius, (panoId) => {
              if (cancelled) return;
              if (!panoId) {
                tryRadius(rest);
                return;
              }

              roadview = new maps.Roadview(container.current!);
              onInit = () => {
                if (cancelled) return;
                const from = roadview!.getPosition();
                roadview!.setViewpoint({
                  pan: bearing(
                    from.getLat(),
                    from.getLng(),
                    position.getLat(),
                    position.getLng(),
                  ),
                  tilt: 0,
                  // 기본 화각(0)은 파노라마가 건물에 가까울 때 간판이 잘린다.
                  // 한 단계 넓히면 상가 전면과 인접 점포까지 프레임에 들어온다.
                  zoom: -1,
                });
                finish("ready");
              };
              maps.event.addListener(roadview, "init", onInit);
              resize = new ResizeObserver(() => { if (!cancelled) roadview?.relayout(); });
              resize.observe(container.current!);
              roadview.setPanoId(panoId, position);
            });
          };

          tryRadius([50, 150, 400]);
        };

        if (validCoordinates(lat, lng)) {
          start(new maps.LatLng(lat!, lng!));
          return;
        }

        // 좌표가 없는 매물(사용자가 직접 등록한 건 등)은 주소로 즉석 지오코딩한다.
        new maps.services.Geocoder().addressSearch(address, (result, st) => {
          if (cancelled) return;
          if (st !== maps.services.Status.OK || !result.length) {
            finish("unavailable");
            return;
          }
          const geocodedLat = Number(result[0].y);
          const geocodedLng = Number(result[0].x);
          if (!validCoordinates(geocodedLat, geocodedLng)) { finish("unavailable"); return; }
          start(new maps.LatLng(geocodedLat, geocodedLng));
        });
      })
      .catch((error: unknown) => {
        finish(error instanceof RoadviewSetupError ? "unconfigured" : "error");
      });

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
      resize?.disconnect();
      if (roadview && onInit) window.kakao?.maps.event.removeListener(roadview, "init", onInit);
      element?.replaceChildren();
    };
  }, [lat, lng, address]);

  const failed = status === "unavailable" || status === "error" || status === "unconfigured";
  const externalUrl = validCoordinates(lat, lng)
    ? `https://map.kakao.com/link/roadview/${lat},${lng}`
    : `https://map.kakao.com/link/search/${encodeURIComponent(address)}`;
  const message = status === "unconfigured" ? "로드뷰 연결이 아직 설정되지 않았습니다."
    : status === "unavailable" ? "이 위치 주변에서 제공되는 로드뷰를 찾지 못했습니다."
    : "로드뷰를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";

  return (
    <section aria-label="매물 로드뷰" className="overflow-hidden rounded-lg border border-border">
      <div ref={container} aria-label={`${address} 로드뷰`} className={`${failed ? "hidden" : "aspect-[4/3]"} w-full bg-background`} />
      {failed && (
        <div className="flex min-h-52 flex-col items-center justify-center gap-4 bg-background px-6 py-8 text-center">
          <p role="status" className="text-sm text-muted">{message}</p>
          <div className="flex flex-wrap justify-center gap-3 text-sm font-semibold">
            <button type="button" onClick={onRetry} className="rounded-full border border-border bg-surface px-4 py-2 hover:bg-accent-soft">로드뷰 다시 불러오기</button>
            <a href={externalUrl} target="_blank" rel="noopener noreferrer" className="rounded-full bg-accent px-4 py-2 text-accent-foreground">{validCoordinates(lat, lng) ? "카카오맵에서 로드뷰 보기 ↗" : "카카오맵에서 주소 검색 ↗"}</a>
          </div>
        </div>
      )}
      {!failed && <p role="status" className="border-t border-border bg-background px-3 py-1.5 text-xs text-muted">
        {status === "loading" ? "로드뷰 불러오는 중…" : `카카오 로드뷰 · ${address}`}
      </p>}
    </section>
  );
}
