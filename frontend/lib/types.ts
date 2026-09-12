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

// --- 매칭 flow (예비창업자 등: 조건 입력 → 매물 추천) ---

export interface BudgetInput {
  deposit: number;
  monthly_rent: number;
}

export interface MatchRequest {
  business_type: string;
  area_pyeong?: number;
  budget: BudgetInput;
  region_pref: string;
  commercial_style_pref?: string;
  priority: string;
}

export interface MatchAgentScores {
  budget: number;
  market_fit: number;
  condition: number;
}

export interface MatchCandidate {
  building_id: string;
  address: string;
  final_score: number;
  rank: RankLabel;
  agent_scores: MatchAgentScores;
  explanation: string;
}

export interface MatchResponse {
  matches: MatchCandidate[];
}

export const BUSINESS_TYPE_OPTIONS = ["카페", "학원", "병원", "편의점", "스터디카페"];
export const REGION_OPTIONS = ["상관없음", "팔달로", "객사길", "태평동", "경원동", "전주역"];
export const STYLE_OPTIONS: { value: string; label: string }[] = [
  { value: "유동인구중심", label: "유동인구중심형" },
  { value: "조용한골목상권", label: "조용한골목상권형" },
  { value: "학생상권", label: "학생상권형" },
];
export const PRIORITY_OPTIONS: { value: string; label: string; description: string }[] = [
  { value: "예산절약", label: "예산절약", description: "임대료·보증금 부담이 적은 매물을 우선" },
  { value: "매출잠재력", label: "매출잠재력", description: "유동인구·경쟁 상황 등 상권 적합도를 우선" },
  { value: "건물안정성", label: "건물안정성", description: "노후도·접근성·채광 등 건물 컨디션을 우선" },
];
