from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import DashboardMetrics
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api/buildings", tags=["dashboard"])


@router.get("/{building_id}/dashboard", response_model=DashboardMetrics)
def get_dashboard(building_id: str, provider: DataProvider = Depends(get_data_provider)):
    building = provider.get_building(building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")

    market_data = provider.get_market_data(building_id)
    if not market_data:
        raise HTTPException(status_code=404, detail="Market data not found")

    saturations = [v["competition_saturation_index"] for v in market_data.values()]
    rents = [v["estimated_rent"] for v in market_data.values()]
    foot_traffics = [v["foot_traffic_index"] for v in market_data.values()]
    top_competition_type = max(market_data.items(), key=lambda kv: kv[1]["competition_saturation_index"])[0]

    return DashboardMetrics(
        avg_competition_saturation=round(sum(saturations) / len(saturations), 1),
        avg_estimated_rent=round(sum(rents) / len(rents)),
        avg_foot_traffic=round(sum(foot_traffics) / len(foot_traffics), 1),
        top_competition_type=top_competition_type,
    )
