from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import Building, BuildingSummary, PropertyInput
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api/buildings", tags=["buildings"])


@router.get("", response_model=list[BuildingSummary])
def list_buildings(provider: DataProvider = Depends(get_data_provider)):
    """데모 시나리오 피커용 건물 목록."""
    return provider.list_buildings()


@router.post("/diagnose", response_model=Building)
def diagnose_building(payload: PropertyInput, provider: DataProvider = Depends(get_data_provider)):
    """매물 입력 화면에서 호출. 주소를 기반으로 mock 진단 결과를 반환한다."""
    building = provider.create_building_from_input(
        address=payload.address,
        floor=payload.floor,
        area_pyeong=payload.area_pyeong,
        has_photo=payload.has_photo,
    )
    return building


@router.get("/{building_id}", response_model=Building)
def get_building(building_id: str, provider: DataProvider = Depends(get_data_provider)):
    building = provider.get_building(building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return building
