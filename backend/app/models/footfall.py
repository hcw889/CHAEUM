from typing import Literal, Optional

from pydantic import BaseModel, Field

DayType = Literal["weekday", "weekend"]


class FootfallArea(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    radius_m: int = Field(gt=0)
    profile: str  # commercial | market | tourism | station | office | academy | youth | residential
    profile_label: str
    distance_m: int = Field(ge=0)
    hourly: list[int]  # 0시~23시 유동인구 (24칸)
    daily_total: int = Field(ge=0)
    peak_hour: int = Field(ge=0, le=23)
    share_pct: float = Field(ge=0, le=100)  # 조회된 구역 합계 대비 비중
    is_mock: bool  # 이 구역 값이 실측이 아니라 가상 수치인지
    # measured = 사람이 전사한 상권정보시스템 실측(footfall_measured.json), sk_api = SK 응답, mock = 가상
    source: Literal["measured", "sk_api", "mock"] = "mock"
    reference_month: Optional[str] = None  # 실측 기준월 (YYYY-MM). 구역마다 다를 수 있다
    # mock(추정) 구역의 규모 근거 — 구역이 속한 행정동과 주민등록 인구 어림값
    admin_dong: Optional[str] = None
    resident_population: Optional[int] = None


class FootfallSummary(BaseModel):
    daily_total: int
    peak_hour: int
    peak_area_name: str
    top_area_name: str
    walkable_total: int  # 도보권(500m 이내) 구역 합계
    max_area_daily: int


class FootfallResponse(BaseModel):
    building_id: str
    address: Optional[str] = None
    region: Optional[str] = None
    mode: Literal["sk_api", "mock"]
    is_mock: bool  # 구역 중 하나라도 실데이터면 False
    source_label: str
    note: Optional[str] = None  # 폴백 진단 문구 (정상이면 None)
    measured_count: int = 0  # 이번 응답 구역 중 전사 실측인 구역 수
    day_type: DayType
    date: str
    data_reference_month: str
    description: str
    center_lat: float
    center_lng: float
    search_radius_m: int
    areas: list[FootfallArea]
    summary: FootfallSummary
