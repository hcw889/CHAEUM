"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";
import { formatScore } from "@/lib/format";
import { hasMapLocation, RANK_NUMBERS, type LocatedMatch } from "@/lib/matchMap";
import type { MatchCandidate } from "@/lib/types";
import "./match-results.css";

interface Props {
  matches: MatchCandidate[];
  onSelect?: (id: string) => void;
  detail?: boolean;
  loading?: boolean;
}

export default function MatchMap({ matches, onSelect, detail = false, loading = false }: Props) {
  const located = useMemo(() => matches.filter(hasMapLocation), [matches]);
  if (located.length === 0) {
    return (
      <div className="match-map-empty" role="status">
        <span className="text-3xl" aria-hidden>⌖</span>
        <p>{loading ? "매물 위치를 불러오고 있습니다…" : "이 매물의 위치 정보가 아직 없습니다."}</p>
        {!loading && <p className="text-xs text-muted">추천 근거는 매물 상세에서 확인할 수 있습니다.</p>}
      </div>
    );
  }
  return <LeafletMatchMap matches={located} onSelect={onSelect} detail={detail} />;
}

function LeafletMatchMap({ matches, onSelect, detail }: { matches: LocatedMatch[]; onSelect?: Props["onSelect"]; detail: boolean }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const library = useRef<typeof Leaflet | null>(null);
  const tiles = useRef<Leaflet.TileLayer | null>(null);
  const fit = useRef<(() => void) | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let resize: ResizeObserver | undefined;
    let instance: Leaflet.Map | undefined;
    import("leaflet").then((L) => {
      if (cancelled || !container.current) return;
      library.current = L;
      instance = L.map(container.current, { zoomControl: false, scrollWheelZoom: false, minZoom: 3, maxZoom: 19 });
      map.current = instance;
      L.control.zoom({ position: "topright" }).addTo(instance);
      L.control.scale({ imperial: false, position: "bottomleft" }).addTo(instance);
      tiles.current = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).on("tileerror", () => {
        if (!cancelled) setError("배경 지도를 불러오지 못했습니다. 매물 마커와 추천 카드는 계속 선택할 수 있습니다.");
      }).addTo(instance);
      resize = new ResizeObserver(() => {
        instance?.invalidateSize();
        fit.current?.();
      });
      resize.observe(container.current);
      setReady(true);
    }).catch(() => {
      if (!cancelled) setError("지도를 불러오지 못했습니다. 아래 추천 카드에서 매물 상세를 확인해 주세요.");
    });
    return () => {
      cancelled = true;
      resize?.disconnect();
      instance?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const L = library.current;
    const instance = map.current;
    if (!ready || !L || !instance) return;
    const group = L.layerGroup().addTo(instance);

    for (const match of matches) {
      const rank = match.rank ? RANK_NUMBERS[match.rank] : null;
      const label = rank ? `추천 ${rank}위 ${match.address} 상세 보기` : `${match.address} 위치`;
      const pin = document.createElement("div");
      pin.className = `match-pin match-pin--${match.rank ?? "selected"}`;
      const rankLabel = document.createElement("span");
      rankLabel.className = "match-pin-rank";
      rankLabel.textContent = rank ? `${rank}위` : "매물";
      const score = document.createElement("span");
      score.className = "match-pin-score";
      score.textContent = `${formatScore(match.final_score)}점`;
      pin.append(rankLabel, score);
      const marker = L.marker([match.location.lat, match.location.lng], {
        icon: L.divIcon({ html: pin, className: "match-marker", iconSize: [116, 52], iconAnchor: [58, 52] }),
        title: label, alt: label, keyboard: !!onSelect, interactive: !!onSelect,
        zIndexOffset: rank ? 100 - rank : 100,
      });
      // 첫 setView 전에는 Leaflet이 마커 DOM 생성을 미루므로 add 시점에 이름을 붙인다.
      marker.on("add", () => {
        const element = marker.getElement();
        if (element) {
          element.setAttribute("aria-label", label);
          if (onSelect) {
            element.setAttribute("role", "button");
            element.setAttribute("aria-haspopup", "dialog");
            element.addEventListener("keydown", (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                event.stopPropagation();
                marker.fire("click");
              }
            });
          }
        }
      });
      marker.addTo(group);
      if (onSelect) marker.on("click", () => {
        marker.getElement()?.focus({ preventScroll: true });
        onSelect(match.building_id);
      });
    }

    const fitMatches = () => {
      if (detail || matches.length === 1) {
        instance.setView([matches[0].location.lat, matches[0].location.lng], detail ? 17 : 15, { animate: false });
      } else {
        instance.fitBounds(L.latLngBounds(matches.map((m) => [m.location.lat, m.location.lng])), {
          paddingTopLeft: [80, 110], paddingBottomRight: [80, 205], maxZoom: 15, animate: false,
        });
      }
    };
    fit.current = fitMatches;
    fitMatches();
    return () => { group.remove(); fit.current = null; };
  }, [ready, matches, onSelect, detail]);

  return (
    <div className="match-map-frame">
      <div ref={container} className="match-map-canvas" role="region" aria-label={detail ? "선택한 매물 확대 지도" : "추천 TOP 3 매물 지도"} />
      {ready && (
        <button type="button" className="match-map-reset" onClick={() => fit.current?.()}>
          {detail ? "매물 위치로" : "전체 매물 보기"}
        </button>
      )}
      {!ready && !error && <div className="match-map-message" role="status">지도를 준비하고 있습니다…</div>}
      {error && (
        <div className="match-map-message" role="status">
          <span>{error}</span>
          {ready && <button type="button" onClick={() => { setError(""); tiles.current?.redraw(); }}>지도 다시 불러오기</button>}
        </div>
      )}
    </div>
  );
}
