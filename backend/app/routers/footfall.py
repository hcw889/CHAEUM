"""
추천 매물 주변 유동인구 조회 API.

유동인구 시각화 화면(/diagnosis/[id]#visualize)의 "주변 유동인구" 대시보드가 쓴다.
구역 값은 우선순위대로 고른다:
  1. footfall_measured.json — 사람이 상권정보시스템에서 전사한 실측 (app/services/footfall_measured.py)
  2. SK open API (app/services/sk_footfall.py, 키 있을 때)
  3. mock — 구역 특성 기반 가상 수치
이 라우터는 구역 선별/집계/응답 스키마만 책임진다.
"""

from __future__ import annotations

from datetime import date as date_cls, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.footfall import FootfallResponse
from app.services import footfall_measured, sk_footfall
from app.services.building_location import get_building_location
from app.services.data_provider import DataProvider, get_data_provider

router = APIRouter(prefix="/api", tags=["footfall"])

# SK 유동인구 데이터는 집계 지연이 있어 최근 날짜는 비어 올 수 있다. 일주일 전을 기준일로 잡는다.
DATA_LAG_DAYS = 7
SOURCE_LABELS = {
    "sk_api": "SK open API 유동인구",
    # footfall_areas.json의 행정동 인구(resident_population) x 구역 성격 계수 (sk_footfall.estimated_daily_total)
    "mock": "행정동 주민등록 인구 기반 추정 유동인구",
}
# 키는 설정됐는데 값이 전부 mock으로 떨어진 경우 — 엔드포인트/지역코드 설정을 봐야 한다.
FALLBACK_NOTE = "SK 키는 인식됐지만 응답을 받지 못해 행정동 인구 기반 추정치로 표시 중입니다 (/api/footfall/status 참고)."
# 일부 구역만 전사가 끝난 경우 — 어느 구역이 추정치인지 화면에 밝힌다.
PARTIAL_NOTE = "{names} 구역은 아직 실측 전사 전이라 추정치입니다 (footfall_measured.json)."


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
    데모 매물(b1~b15)은 footfall_areas.json의 대표 좌표를, 실데이터 매물은 매물 레코드의
    lat/lng(상가정보 API 좌표)를 쓴다 — 매칭 지도(building_location)와 같은 점을 가리켜야 한다.
    직접 입력으로 만들어진 매물이면 매핑된 데모 시나리오 또는 지역명으로 되짚는다.
    """
    centers = config["buildings"]
    if building_id in centers:
        return centers[building_id]

    building = provider.get_building(building_id)
    if building:
        scenario = building.get("matched_scenario_id")
        if scenario in centers:
            return centers[scenario]
        # 예전에는 데모 표와 지역명만 봐서 실데이터 모드(region이 비어 있고 id가 r…)에서
        # 전부 404가 나고 /diagnosis/[id]#visualize 지도가 비어 있었다.
        location = get_building_location(building)
        if location is not None:
            return {"lat": location.lat, "lng": location.lng, "region": building.get("region") or None}
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
        # 사람이 전사한 실측 진행 현황. errors에 뜬 구역은 규격에 안 맞아 무시되고 있다.
        "measured": footfall_measured.coverage(areas, sk_footfall.PROFILES),
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
        profile = sk_footfall.PROFILES.get(area.get("profile"), sk_footfall.PROFILES[sk_footfall.DEFAULT_PROFILE])
        measured = footfall_measured.area_hourly(area, day_type, profile["curve"])
        if measured is not None:
            hourly, source, reference_month = measured["hourly"], "measured", measured["reference_month"]
        else:
            hourly, area_is_mock = sk_footfall.area_hourly(area, day_type, reference_date)
            source, reference_month = ("mock" if area_is_mock else "sk_api"), None
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
                "is_mock": source == "mock",
                "source": source,
                "reference_month": reference_month,
                "admin_dong": area.get("admin_dong"),
                "resident_population": area.get("resident_population"),
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
    measured_areas = [a for a in areas if a["source"] == "measured"]
    estimated_areas = [a for a in areas if a["source"] != "measured"]

    if measured_areas:
        source_label = footfall_measured.source_label()
        note = PARTIAL_NOTE.format(names="·".join(a["name"] for a in estimated_areas)) if estimated_areas else None
        # 구역마다 기준월이 다를 수 있으니 가장 최근 것을 대표로 쓴다.
        months = [a["reference_month"] for a in measured_areas if a["reference_month"]]
        reference_month = max(months) if months else config["data_reference_month"]
    else:
        source_label = SOURCE_LABELS["mock"] if all_mock else SOURCE_LABELS["sk_api"]
        note = FALLBACK_NOTE if all_mock and sk_footfall.resolve_mode() == "sk_api" else None
        reference_month = config["data_reference_month"]

    return {
        "building_id": building_id,
        "address": building.get("address") if building else None,
        "region": center.get("region"),
        "mode": sk_footfall.resolve_mode(),
        "is_mock": all_mock,
        "source_label": source_label,
        "note": note,
        "measured_count": len(measured_areas),
        "day_type": day_type,
        "date": reference_date,
        "data_reference_month": reference_month,
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
