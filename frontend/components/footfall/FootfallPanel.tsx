"use client";

import { useEffect, useMemo, useState } from "react";
import FootfallMap from "@/components/footfall/FootfallMap";
import { api } from "@/lib/api";
import {
  FOOTFALL_COLORS,
  FOOTFALL_LEVEL_LABELS,
  areaValue,
  footfallColor,
  formatDate,
  formatHour,
  formatPeople,
  type DayType,
  type FootfallResponse,
} from "@/lib/footfallTypes";

interface Props {
  buildingId: string;
  /** 지도 옆 문구에 쓰는 매물 주소 (선택) */
  address?: string;
}

const DAY_OPTIONS: { value: DayType; label: string }[] = [
  { value: "weekday", label: "평일" },
  { value: "weekend", label: "주말" },
];
const ALL_DAY = -1; // 시간 슬라이더의 '하루 전체' 위치

/**
 * 추천 매물 주변 유동인구 대시보드.
 * 값은 SK open API 유동인구(키 미설정 시 시연용 가상 수치)에서 오며,
 * 시간대를 옮기면 지도 구역 색이 같이 바뀐다.
 */
export default function FootfallPanel({ buildingId, address }: Props) {
  const [dayType, setDayType] = useState<DayType>("weekday");
  const [hourSlot, setHourSlot] = useState<number>(ALL_DAY);
  const [pickedArea, setPickedArea] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  // 응답에 요청 키를 같이 담아둔다. 매물/요일을 바꾸는 동안 직전 결과를 그대로 두고
  // 새 결과가 오면 교체하므로, effect 안에서 로딩 state를 따로 세팅하지 않아도 된다.
  const [result, setResult] = useState<{ key: string; data?: FootfallResponse; failed?: boolean } | null>(null);
  const requestKey = `${buildingId}:${dayType}:${reloadKey}`;

  useEffect(() => {
    let cancelled = false;
    api
      .getFootfall(buildingId, dayType)
      .then((data) => {
        if (!cancelled) setResult({ key: requestKey, data });
      })
      .catch(() => {
        if (!cancelled) setResult({ key: requestKey, failed: true });
      });
    return () => {
      cancelled = true;
    };
  }, [requestKey, buildingId, dayType]);

  const settled = result?.key === requestKey ? result : null;
  const data = settled?.data ?? null;
  const loading = settled === null;
  const failed = settled?.failed ?? false;

  const hour = hourSlot === ALL_DAY ? null : hourSlot;
  const areas = useMemo(
    () => (data ? [...data.areas].sort((a, b) => areaValue(b, hour) - areaValue(a, hour)) : []),
    [data, hour],
  );
  const max = useMemo(() => Math.max(1, ...areas.map((area) => areaValue(area, hour))), [areas, hour]);
  const hourTotals = useMemo(
    () => Array.from({ length: 24 }, (_, h) => areas.reduce((sum, area) => sum + area.hourly[h], 0)),
    [areas],
  );
  const hourMax = Math.max(1, ...hourTotals);
  const detail = areas.find((area) => area.id === pickedArea) ?? null;
  const selectedArea = detail?.id ?? null;

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6">
        <div className="h-4 w-40 animate-pulse rounded bg-border" />
        <div className="mt-4 h-[340px] animate-pulse rounded bg-border/60" />
      </div>
    );
  }

  if (failed || !data) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6">
        <h2 className="mb-2 font-semibold">주변 유동인구</h2>
        <p className="text-sm text-muted">주변 유동인구를 불러오지 못했습니다.</p>
        <button
          onClick={() => setReloadKey((key) => key + 1)}
          className="mt-4 rounded-md border border-border px-4 py-2 text-sm hover:bg-accent-soft"
        >
          다시 불러오기
        </button>
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className="rounded-lg border border-border bg-surface p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold tracking-[1.6px] text-muted">AROUND THE SITE</p>
          <h2 className="mt-1 font-semibold">주변 유동인구</h2>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            {address ?? data.address ?? ""} 반경 {data.search_radius_m}m · {data.areas.length}개 구역 ·{" "}
            {formatDate(data.date)} 기준
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-border p-[3px]">
            {DAY_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setDayType(option.value)}
                aria-pressed={dayType === option.value}
                className={`rounded px-3 py-1.5 text-xs transition-colors ${
                  dayType === option.value ? "bg-foreground text-background font-semibold" : "text-muted"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="하루 유동인구" value={formatPeople(summary.daily_total)} note="조회 구역 합계" />
        <Stat label="피크 시간대" value={formatHour(summary.peak_hour)} note={`최다 ${summary.peak_area_name}`} />
        <Stat label="도보권(500m)" value={formatPeople(summary.walkable_total)} note="가까운 구역 합계" />
        <Stat label="최대 구역" value={summary.top_area_name} note={formatPeople(summary.max_area_daily)} />
      </div>

      <div className="mb-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <label htmlFor="footfall-hour" className="text-xs text-muted">
            시간대
          </label>
          <span className="text-sm font-semibold">
            {hour === null ? "하루 전체" : `${formatHour(hour)} · ${formatPeople(hourTotals[hour])}`}
          </span>
        </div>
        <input
          id="footfall-hour"
          type="range"
          min={ALL_DAY}
          max={23}
          step={1}
          value={hourSlot}
          onChange={(event) => setHourSlot(Number(event.target.value))}
          className="w-full accent-accent"
          aria-valuetext={hour === null ? "하루 전체" : formatHour(hour)}
        />
        <div
          className="mt-2 flex h-12 items-end gap-[2px]"
          role="img"
          aria-label={`시간대별 주변 유동인구 합계. 피크 ${formatHour(summary.peak_hour)}`}
        >
          {hourTotals.map((total, index) => (
            <button
              key={index}
              onClick={() => setHourSlot(index)}
              title={`${formatHour(index)} ${formatPeople(total)}`}
              className="flex-1 rounded-sm transition-opacity hover:opacity-80"
              style={{
                height: `${Math.max(8, (total / hourMax) * 100)}%`,
                background: footfallColor(total, hourMax),
                outline: hourSlot === index ? "2px solid var(--foreground)" : "none",
              }}
            >
              <span className="sr-only">
                {formatHour(index)} {formatPeople(total)}
              </span>
            </button>
          ))}
        </div>
      </div>

      <FootfallMap
        areas={data.areas}
        center={{ lat: data.center_lat, lng: data.center_lng }}
        hour={hour}
        selectedId={selectedArea}
        onSelect={setPickedArea}
      />

      <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-muted">
        <span>{hour === null ? "하루 전체" : formatHour(hour)} 기준 유동인구</span>
        <div className="flex items-center gap-1">
          {FOOTFALL_COLORS.map((color, index) => (
            <span key={color} className="flex items-center gap-1">
              <span className="inline-block h-3 w-5 rounded-sm" style={{ background: color }} aria-hidden />
              {(index === 0 || index === FOOTFALL_COLORS.length - 1) && <span>{FOOTFALL_LEVEL_LABELS[index]}</span>}
            </span>
          ))}
        </div>
        <span className="ml-auto">색 기준: 구역 중 최댓값 대비 상대값</span>
      </div>

      <ul className="mt-4 space-y-1.5">
        {areas.map((area) => {
          const value = areaValue(area, hour);
          return (
            <li key={area.id}>
              <button
                onClick={() => setPickedArea(area.id === selectedArea ? null : area.id)}
                aria-pressed={area.id === selectedArea}
                className={`flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors ${
                  area.id === selectedArea ? "border-accent bg-accent-soft" : "border-border bg-background"
                }`}
              >
                <span
                  className="h-3 w-3 shrink-0 rounded-full"
                  style={{ background: footfallColor(value, max) }}
                  aria-hidden
                />
                <span className="w-28 shrink-0 truncate text-sm font-medium">{area.name}</span>
                <span className="hidden text-xs text-muted sm:inline">
                  {area.profile_label} · {area.distance_m}m
                </span>
                <span className="ml-auto flex items-center gap-3">
                  <span className="h-1.5 w-16 overflow-hidden rounded-full bg-border sm:w-28">
                    <span
                      className="block h-full rounded-full"
                      style={{ width: `${(value / max) * 100}%`, background: footfallColor(value, max) }}
                    />
                  </span>
                  <span className="w-20 text-right text-sm tabular-nums">{formatPeople(value)}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      {detail && (
        <div className="mt-4 rounded-md border border-border bg-background p-4 text-sm">
          <p className="font-semibold">
            {detail.name} <span className="text-xs font-normal text-muted">{detail.profile_label}</span>
          </p>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            하루 {formatPeople(detail.daily_total)} · 피크 {formatHour(detail.peak_hour)} · 매물에서{" "}
            {detail.distance_m}m · 주변 구역 합계의 {detail.share_pct}%
          </p>
        </div>
      )}

      {data.note && (
        <p className="mt-4 rounded-md border border-caution/40 bg-caution-soft px-3 py-2 text-[11px] leading-relaxed text-foreground">
          {data.note}
        </p>
      )}

      <p className="mt-4 text-[11px] leading-relaxed text-muted">
        출처: {data.source_label}
        {data.is_mock && " — SK open API 키가 연결되면 실측치로 대체됩니다"} · 기준월{" "}
        {data.data_reference_month.replace("-", ".")}
      </p>
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-md border border-border bg-background px-3 py-3">
      <p className="text-[11px] text-muted">{label}</p>
      <p className="mt-1 truncate text-lg font-bold tabular-nums">{value}</p>
      <p className="mt-0.5 truncate text-[11px] text-muted">{note}</p>
    </div>
  );
}
