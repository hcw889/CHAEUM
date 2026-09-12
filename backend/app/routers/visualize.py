from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import SpaceRenderRequest, SpaceRenderResponse
from app.services import space_render
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api", tags=["visualize"])


@router.get("/visualize/mode")
def get_render_mode():
    """
    현재 이미지 생성 모드를 알려준다. 프론트가 "실제 생성" / "미리보기"를
    사전에 구분해 안내 문구를 띄우는 용도.
    """
    return {"mode": space_render.resolve_mode()}


@router.post("/buildings/{building_id}/visualize", response_model=SpaceRenderResponse)
def visualize_building(
    building_id: str,
    payload: SpaceRenderRequest,
    provider: DataProvider = Depends(get_data_provider),
):
    """
    공실 사진 + 컨셉 -> 적용 후 이미지 생성.

    팝업 브랜드가 입지를 고르는 단계에서 "이 공간이 내 팝업을 구현하기에 맞는가"를
    눈으로 확인하기 위한 화면(/visualize/[id])용 엔드포인트이며, 매칭 flow의
    /api/match 파이프라인과는 서로 호출하지 않는 독립 경로다.
    """
    building = provider.get_building(building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="건물을 찾을 수 없습니다.")

    result = space_render.render_space(
        concept=payload.concept,
        photo_data_url=payload.photo_data_url,
        mask_data_url=payload.mask_data_url,
        commercial_style_pref=payload.commercial_style_pref,
        occupancy_term=payload.occupancy_term,
        strength=payload.strength,
        building=building,
    )
    return SpaceRenderResponse(**result)
