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
    kakao: { maps: KakaoMaps };
  }
}

// SDK는 앱 전체에서 한 번만 로드한다. 매물을 바꿔 누를 때마다 script 태그가
// 늘어나는 것을 막는다.
let sdkPromise: Promise<void> | null = null;

function loadKakaoSdk(): Promise<void> {
  if (sdkPromise) return sdkPromise;

  sdkPromise = new Promise((resolve, reject) => {
    const key = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY;
    if (!key) {
      reject(new Error("NEXT_PUBLIC_KAKAO_MAP_KEY 미설정"));
      return;
    }
    const script = document.createElement("script");
    // autoload=false + kakao.maps.load()로 초기화 시점을 직접 잡는다.
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${key}&libraries=services&autoload=false`;
    script.async = true;
    script.onload = () => window.kakao.maps.load(() => resolve());
    script.onerror = () => reject(new Error("Kakao SDK 로드 실패"));
    document.head.appendChild(script);
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

type Status = "loading" | "ready" | "unavailable" | "error";

/**
 * 매물 위치의 카카오 로드뷰. 호출하는 쪽에서 매물이 바뀔 때 key로 리마운트해야
 * 상태가 초기화된다 (effect 안에서 setState로 되돌리지 않기 위한 선택).
 */
export default function RoadviewPanel({
  lat,
  lng,
  address,
  fallbackSrc,
}: {
  lat?: number;
  lng?: number;
  address: string;
  fallbackSrc?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;

    loadKakaoSdk()
      .then(() => {
        if (cancelled || !container.current) return;
        const { maps } = window.kakao;

        const start = (position: KakaoLatLng) => {
          const client = new maps.RoadviewClient();

          // 반경을 넓혀가며 가장 가까운 파노라마를 찾는다. 이면도로 매물은
          // 50m로는 촬영 지점이 안 걸리는 경우가 있다.
          const tryRadius = (radii: number[]) => {
            if (!radii.length) {
              setStatus("unavailable");
              return;
            }
            const [radius, ...rest] = radii;
            client.getNearestPanoId(position, radius, (panoId) => {
              if (cancelled) return;
              if (!panoId) {
                tryRadius(rest);
                return;
              }

              const roadview = new maps.Roadview(container.current!);
              maps.event.addListener(roadview, "init", () => {
                if (cancelled) return;
                const from = roadview.getPosition();
                roadview.setViewpoint({
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
                setStatus("ready");
              });
              roadview.setPanoId(panoId, position);
            });
          };

          tryRadius([50, 150, 400]);
        };

        if (lat != null && lng != null) {
          start(new maps.LatLng(lat, lng));
          return;
        }

        // 좌표가 없는 매물(사용자가 직접 등록한 건 등)은 주소로 즉석 지오코딩한다.
        new maps.services.Geocoder().addressSearch(address, (result, st) => {
          if (cancelled) return;
          if (st !== maps.services.Status.OK || !result.length) {
            setStatus("unavailable");
            return;
          }
          start(new maps.LatLng(Number(result[0].y), Number(result[0].x)));
        });
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [lat, lng, address]);

  // 로드뷰가 없거나 SDK가 실패하면 기존 참고 이미지로 폴백한다.
  if (status === "unavailable" || status === "error") {
    if (!fallbackSrc) {
      return (
        <div className="grid aspect-[4/3] w-full place-items-center rounded-lg border border-border bg-background px-6 text-center text-sm text-muted">
          이 위치는 로드뷰가 제공되지 않습니다
        </div>
      );
    }
    return (
      <div className="overflow-hidden rounded-lg border border-border">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={fallbackSrc}
          alt={`${address} 상가 외관 참고 이미지`}
          className="aspect-[4/3] w-full object-cover"
        />
        <p className="border-t border-border bg-background px-3 py-1.5 text-xs text-muted">
          로드뷰 미제공 구간 · 참고 이미지
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div ref={container} className="aspect-[4/3] w-full bg-background" />
      <p className="border-t border-border bg-background px-3 py-1.5 text-xs text-muted">
        {status === "loading" ? "로드뷰 불러오는 중…" : `카카오 로드뷰 · ${address}`}
      </p>
    </div>
  );
}
