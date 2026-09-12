"""매칭 지도용 위치. 유동인구 API 호출 없이 기존 데모 좌표만 읽는다."""

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
    centers = _demo_locations()
    center = centers.get(building["id"]) or centers.get(building.get("matched_scenario_id"))
    if center is None:
        return None
    try:
        return BuildingLocation(lat=center["lat"], lng=center["lng"], is_approximate=True)
    except (KeyError, ValueError, TypeError):
        return None
