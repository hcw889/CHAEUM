from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class BuildingSummary(BaseModel):
    id: str
    name: str
    address: str
    risk_grade: str
    thumbnail_color: str


class Diagnosis(BaseModel):
    aging_score: float
    accessibility_score: float
    lighting_score: float


class Building(BaseModel):
    id: str
    name: str
    address: str
    floor: int
    area_pyeong: float
    built_year: int
    risk_grade: str
    diagnosis: Diagnosis
    data_reference_month: str
    thumbnail_color: str = "#EEEEEE"


class PropertyInput(BaseModel):
    address: str = Field(..., min_length=1)
    floor: Optional[int] = None
    area_pyeong: Optional[float] = None
    has_photo: bool = False


class ScoreBreakdownItem(BaseModel):
    weight: float
    raw_score: float
    contribution: float


class BusinessFitCandidate(BaseModel):
    type: str
    fit_score: float
    rank: Optional[str] = None  # gold | silver | bronze | None
    score_breakdown: dict
    estimated_rent: int
    required_permits: list[str]


class DashboardMetrics(BaseModel):
    avg_competition_saturation: float
    avg_estimated_rent: int
    avg_foot_traffic: float
    top_competition_type: str


class PermitChecklistItem(BaseModel):
    label: str
    checked: bool = False


class ReportSummary(BaseModel):
    building: Building
    top_business: BusinessFitCandidate
    dashboard: DashboardMetrics
    generated_at: str


class BudgetInput(BaseModel):
    deposit: float = Field(..., ge=0)
    monthly_rent: float = Field(..., ge=0)


class MatchRequest(BaseModel):
    business_type: str = Field(..., min_length=1)
    area_pyeong: Optional[float] = None
    budget: BudgetInput
    region_pref: str = "상관없음"
    commercial_style_pref: Optional[str] = None
    priority: str = "매출잠재력"
    # 입점 희망 기간(단기/장기). 팝업 브랜드 role에서만 입력되며 값 전달/로깅 전용이다.
    # TODO: 단기임대 가중치 반영은 로드맵 다음 단계 — 현재 스코어링에는 쓰지 않는다.
    occupancy_term: Optional[str] = None


class SpaceVision(BaseModel):
    """space_vision_agent.calculate_space_score()의 반환 스키마. 4-agent 스코어링과
    완전히 독립적인 필드로, final_score/agent_scores 계산에는 관여하지 않는다."""

    exposure_score: float
    accessibility_score: float
    popup_fit_score: float
    detected_elements: list[str]
    visual_summary: str


class VacancyEstimate(BaseModel):
    """
    공실 추정 결과. 상가정보 API와 건축물대장 API 어느 쪽도 공실 여부를 직접
    제공하지 않으므로, 두 소스를 조인해 추론한 값이다 (vacancy_estimator.py).
    estimated는 항상 True이며, 판정 근거를 basis에 남겨 화면에서 펼쳐 볼 수 있게 한다.
    """

    estimated: bool = True
    confidence: str  # high | medium | low
    method: str
    basis: list[str]
    register_purpose: str = ""
    floor_label: str = ""
    floor_area_sqm: Optional[float] = None
    building_store_count: int = 0
    floor_store_count: int = 0
    unknown_floor_store_count: int = 0


class MatchCandidate(BaseModel):
    building_id: str
    address: str
    final_score: float
    rank: Optional[str] = None  # gold | silver | bronze | None
    agent_scores: dict
    explanation: str
    photo_url: Optional[str] = None
    # 로드뷰 파노라마 조회용 좌표. scripts/geocode_buildings.py가 채운다.
    # 없으면 프론트가 address로 즉석 지오코딩한다.
    lat: Optional[float] = None
    lng: Optional[float] = None
    space_vision: Optional[SpaceVision] = None
    location: Optional[BuildingLocation] = None

    # --- 실데이터 연동으로 추가된 필드 (목업에서는 대부분 None) ---
    name: Optional[str] = None
    floor: Optional[int] = None
    area_pyeong: Optional[float] = None
    built_year: Optional[int] = None
    region: Optional[str] = None
    risk_grade: Optional[str] = None
    # 공실 추정 결과. 목업 데이터에는 없으므로 None이다.
    vacancy: Optional[VacancyEstimate] = None
    # 필드별 출처 배지용. {필드명: "실데이터 · 기관명" | "추정값 · 근거"}
    data_sources: dict[str, str] = Field(default_factory=dict)
    # 반경 300m 내 실제 영업 점포 수 / 그중 동일 업종 수 (상가정보 실측)
    competitor_count: Optional[int] = None
    nearby_store_count: Optional[int] = None
    # 같은 건물에서 영업 중인 점포 상호 (공실 판정의 방증)
    nearby_stores: list[str] = Field(default_factory=list)


class MatchResponse(BaseModel):
    matches: list[MatchCandidate]
    # "real" = 상가정보 + 건축물대장 실데이터, "mock" = 시연용 목업
    data_mode: str = "mock"
    source_note: Optional[str] = None
    # 필터를 통과한 전체 후보 수. matches는 상위 일부만 담는다.
    total_candidates: int = 0
