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
