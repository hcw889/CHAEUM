from typing import Literal

from pydantic import BaseModel, Field


class RegionStats(BaseModel):
    id: str
    scope: Literal["district", "neighborhood"]
    region_name: str
    lat: float
    lng: float
    total_units: int = Field(gt=0)
    vacant_units: int = Field(ge=0)
    vacancy_rate: float = Field(ge=0, le=100)
    avg_vacancy_period_months: float = Field(ge=0)
    top_recommended_business: str
    monthly_vacant_units: list[int]
    vacancy_trend_6m: list[float]
    building_id: str | None = None
    parent_id: str | None = None


class RegionStatsResponse(BaseModel):
    is_mock: bool
    data_reference_month: str
    months: list[str]
    description: str
    regions: list[RegionStats]
