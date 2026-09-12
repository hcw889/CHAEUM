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


class MatchCandidate(BaseModel):
    building_id: str
    address: str
    final_score: float
    rank: Optional[str] = None  # gold | silver | bronze | None
    agent_scores: dict
    explanation: str
    photo_url: Optional[str] = None
    space_vision: Optional[SpaceVision] = None


class MatchResponse(BaseModel):
    matches: list[MatchCandidate]


# --- 공간 시각화 (팝업 컨셉 적용 이미지 생성) ---
# 매칭 flow와는 독립적인 기능이다. MatchRequest / MatchResponse는 건드리지 않는다.


class SpaceRenderRequest(BaseModel):
    concept: str = Field(..., min_length=1)  # 업종 또는 팝업 브랜드/컨셉
    photo_data_url: Optional[str] = None  # 업로드 사진 (data URL). 없으면 기본 이미지
    mask_data_url: Optional[str] = None  # 다시 그릴 영역 마스크. local 모드에서만 사용
    commercial_style_pref: Optional[str] = None
    occupancy_term: Optional[str] = None  # 단기 | 장기
    strength: float = Field(0.65, ge=0.1, le=1.0)


class SpaceRenderResponse(BaseModel):
    mode: str  # hf_api | local | mock
    model: str
    prompt: str
    before_image: str
    after_image: str
    note: Optional[str] = None
