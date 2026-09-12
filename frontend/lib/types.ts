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

/** 매칭 지도에 표시할 좌표와 대략적인 위치 여부. */
export interface BuildingLocation {
  lat: number;
  lng: number;
  is_approximate: boolean;
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
   * 저장/로깅에만 쓰인다.
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

// space_vision_agent(backend) 결과. YOLO 없이 Vision-LLM 단일 호출로 산출되며,
// 4-agent 스코어링(final_score/agent_scores)과는 완전히 독립적인 별도 필드다.
export interface SpaceVision {
  exposure_score: number;
  accessibility_score: number;
  popup_fit_score: number;
  detected_elements: string[];
  visual_summary: string;
}

/**
 * 공실 추정 결과 (backend vacancy_estimator.py).
 *
 * 상가(상권)정보 API와 건축물대장 API 어느 쪽도 공실 여부를 직접 주지 않는다.
 * 건축물대장에 근린생활시설·판매시설로 등재된 층 중 상가정보에 등록 점포가
 * 0건인 층을 공실로 추정한 값이므로, 화면에는 반드시 "추정"과 근거를 함께 띄운다.
 * 목업 데이터에는 이 필드가 없다.
 */
export interface VacancyEstimate {
  estimated: boolean;
  confidence: "high" | "medium" | "low";
  method: string;
  /** 판정 근거. 화면에서 펼쳐 보여 준다. */
  basis: string[];
  register_purpose: string;
  floor_label: string;
  floor_area_sqm?: number;
  building_store_count: number;
  floor_store_count: number;
  unknown_floor_store_count: number;
}

export const VACANCY_CONFIDENCE_LABEL: Record<VacancyEstimate["confidence"], string> = {
  high: "높음",
  medium: "보통",
  low: "낮음",
};

export interface MatchCandidate {
  building_id: string;
  address: string;
  final_score: number;
  rank: RankLabel;
  agent_scores: MatchAgentScores;
  explanation: string;
  photo_url?: string;
  // 로드뷰 파노라마 조회용. 없으면 RoadviewPanel이 address로 지오코딩한다.
  lat?: number;
  lng?: number;
  space_vision?: SpaceVision;
  location?: BuildingLocation | null;

  // --- 실데이터(상가정보 + 건축물대장) 연동 필드. 목업에서는 대부분 비어 있다 ---
  name?: string;
  floor?: number;
  area_pyeong?: number;
  built_year?: number;
  region?: string;
  risk_grade?: string;
  vacancy?: VacancyEstimate;
  /** {필드명: "실데이터 · 기관명" | "추정값 · 근거"} — 출처 배지용 */
  data_sources?: Record<string, string>;
  /** 반경 300m 내 동일 업종 점포 수 (상가정보 실측) */
  competitor_count?: number;
  /** 반경 300m 내 전체 점포 수 (상가정보 실측) */
  nearby_store_count?: number;
  /** 같은 건물에서 영업 중인 점포 상호 — 공실 판정의 방증 */
  nearby_stores?: string[];
}

export interface MatchResponse {
  matches: MatchCandidate[];
  /** "real" = 상가정보 + 건축물대장 실데이터, "mock" = 시연용 목업 */
  data_mode?: "real" | "mock";
  source_note?: string;
  /** 입력 조건을 만족한 후보 수. matches는 그중 상위 일부다. */
  total_candidates?: number;
}

export interface MatchOptions {
  data_mode: "real" | "mock";
  /** 실데이터에서 매물이 실제로 존재하는 지역만. null이면 정적 REGION_OPTIONS를 쓴다. */
  region_options: string[] | null;
  business_types: string[];
  building_count: number;
  collected_at?: string | null;
  data_reference_month?: string | null;
  sources?: Record<string, string> | null;
  source_note?: string | null;
}

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
