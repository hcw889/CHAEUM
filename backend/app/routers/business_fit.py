from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import BusinessFitCandidate
from app.services.data_provider import DataProvider, get_data_provider
from app.services.scoring import calculate_fit_score

router = APIRouter(prefix="/api", tags=["business-fit"])

RANK_LABELS = ["gold", "silver", "bronze"]


def _compute_candidates(building: dict, market_data: dict, provider: DataProvider) -> list[dict]:
    candidates = []
    for business_type, raw_market in market_data.items():
        result = calculate_fit_score(building, business_type, raw_market)
        candidates.append(
            {
                "type": business_type,
                "fit_score": result["fit_score"],
                "score_breakdown": result["breakdown"],
                "estimated_rent": raw_market.get("estimated_rent", 0),
                "required_permits": provider.get_permits(business_type),
            }
        )
    candidates.sort(key=lambda c: c["fit_score"], reverse=True)
    for i, c in enumerate(candidates):
        c["rank"] = RANK_LABELS[i] if i < len(RANK_LABELS) else None
    return candidates


@router.get("/business-types", response_model=list[str])
def list_business_types(provider: DataProvider = Depends(get_data_provider)):
    return provider.list_business_types()


@router.get("/buildings/{building_id}/business-fit", response_model=list[BusinessFitCandidate])
def get_business_fit(building_id: str, provider: DataProvider = Depends(get_data_provider)):
    building = provider.get_building(building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")
    market_data = provider.get_market_data(building_id)
    return _compute_candidates(building, market_data, provider)
