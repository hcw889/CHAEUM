"""
추천 매물 주변 유동인구 조회 API.

매칭 결과 화면(/match/results)의 "주변 유동인구" 대시보드가 쓴다.
데이터 획득은 app/services/sk_footfall.py가 담당하며(SK open API -> 실패 시 mock),
이 라우터는 구역 선별/집계/응답 스키마만 책임진다.
"""

from __future__ import annotations

from datetime import date as date_cls, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.footfall import FootfallResponse
from app.services import sk_footfall
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api", tags=["footfall"])

# SK 유동인구 데이터는 집계 지연이 있어 최근 날짜는 비어 올 수 있다. 일주일 전을 기준일로 잡는다.
DATA_LAG_DAYS = 7
SOURCE_LABELS = {
    "sk_api": "SK open API 유동인구",
    "mock": "시연용 가상 유동인구",
}
# 키는 설정됐는데 값이 전부 mock으로 떨어진 경우 — 엔드포인트/지역코드 설정을 봐야 한다.
FALLBACK_NOTE = "SK 키는 인식됐지만 응답을 받지 못해 가상 수치로 표시 중입니다 (/api/footfall/status 참고)."


def _reference_date(day_type: str) -> str:
    """기준일에서 거꾸로 훑어 day_type(평일/주말)에 맞는 가장 가까운 날짜를 고른다."""
    cursor = date_cls.today() - timedelta(days=DATA_LAG_DAYS)
    for _ in range(7):
        is_weekend = cursor.weekday() >= 5
        if (day_type == "weekend") == is_weekend:
            break
        cursor -= timedelta(days=1)
    return cursor.strftime("%Y%m%d")


def _resolve_center(building_id: str, config: dict, provider: DataProvider) -> dict:
    """
    building_id -> 지도 중심 좌표.
    직접 입력으로 만들어진 매물이면 지역명 또는 매핑된 데모 시나리오로 되짚는다.
    """
    centers = config["buildings"]
    if building_id in centers:
        return centers[building_id]

    building = provider.get_building(building_id)
    if building:
        scenario = building.get("matched_scenario_id")
        if scenario in centers:
            return centers[scenario]
        region = building.get("region")
        for center in centers.values():
            if center.get("region") == region:
                return center

    raise HTTPException(status_code=404, detail="유동인구를 조회할 매물을 찾지 못했습니다.")


@router.get("/footfall/status")
def get_footfall_status():
    """
    SK open API 키 연결 상태 점검용. 화면이 아니라 사람이 확인하려고 쓰는 엔드포인트다.
    브라우저에서 http://localhost:8000/api/footfall/status 로 열어 본다.
    """
    config = sk_footfall.load_areas()
    areas = config["areas"]
    with_code = [area for area in areas if area.get("sk_area_code")]
    sample = sk_footfall._endpoint(areas[0], _reference_date("weekday"))
    return {
        "mode": sk_footfall.resolve_mode(),
        "app_key_detected": sk_footfall.app_key() is not None,
        "areas_total": len(areas),
        "areas_with_sk_area_code": len(with_code),
        "sample_request_url": sample,
        "hint": _status_hint(sample),
    }


def _status_hint(sample_url: str | None) -> str:
    if sk_footfall.resolve_mode() == "mock":
        return "SK_OPENAPI_APP_KEY가 비어 있습니다. backend/.env에 키를 넣고 서버를 다시 시작하세요."
    if sample_url is None:
        return (
            "키는 인식됐지만 호출할 URL을 만들 수 없습니다. "
            "footfall_areas.json의 sk_area_code를 채우거나 SK_FOOTFALL_COORD_PATH를 지정하세요."
        )
    return "키와 엔드포인트가 준비됐습니다. 호출이 실패하면 서버 로그의 '유동인구 호출 실패' 경고를 확인하세요."


@router.get("/buildings/{building_id}/footfall", response_model=FootfallResponse)
def get_building_footfall(
    building_id: str,
    day_type: str = Query("weekday", pattern="^(weekday|weekend)$"),
    provider: DataProvider = Depends(get_data_provider),
):
    config = sk_footfall.load_areas()
    center = _resolve_center(building_id, config, provider)
    reference_date = _reference_date(day_type)

    selected = sk_footfall.nearby_areas(
        center, config["areas"], config["search_radius_m"], config["min_areas"], config["max_areas"]
    )

    areas = []
    for area in selected:
        hourly, area_is_mock = sk_footfall.area_hourly(area, day_type, reference_date)
        daily_total = sum(hourly)
        areas.append(
            {
                "id": area["id"],
                "name": area["name"],
                "lat": area["lat"],
                "lng": area["lng"],
                "radius_m": area["radius_m"],
                "profile": area["profile"],
                "profile_label": sk_footfall.profile_label(area),
                "distance_m": area["distance_m"],
                "hourly": hourly,
                "daily_total": daily_total,
                "peak_hour": max(range(24), key=lambda h: hourly[h]),
                "share_pct": 0.0,  # 아래에서 전체 합계가 나온 뒤 채운다
                "is_mock": area_is_mock,
            }
        )

    total = sum(a["daily_total"] for a in areas)
    for area in areas:
        area["share_pct"] = round(area["daily_total"] / total * 100, 1) if total else 0.0

    hour_totals = [sum(a["hourly"][hour] for a in areas) for hour in range(24)]
    peak_hour = max(range(24), key=lambda h: hour_totals[h]) if total else 0
    top_area = max(areas, key=lambda a: a["daily_total"])
    peak_area = max(areas, key=lambda a: a["hourly"][peak_hour])

    building = provider.get_building(building_id)
    all_mock = all(a["is_mock"] for a in areas)

    return {
        "building_id": building_id,
        "address": building.get("address") if building else None,
        "region": center.get("region"),
        "mode": sk_footfall.resolve_mode(),
        "is_mock": all_mock,
        "source_label": SOURCE_LABELS["mock"] if all_mock else SOURCE_LABELS["sk_api"],
        "note": FALLBACK_NOTE if all_mock and sk_footfall.resolve_mode() == "sk_api" else None,
        "day_type": day_type,
        "date": reference_date,
        "data_reference_month": config["data_reference_month"],
        "description": config["description"],
        "center_lat": center["lat"],
        "center_lng": center["lng"],
        "search_radius_m": config["search_radius_m"],
        "areas": areas,
        "summary": {
            "daily_total": total,
            "peak_hour": peak_hour,
            "peak_area_name": peak_area["name"],
            "top_area_name": top_area["name"],
            "walkable_total": sum(a["daily_total"] for a in areas if a["distance_m"] <= 500),
            "max_area_daily": top_area["daily_total"],
        },
    }
