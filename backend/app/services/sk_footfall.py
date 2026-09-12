"""
채움(Chaeum) 주변 유동인구 — SK open API 유동인구 상품 연동.

매칭 결과 화면에서 "추천된 매물 주변에 사람이 실제로 얼마나 다니는가"를
시간대별 색상 지도로 보여주기 위한 서비스다. 매칭 스코어링(match.py)과는
독립적이며, 이 모듈이 실패해도 매칭 결과 화면은 그대로 동작해야 한다.

실행 모드는 space_render.py와 같은 방식으로 폴백한다.

    sk_api : SK_OPENAPI_APP_KEY 있음 -> SK open API 유동인구 호출.
             구역별로 응답을 받아 24시간 배열로 정규화한다.
    mock   : 키 없음 / 호출 실패 / 파싱 실패 -> 구역 특성 기반 가상 수치.

SK open API 유동인구 상품은 상세 스펙이 콘솔 로그인 뒤에만 공개되어 있고
계약 상품에 따라 엔드포인트와 응답 필드명이 달라진다. 그래서 URL을 환경변수로
빼두고, 응답 파싱은 "시(hour)처럼 보이는 키 + 인구처럼 보이는 키"를 재귀로 찾는
느슨한 방식으로 처리한다. 실제 응답 예시를 확보하면 _parse_hourly()만
엄격하게 바꾸면 된다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "footfall_areas.json"

DEFAULT_BASE_URL = "https://apis.openapi.sk.com"
# 계약 상품에 맞춰 .env에서 덮어쓴다. {area_code} {date} {lat} {lng} {radius} 치환 가능.
DEFAULT_AREA_PATH = "/puzzle/pop/raw/hourly/districts/{area_code}"
DEFAULT_COORD_PATH = ""  # 좌표 기반 엔드포인트를 쓰는 상품이면 .env에서 지정

HOUR_KEYS = ("hour", "hh", "time", "tmzon", "stdhour", "hourcd")
VALUE_KEYS = ("population", "pop", "value", "cnt", "count", "total", "totpop", "flowpop", "fpopcnt")

CACHE_TTL_SEC = 600
_cache: dict[str, tuple[float, list[int]]] = {}

# 구역 성격별 24시간 분포 가중치와 일 유동인구 기준 규모.
# mock 모드에서만 쓰이며, 실제 API가 붙으면 사용되지 않는다.
PROFILES: dict[str, dict[str, Any]] = {
    "commercial": {
        "label": "상업지",
        "base": 18000,
        "weekend": 1.15,
        "curve": [0.4, 0.2, 0.1, 0.1, 0.2, 0.6, 1.5, 3.0, 4.2, 4.5, 5.0, 6.2,
                  7.0, 6.4, 6.0, 6.2, 6.8, 7.6, 8.2, 7.4, 6.0, 4.2, 2.6, 1.2],
    },
    "market": {
        "label": "전통시장",
        "base": 12000,
        "weekend": 1.05,
        "curve": [0.2, 0.1, 0.1, 0.2, 0.8, 2.0, 4.0, 5.5, 6.5, 7.2, 7.6, 7.8,
                  7.4, 7.0, 6.6, 6.0, 5.4, 4.6, 3.6, 2.4, 1.4, 0.8, 0.4, 0.2],
    },
    "tourism": {
        "label": "관광지",
        "base": 15000,
        "weekend": 1.6,
        "curve": [0.2, 0.1, 0.1, 0.1, 0.2, 0.4, 0.9, 1.8, 3.0, 4.6, 6.4, 7.8,
                  8.4, 8.6, 8.4, 8.0, 7.4, 6.6, 5.6, 4.2, 3.0, 2.0, 1.2, 0.6],
    },
    "station": {
        "label": "역세권",
        "base": 21000,
        "weekend": 0.9,
        "curve": [0.6, 0.3, 0.2, 0.2, 0.6, 2.2, 4.6, 6.4, 6.0, 4.8, 4.4, 4.6,
                  5.0, 4.8, 4.6, 5.0, 5.8, 7.2, 7.8, 6.4, 5.0, 4.0, 2.6, 1.4],
    },
    "office": {
        "label": "업무지구",
        "base": 13000,
        "weekend": 0.45,
        "curve": [0.2, 0.1, 0.1, 0.1, 0.3, 1.0, 2.6, 5.6, 8.2, 7.4, 7.0, 7.2,
                  8.0, 7.2, 6.8, 6.6, 6.4, 7.4, 6.0, 4.0, 2.6, 1.6, 0.9, 0.4],
    },
    "academy": {
        "label": "학원가",
        "base": 9000,
        "weekend": 0.7,
        "curve": [0.2, 0.1, 0.1, 0.1, 0.2, 0.5, 1.4, 3.4, 4.0, 4.2, 4.6, 5.0,
                  5.2, 5.6, 6.4, 7.0, 7.6, 8.2, 8.6, 8.0, 6.4, 4.2, 2.4, 1.0],
    },
    "youth": {
        "label": "청년상권",
        "base": 11000,
        "weekend": 1.35,
        "curve": [1.2, 0.8, 0.4, 0.2, 0.2, 0.3, 0.8, 1.6, 2.4, 3.0, 3.6, 4.6,
                  5.4, 5.2, 5.0, 5.4, 6.2, 7.4, 8.4, 8.8, 8.4, 7.0, 4.8, 2.6],
    },
    "residential": {
        "label": "주거지",
        "base": 7000,
        "weekend": 0.95,
        "curve": [0.6, 0.3, 0.2, 0.2, 0.6, 1.8, 3.8, 5.6, 5.0, 4.2, 4.0, 4.4,
                  4.8, 4.4, 4.2, 4.6, 5.4, 7.0, 8.0, 7.4, 6.2, 4.6, 3.0, 1.6],
    },
}
DEFAULT_PROFILE = "commercial"


def load_areas() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def app_key() -> Optional[str]:
    key = (os.environ.get("SK_OPENAPI_APP_KEY") or "").strip()
    return key or None


def resolve_mode() -> str:
    """SK_FOOTFALL_MODE=sk_api|mock 로 강제 지정 가능. 미지정이면 키 유무로 결정."""
    forced = (os.environ.get("SK_FOOTFALL_MODE") or "").strip().lower()
    if forced in {"sk_api", "mock"}:
        return forced
    return "sk_api" if app_key() else "mock"


def profile_label(area: dict) -> str:
    profile = PROFILES.get(area.get("profile", DEFAULT_PROFILE), PROFILES[DEFAULT_PROFILE])
    return profile["label"]


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def nearby_areas(center: dict, areas: list[dict], radius_m: float, minimum: int, maximum: int) -> list[dict]:
    """
    반경 안의 구역을 가까운 순으로 고른다.
    반경 안이 너무 적으면 가까운 순으로 minimum개까지 채우고,
    지도가 읽기 어려워지지 않도록 maximum개에서 끊는다.
    """
    ranked = sorted(
        (
            {**area, "distance_m": round(haversine_m(center["lat"], center["lng"], area["lat"], area["lng"]))}
            for area in areas
        ),
        key=lambda a: a["distance_m"],
    )
    within = [a for a in ranked if a["distance_m"] <= radius_m]
    selected = within if len(within) >= minimum else ranked[:minimum]
    return selected[:maximum]


# --- SK open API 호출 ---------------------------------------------------------


def _endpoint(area: dict, date: str) -> Optional[str]:
    base = (os.environ.get("SK_FOOTFALL_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    area_path = os.environ.get("SK_FOOTFALL_AREA_PATH", DEFAULT_AREA_PATH)
    coord_path = os.environ.get("SK_FOOTFALL_COORD_PATH", DEFAULT_COORD_PATH)

    if area.get("sk_area_code") and area_path:
        path = area_path
    elif coord_path:
        path = coord_path
    else:
        # 지역코드도 없고 좌표 엔드포인트도 지정되지 않았다 -> 호출할 URL을 만들 수 없다.
        return None

    return base + path.format(
        area_code=area.get("sk_area_code") or "",
        date=date,
        lat=area["lat"],
        lng=area["lng"],
        radius=int(area.get("radius_m", 250)),
    )


def _iter_dicts(node: Any) -> Iterable[dict]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_dicts(item)


def _first_number(entry: dict, keys: tuple[str, ...]) -> Optional[float]:
    for key, value in entry.items():
        if isinstance(value, (int, float, str)) and key.lower().replace("_", "") in keys:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _parse_hourly(payload: Any) -> Optional[list[int]]:
    """
    응답 어딘가에 있는 '시간 + 인구' 쌍들을 찾아 24칸 배열로 만든다.
    상품별 응답 구조 차이를 흡수하기 위한 느슨한 파서이며,
    24시간 중 절반 이상이 채워지지 않으면 실패로 본다.
    """
    hours: dict[int, float] = {}
    for entry in _iter_dicts(payload):
        hour = _first_number(entry, HOUR_KEYS)
        value = _first_number(entry, VALUE_KEYS)
        if hour is None or value is None:
            continue
        index = int(hour)
        if 0 <= index <= 23:
            hours[index] = hours.get(index, 0.0) + value
    if len(hours) < 12:
        return None
    return [int(round(hours.get(hour, 0.0))) for hour in range(24)]


def fetch_area_hourly(area: dict, date: str) -> Optional[list[int]]:
    """구역 하나의 시간대별 유동인구. 실패하면 None을 돌려주고 호출부가 mock으로 폴백한다."""
    key = app_key()
    url = _endpoint(area, date)
    if not key or not url:
        return None

    cache_key = f"{area['id']}:{date}:{url}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_TTL_SEC:
        return cached[1]

    try:
        import httpx

        response = httpx.get(
            url,
            headers={"appKey": key, "accept": "application/json"},
            params={"date": date},
            timeout=4.0,
        )
        response.raise_for_status()
        hourly = _parse_hourly(response.json())
    except Exception as exc:  # 데모 중 화면이 죽지 않는 것이 최우선이다.
        logger.warning("SK 유동인구 호출 실패 (%s): %s", area["id"], exc)
        return None

    if hourly is None:
        logger.warning("SK 유동인구 응답에서 시간대 값을 찾지 못했다 (%s)", area["id"])
        return None

    _cache[cache_key] = (time.time(), hourly)
    return hourly


# --- mock 생성 ----------------------------------------------------------------


def mock_area_hourly(area: dict, day_type: str) -> list[int]:
    """구역 id를 시드로 한 결정적 가상 수치. 같은 입력이면 항상 같은 값이 나온다."""
    profile = PROFILES.get(area.get("profile", DEFAULT_PROFILE), PROFILES[DEFAULT_PROFILE])
    digest = hashlib.sha256(f"{area['id']}:{day_type}".encode("utf-8")).digest()
    scale = profile["base"] * (0.85 + (digest[0] / 255) * 0.3)
    if day_type == "weekend":
        scale *= profile["weekend"]

    curve = profile["curve"]
    total_weight = sum(curve)
    hourly = []
    for hour, weight in enumerate(curve):
        jitter = 0.92 + (digest[hour + 1] / 255) * 0.16
        hourly.append(int(round(scale * (weight / total_weight) * jitter)))
    return hourly


def area_hourly(area: dict, day_type: str, date: str) -> tuple[list[int], bool]:
    """(시간대별 값, is_mock). sk_api 모드여도 구역 단위로 실패하면 그 구역만 mock이 된다."""
    if resolve_mode() == "sk_api":
        fetched = fetch_area_hourly(area, date)
        if fetched is not None:
            return fetched, False
    return mock_area_hourly(area, day_type), True
