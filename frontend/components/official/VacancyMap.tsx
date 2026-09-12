"use client";

import { useEffect, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";
import { metricValue, vacancyColor, type RegionStats, type VacancyMetric } from "@/lib/regionTypes";

interface Props {
  regions: RegionStats[];
  selectedId: string;
  metric: VacancyMetric;
  onSelect: (id: string) => void;
}

export default function VacancyMap({ regions, selectedId, metric, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const library = useRef<typeof Leaflet | null>(null);
  const tiles = useRef<Leaflet.TileLayer | null>(null);
  const bounds = useRef<Leaflet.LatLngBounds | null>(null);
  const fitMaxZoom = useRef(9);
  const markers = useRef(new Map<string, Leaflet.CircleMarker>());
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let resize: ResizeObserver | undefined;
    import("leaflet").then((L) => {
      if (cancelled || !container.current) return;
      library.current = L;
      const instance = L.map(container.current, {
        scrollWheelZoom: false, zoomControl: false, minZoom: 7, maxZoom: 17,
      }).setView([35.73, 127.12], 9);
      map.current = instance;
      L.control.zoom({ position: "topright" }).addTo(instance);
      tiles.current = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).on("tileerror", () => {
        if (!cancelled) setError("배경 지도를 불러오지 못했습니다. 지역 원과 아래 비교 목록은 사용할 수 있습니다.");
      }).addTo(instance);
      resize = new ResizeObserver(() => {
        instance.invalidateSize();
        if (bounds.current) instance.fitBounds(bounds.current, {
          padding: [55, 55], maxZoom: fitMaxZoom.current, animate: false,
        });
      });
      resize.observe(container.current);
      setReady(true);
    }).catch(() => {
      if (!cancelled) setError("지도를 불러오지 못했습니다. 아래 지역별 비교 목록에서 지역을 선택해 주세요.");
    });
    return () => {
      cancelled = true;
      resize?.disconnect();
      map.current?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const L = library.current;
    const instance = map.current;
    if (!ready || !L || !instance || regions.length === 0) return;
    bounds.current = L.latLngBounds(regions.map((r) => [r.lat, r.lng]));
    fitMaxZoom.current = regions[0].scope === "district" ? 9 : 13;
    instance.fitBounds(bounds.current, {
      padding: [55, 55], maxZoom: fitMaxZoom.current, animate: false,
    });
  }, [ready, regions]);

  useEffect(() => {
    const L = library.current;
    const instance = map.current;
    if (!ready || !L || !instance) return;
    const group = L.layerGroup().addTo(instance);
    const currentMarkers = markers.current;
    currentMarkers.clear();
    const max = Math.max(1, ...regions.map((region) => metricValue(region, metric)));
    for (const region of regions) {
      const value = metricValue(region, metric);
      const marker = L.circleMarker([region.lat, region.lng], {
        radius: region.scope === "district" ? 12 + Math.sqrt(value / max) * 21 : 7 + Math.sqrt(value / max) * 13,
        color: "#fff", weight: 2, fillColor: vacancyColor(value, metric), fillOpacity: 0.83,
      }).addTo(group);
      const label = document.createElement("span");
      label.textContent = region.region_name;
      const direction = region.id === "gaeksa" ? "left" : region.id === "gyeongwon" ? "right" : region.id === "wanju" ? "top" : "bottom";
      marker.bindTooltip(label, { permanent: true, direction, offset: [0, direction === "bottom" ? 14 : 0], className: "vacancy-map-label" });
      const popup = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = region.region_name;
      const summary = document.createElement("p");
      summary.textContent = "공실 " + region.vacant_units.toLocaleString("ko-KR") + "개 · 공실률 " + region.vacancy_rate.toFixed(1) + "%";
      const detail = document.createElement("p");
      detail.textContent = "평균 공실 " + region.avg_vacancy_period_months + "개월 · 추천 업종 " + region.top_recommended_business;
      popup.append(heading, summary, detail);
      marker.bindPopup(popup).on("click", () => onSelect(region.id));
      const element = marker.getElement();
      if (element) {
        element.setAttribute("tabindex", "0");
        element.setAttribute("role", "button");
        element.setAttribute("aria-label", region.region_name + " 공실 " + region.vacant_units + "개, 공실률 " + region.vacancy_rate + "%");
        element.addEventListener("keydown", (event) => {
          const key = (event as KeyboardEvent).key;
          if (key === "Enter" || key === " ") {
            event.preventDefault();
            onSelect(region.id);
            marker.openPopup();
          }
        });
      }
      currentMarkers.set(region.id, marker);
    }
    return () => { group.remove(); currentMarkers.clear(); };
  }, [ready, regions, metric, onSelect]);

  useEffect(() => {
    markers.current.forEach((marker, id) => {
      marker.setStyle({ color: id === selectedId ? "#292720" : "#fff", weight: id === selectedId ? 3 : 2 });
      marker.getElement()?.setAttribute("aria-pressed", String(id === selectedId));
      if (id === selectedId) marker.bringToFront();
      else marker.closePopup();
    });
  }, [selectedId, ready, regions, metric, onSelect]);

  function resetView() {
    const L = library.current;
    if (L && map.current && regions.length) {
      map.current.fitBounds(L.latLngBounds(regions.map((r) => [r.lat, r.lng])), {
        padding: [55, 55], maxZoom: regions[0].scope === "district" ? 9 : 13, animate: false,
      });
    }
  }

  return (
    <div className="vacancy-map-wrap">
      <div ref={container} className="vacancy-map" role="region" aria-label="전북 지역별 공실 분포 지도" />
      {!ready && !error && <div className="map-loading" role="status">지도를 준비하고 있습니다…</div>}
      <button className="map-reset" onClick={resetView} disabled={!ready}>전체 보기 ↗</button>
      {error && <div className="map-error" role="status">{error}
        {ready && <button onClick={() => { setError(""); tiles.current?.redraw(); }}>지도 다시 불러오기</button>}
      </div>}
    </div>
  );
}
