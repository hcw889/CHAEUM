from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.schemas import PermitChecklistItem
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api/buildings", tags=["permits"])


@router.get("/{building_id}/permits", response_model=list[PermitChecklistItem])
def get_permits(
    building_id: str,
    business_type: str = Query(..., description="예: 카페, 학원, 병원, 편의점, 스터디카페"),
    provider: DataProvider = Depends(get_data_provider),
):
    building = provider.get_building(building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")

    permits = provider.get_permits(business_type)
    if not permits:
        raise HTTPException(status_code=404, detail="No permits found for business type")
    return [PermitChecklistItem(label=p) for p in permits]
