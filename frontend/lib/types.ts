export type RiskGrade = "안전" | "주의" | "위험";
export type RankLabel = "gold" | "silver" | "bronze" | null;
export type Role = "owner" | "founder" | "brand" | "official";

export interface BuildingSummary {
  id: string;
  name: string;
  address: string;
  risk_grade: RiskGrade;
  thumbnail_color: string;
}

export interface Diagnosis {
  aging_score: number;
  accessibility_score: number;
  lighting_score: number;
}

export interface Building {
  id: string;
  name: string;
  address: string;
  floor: number;
  area_pyeong: number;
  built_year: number;
  risk_grade: RiskGrade;
  diagnosis: Diagnosis;
  data_reference_month: string;
  thumbnail_color: string;
  matched_scenario_id?: string;
}

export interface PropertyInput {
  address: string;
  floor?: number;
  area_pyeong?: number;
  has_photo?: boolean;
}

export interface ScoreBreakdown {
  [key: string]: number;
}

export interface BusinessFitCandidate {
  type: string;
  fit_score: number;
  rank: RankLabel;
  score_breakdown: ScoreBreakdown;
  estimated_rent: number;
  required_permits: string[];
}

export interface DashboardMetrics {
  avg_competition_saturation: number;
  avg_estimated_rent: number;
  avg_foot_traffic: number;
  top_competition_type: string;
}

export interface PermitChecklistItem {
  label: string;
  checked: boolean;
}

export interface ReportSummary {
  building: Building;
  top_business: BusinessFitCandidate;
  dashboard: DashboardMetrics;
  generated_at: string;
}

export const ROLE_LABELS: Record<Role, string> = {
  owner: "건물주",
  founder: "예비 창업자",
  brand: "팝업 브랜드",
  official: "지자체 담당자",
};
