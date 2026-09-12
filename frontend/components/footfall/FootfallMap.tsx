"use client";

import { useEffect, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";
import "./footfall.css";
import {
  areaValue,
  footfallColor,
  formatHour,
  formatPeople,
  type FootfallArea,
} from "@/lib/footfallTypes";

interface Props {
  areas: FootfallArea[];
  center: { lat: number; lng: number };
  /** null이면 하루 전체 합계를 색으로 표시한다. */
  hour: number | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/**
 * 추천 매물 주변 유동인구 지도.
 * 구역 원의 색 = 선택한 시간대의 유동인구(구역 중 최댓값 대비 상대값),
 * 원의 크기 = 구역 반경. 지자체 대시보드의 VacancyMap과 같은 Leaflet 구성을 따른다.
 */
export default function FootfallMap({ areas, center, hour, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const library = useRef<typeof Leaflet | null>(null);
  const tiles = useRef<Leaflet.TileLayer | null>(null);
  const bounds = useRef<Leaflet.LatLngBounds | null>(null);
  const circles = useRef(new Map<string, Leaflet.Circle>());
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let resize: ResizeObserver | undefined;
    import("leaflet")
      .then((L) => {
        if (cancelled || !container.current) return;
        library.current = L;
        const instance = L.map(container.current, {
          scrollWheelZoom: false,
          zoomControl: false,
          minZoom: 11,
          maxZoom: 18,
        }).setView([center.lat, center.lng], 15);
        map.current = instance;
        L.control.zoom({ position: "topright" }).addTo(instance);
        tiles.current = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        })
          .on("tileerror", () => {
            if (!cancelled) setError("배경 지도를 불러오지 못했습니다. 아래 구역 목록은 그대로 사용할 수 있습니다.");
          })
          .addTo(instance);
        resize = new ResizeObserver(() => {
          instance.invalidateSize();
          if (bounds.current) instance.fitBounds(bounds.current, { padding: [40, 40], maxZoom: 15, animate: false });
        });
        resize.observe(container.current);
        setReady(true);
      })
      .catch(() => {
        if (!cancelled) setError("지도를 불러오지 못했습니다. 아래 구역 목록에서 유동인구를 확인해 주세요.");
      });
    return () => {
      cancelled = true;
      resize?.disconnect();
      map.current?.remove();
      map.current = null;
    };
    // 매물을 바꿔도 지도 인스턴스는 재사용하고 아래 effect에서 범위만 다시 잡는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 구역 목록이 바뀌면(= 다른 매물 선택) 지도 범위를 다시 맞춘다.
  useEffect(() => {
    const L = library.current;
    const instance = map.current;
    if (!ready || !L || !instance || areas.length === 0) return;
    bounds.current = L.latLngBounds(areas.map((a) => [a.lat, a.lng] as [number, number]));
    instance.fitBounds(bounds.current, { padding: [40, 40], maxZoom: 15, animate: false });
  }, [ready, areas]);

  // 매물 위치 표시(중심점). 구역 원 위에 그려야 가려지지 않는다.
  useEffect(() => {
    const L = library.current;
    const instance = map.current;
    if (!ready || !L || !instance) return;
    if (!instance.getPane("site")) {
      const pane = instance.createPane("site");
      pane.style.zIndex = "650";
    }
    const marker = L.circleMarker([center.lat, center.lng], {
      pane: "site",
      radius: 6,
      color: "#262220",
      weight: 3,
      fillColor: "#fffefa",
      fillOpacity: 1,
    })
      .bindTooltip("추천 매물", { permanent: true, direction: "top", offset: [0, -6], className: "footfall-map-label" })
      .addTo(instance);
    return () => {
      marker.remove();
    };
  }, [ready, center.lat, center.lng]);

  // 구역 원: 시간대가 바뀔 때마다 색만 다시 칠한다.
  useEffect(() => {
    const L = library.current;
    const instance = map.current;
    if (!ready || !L || !instance || areas.length === 0) return;
    const group = L.layerGroup().addTo(instance);
    const current = circles.current;
    current.clear();
    const max = Math.max(1, ...areas.map((area) => areaValue(area, hour)));

    for (const area of areas) {
      const value = areaValue(area, hour);
      const circle = L.circle([area.lat, area.lng], {
        radius: area.radius_m,
        color: "#fffefa",
        weight: 2,
        fillColor: footfallColor(value, max),
        fillOpacity: 0.78,
      }).addTo(group);

      const popup = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = `${area.name} · ${area.profile_label}`;
      const line1 = document.createElement("p");
      line1.textContent =
        hour === null
          ? `하루 전체 ${formatPeople(value)}`
          : `${formatHour(hour)} ${formatPeople(value)} (하루 ${formatPeople(area.daily_total)})`;
      const line2 = document.createElement("p");
      line2.textContent = `매물에서 ${area.distance_m}m · 피크 ${formatHour(area.peak_hour)} · 주변 비중 ${area.share_pct}%`;
      popup.append(heading, line1, line2);
      circle.bindPopup(popup).on("click", () => onSelect(area.id));

      const label = document.createElement("span");
      label.textContent = area.name;
      circle.bindTooltip(label, { permanent: true, direction: "center", className: "footfall-map-label" });

      current.set(area.id, circle);
    }
    return () => {
      group.remove();
      current.clear();
    };
  }, [ready, areas, hour, onSelect]);

  // 선택 강조는 스타일만 바꿔 원을 다시 만들지 않는다.
  useEffect(() => {
    circles.current.forEach((circle, id) => {
      circle.setStyle({ color: id === selectedId ? "#262220" : "#fffefa", weight: id === selectedId ? 3 : 2 });
      if (id === selectedId) circle.bringToFront();
      else circle.closePopup();
    });
  }, [selectedId, ready, areas, hour]);

  return (
    <div className="footfall-map-wrap">
      <div ref={container} className="footfall-map" role="region" aria-label="추천 매물 주변 유동인구 지도" />
      {!ready && !error && (
        <div className="footfall-map-status" role="status">
          지도를 준비하고 있습니다…
        </div>
      )}
      {error && (
        <div className="footfall-map-status" role="status">
          <div>
            {error}
            {ready && (
              <div>
                <button
                  onClick={() => {
                    setError("");
                    tiles.current?.redraw();
                  }}
                >
                  지도 다시 불러오기
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
