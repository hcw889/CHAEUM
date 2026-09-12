"""
매칭 지도용 위치.

매물 레코드에 lat/lng가 있으면 그 값을 쓴다 — 실데이터(상가정보 API 좌표)와
지오코딩된 목업 모두 해당한다. 없으면 footfall_areas.json의 데모 대표 좌표(b1~b15)로
내려간다. 예전에는 데모 표만 봐서 실데이터 모드에서 모든 매물의 location이 null이
되고 /match/results 지도가 비어 있었다.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.models.schemas import BuildingLocation

logger = logging.getLogger(__name__)
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "footfall_areas.json"


@lru_cache(maxsize=1)
def _demo_locations() -> dict:
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))["buildings"]
    except (OSError, ValueError, KeyError) as exc:
        logger.warning("매물 지도 좌표를 읽지 못했습니다: %s", exc)
        return {}


def get_building_location(building: dict) -> BuildingLocation | None:
    # 실데이터 매물(vacancy 필드가 있다)은 상가정보 API가 준 건물 좌표를 그대로 쓴다.
    if "vacancy" in building:
        lat, lng = building.get("lat"), building.get("lng")
        if lat is None or lng is None:
            return None
        try:
            return BuildingLocation(lat=lat, lng=lng, is_approximate=False)
        except (ValueError, TypeError):
            return None

    # 목업은 유동인구 화면과 같은 데모 대표 좌표를 쓴다 (매칭 지도·유동인구 지도가
    # 같은 점을 가리켜야 한다).
    centers = _demo_locations()
    center = centers.get(building["id"]) or centers.get(building.get("matched_scenario_id"))
    if center is None:
        return None
    try:
        return BuildingLocation(lat=center["lat"], lng=center["lng"], is_approximate=True)
    except (KeyError, ValueError, TypeError):
        return None
