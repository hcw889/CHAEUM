from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import ReportSummary
from app.routers.business_fit import _compute_candidates
from app.routers.dashboard import get_dashboard
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api/buildings", tags=["report"])


@router.get("/{building_id}/report", response_model=ReportSummary)
def get_report(building_id: str, provider: DataProvider = Depends(get_data_provider)):
    building = provider.get_building(building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")

    market_data = provider.get_market_data(building_id)
    candidates = _compute_candidates(building, market_data, provider)
    top_business = candidates[0]
    dashboard = get_dashboard(building_id, provider)

    return ReportSummary(
        building=building,
        top_business=top_business,
        dashboard=dashboard,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
