export type RegionScope = "district" | "neighborhood";
export type VacancyMetric = "count" | "rate";

export interface RegionStats {
  id: string;
  scope: RegionScope;
  region_name: string;
  lat: number;
  lng: number;
  total_units: number;
  vacant_units: number;
  vacancy_rate: number;
  avg_vacancy_period_months: number;
  top_recommended_business: string;
  monthly_vacant_units: number[];
  vacancy_trend_6m: number[];
  building_id: string | null;
  parent_id: string | null;
}

export interface RegionStatsResponse {
  is_mock: boolean;
  data_reference_month: string;
  months: string[];
  description: string;
  regions: RegionStats[];
}

export const VACANCY_COLORS = ["#eac8ac", "#d89770", "#c76a43", "#ad452d", "#7e2b22"];
export const METRIC_THRESHOLDS = { count: [50, 100, 250, 500], rate: [10, 15, 20, 25] };
export const metricValue = (region: RegionStats, metric: VacancyMetric) =>
  metric === "count" ? region.vacant_units : region.vacancy_rate;
export function vacancyColor(value: number, metric: VacancyMetric) {
  const index = METRIC_THRESHOLDS[metric].filter((threshold) => value >= threshold).length;
  return VACANCY_COLORS[index];
}
