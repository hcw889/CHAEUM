from fastapi import APIRouter, Depends

from app.models.regions import RegionStatsResponse
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api/regions", tags=["regions"])


@router.get("/stats", response_model=RegionStatsResponse)
def get_region_stats(provider: DataProvider = Depends(get_data_provider)):
    data = provider.get_region_stats()
    regions = []
    for item in data["regions"]:
        total = item["total_units"]
        history = item["monthly_vacant_units"]
        if total <= 0 or len(history) != len(data["months"]) or not history:
            raise ValueError("Invalid region statistics")
        if any(count < 0 or count > total for count in history):
            raise ValueError("Vacant units must be between zero and total units")
        regions.append({
            **item,
            "vacant_units": history[-1],
            "vacancy_rate": round(history[-1] / total * 100, 1),
            "vacancy_trend_6m": [round(count / total * 100, 1) for count in history],
        })
    return {**data, "regions": regions}
