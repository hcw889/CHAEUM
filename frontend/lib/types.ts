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
  /**
   * 입점 희망 기간(단기/장기). 팝업 브랜드 role에서만 입력받는다.
   * TODO: 단기임대 가중치 반영은 로드맵 다음 단계 — 현재 매칭 스코어링에는 쓰이지 않고
   * 저장/로깅과 공간 시각화 프롬프트 연출에만 쓰인다.
   */
  occupancy_term?: string;
}

export const OCCUPANCY_TERM_OPTIONS: { value: string; label: string; description: string }[] = [
  { value: "단기", label: "단기 (팝업·시즌)", description: "며칠~수개월 단위의 한시적 입점" },
  { value: "장기", label: "장기", description: "1년 이상 고정 임대" },
];

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

// --- 공간 시각화 (팝업 컨셉 적용 이미지 생성) ---

export type RenderMode = "hf_api" | "local" | "mock";

export interface SpaceRenderRequest {
  concept: string;
  photo_data_url?: string;
  mask_data_url?: string;
  commercial_style_pref?: string;
  occupancy_term?: string;
  strength?: number;
}

export interface SpaceRenderResponse {
  mode: RenderMode;
  model: string;
  prompt: string;
  before_image: string;
  after_image: string;
  note?: string | null;
}

export const RENDER_MODE_LABELS: Record<RenderMode, string> = {
  hf_api: "HuggingFace 생성",
  local: "로컬 diffusers 생성",
  mock: "미리보기 (생성 미연결)",
};

export const BUSINESS_TYPE_OPTIONS = ["카페", "학원", "병원", "편의점", "스터디카페"];
export const REGION_OPTIONS = [
  "상관없음",
  "팔달로",
  "객사길",
  "태평동",
  "경원동",
  "전주역",
  "풍남동",
  "노송동",
  "중앙동",
  "진북동",
  "완산동",
  "다가동",
  "인후동",
  "전동",
  "고사동",
  "서노송동",
];
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
