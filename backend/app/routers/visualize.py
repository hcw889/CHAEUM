from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import BuildingPhotoResponse, SpaceRenderRequest, SpaceRenderResponse
from app.services import building_photo, space_render
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api", tags=["visualize"])


@router.get("/visualize/mode")
def get_render_mode():
    """
    현재 이미지 생성 모드를 알려준다. 프론트가 "실제 생성" / "미리보기"를
    사전에 구분해 안내 문구를 띄우는 용도.
    """
    return {"mode": space_render.resolve_mode()}


@router.get("/buildings/{building_id}/photo", response_model=BuildingPhotoResponse)
def get_building_photo(building_id: str, provider: DataProvider = Depends(get_data_provider)):
    """
    매물에 딸린 공간 사진. 시각화 화면이 "현재" 이미지로 바로 띄운다.

    사용자(팝업 브랜드·예비창업자)는 공간을 찾는 쪽이라 공실 사진을 갖고 있지 않다.
    실제 촬영본이 app/data/photos/에 있으면 그것을, 없으면 매물 속성으로 그린
    참고용 이미지를 돌려준다 (source 필드로 구분).
    """
    building = provider.get_building(building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="건물을 찾을 수 없습니다.")

    image, source = building_photo.load_photo(building)
    return BuildingPhotoResponse(
        image=space_render.to_data_url(image),
        source=source,
        has_after=building_photo.find_after_file(building_id) is not None,
    )


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
