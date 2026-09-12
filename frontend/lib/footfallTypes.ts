export type DayType = "weekday" | "weekend";

export interface FootfallArea {
  id: string;
  name: string;
  lat: number;
  lng: number;
  radius_m: number;
  profile: string;
  profile_label: string;
  distance_m: number;
  hourly: number[]; // 0시~23시 (24칸)
  daily_total: number;
  peak_hour: number;
  share_pct: number;
  is_mock: boolean;
}

export interface FootfallSummary {
  daily_total: number;
  peak_hour: number;
  peak_area_name: string;
  top_area_name: string;
  walkable_total: number;
  max_area_daily: number;
}

export interface FootfallResponse {
  building_id: string;
  address: string | null;
  region: string | null;
  mode: "sk_api" | "mock";
  is_mock: boolean;
  source_label: string;
  note: string | null; // 키는 붙었지만 실데이터를 못 받은 경우의 진단 문구
  day_type: DayType;
  date: string;
  data_reference_month: string;
  description: string;
  center_lat: number;
  center_lng: number;
  search_radius_m: number;
  areas: FootfallArea[];
  summary: FootfallSummary;
}

/** 연한 모래색 → 진한 테라코타. 값이 클수록 진해진다. */
export const FOOTFALL_COLORS = ["#f4e6cd", "#efc98d", "#e29a58", "#cd6b3a", "#a53f2a"];
export const FOOTFALL_LEVEL_LABELS = ["매우 적음", "적음", "보통", "많음", "매우 많음"];
/** 구역 중 최댓값 대비 비율 기준. 상권마다 절대 규모가 달라 상대 기준이 더 읽기 쉽다. */
export const FOOTFALL_RATIOS = [0.2, 0.4, 0.6, 0.8];

export function footfallLevel(value: number, max: number) {
  if (max <= 0) return 0;
  const ratio = value / max;
  return FOOTFALL_RATIOS.filter((threshold) => ratio >= threshold).length;
}

export function footfallColor(value: number, max: number) {
  return FOOTFALL_COLORS[footfallLevel(value, max)];
}

/** hour가 null이면 하루 전체 합계를 본다. */
export function areaValue(area: FootfallArea, hour: number | null) {
  return hour === null ? area.daily_total : area.hourly[hour];
}

export const formatPeople = (value: number) => `${Math.round(value).toLocaleString("ko-KR")}명`;
export const formatHour = (hour: number) => `${String(hour).padStart(2, "0")}시`;
export const formatDate = (yyyymmdd: string) =>
  yyyymmdd.length === 8
    ? `${yyyymmdd.slice(0, 4)}.${yyyymmdd.slice(4, 6)}.${yyyymmdd.slice(6, 8)}`
    : yyyymmdd;
