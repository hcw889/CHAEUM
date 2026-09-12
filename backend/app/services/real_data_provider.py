"""
RealSanggaProvider — 실데이터(상가정보 + 건축물대장)로 만든 공실 매물을 제공한다.

scripts/fetch_real_vacancies.py가 app/data/real/ 에 써 둔 캐시를 읽는다. 런타임에
API를 호출하지 않는 이유는 두 가지다:
  - 건축물대장은 건물당 2회 호출이라, 매칭 요청마다 돌리면 응답이 수십 초가 된다
  - 공공데이터포털 개발계정은 일일 호출 한도가 있어 데모 중 소진될 수 있다

캐시가 없으면 get_data_provider()가 MockDataProvider로 폴백하므로, 이 클래스는
캐시가 있다는 전제만 지킨다.

DataProvider 인터페이스를 그대로 구현하므로 라우터/스코어링은 수정할 필요가 없다.
다만 get_data_sources()는 의미 있게 오버라이드한다 — 어떤 필드가 실데이터이고
어떤 필드가 추정인지 화면에 배지로 표시하기 위해서다.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

from app.services.data_provider import DATA_DIR, DataProvider

logger = logging.getLogger(__name__)

REAL_DIR = DATA_DIR / "real"

# 출처 배지 문구. 값이 "추정값"으로 시작하면 프론트가 회색 배지로 구분한다.
SANGGA_LABEL = "실데이터 · 소상공인시장진흥공단 상가(상권)정보"
REGISTER_LABEL = "실데이터 · 국토교통부 건축HUB 건축물대장"
JOIN_LABEL = "추정값 · 상가정보 × 건축물대장 조인"

# 필드별 출처. 두 API가 실제로 제공하는 것과 우리가 계산한 것을 구분한다.
DATA_SOURCE_MAP: dict[str, str] = {
    "built_year": REGISTER_LABEL + " (사용승인일)",
    "area_pyeong": REGISTER_LABEL + " (층별 전용면적)",
    "floor": REGISTER_LABEL + " (층별개요)",
    "register_purpose": REGISTER_LABEL + " (층 주용도)",
    "structure": REGISTER_LABEL + " (구조)",
    "elevators": REGISTER_LABEL + " (승강기)",
    "address": SANGGA_LABEL + " (소재지)",
    "lat": SANGGA_LABEL + " (좌표)",
    "lng": SANGGA_LABEL + " (좌표)",
    "nearby_stores": SANGGA_LABEL + " (인근 영업 점포)",
    "competition_saturation_index": SANGGA_LABEL + " (반경 300m 동일업종 점포 수)",
    "aging_score": "실데이터 기반 계산 · 사용승인일 경과연수",
    "accessibility_score": "실데이터 기반 계산 · 층수 + 승강기",
    "vacancy": JOIN_LABEL + " (층별 미등록 추론)",
    "lighting_score": "추정값 · 층/면적 휴리스틱 (일조 데이터 없음)",
    "foot_traffic_index": "추정값 · 상가 밀도 프록시",
    "demographic_fit_index": "추정값 · 인근 업종 구성 프록시",
    "estimated_rent": "추정값 · 면적 × 시군 기준단가 × 층 계수",
}

_MARKET_KEYS = (
    "foot_traffic_index",
    "competition_saturation_index",
    "demographic_fit_index",
    "estimated_rent",
)


def cache_is_available(real_dir: Path = REAL_DIR) -> bool:
    """수집 스크립트가 남긴 캐시가 온전한지. get_data_provider()가 이걸로 분기한다."""
    return all(
        (real_dir / name).is_file()
        for name in ("buildings.json", "market_data.json", "region_stats.json")
    )


class RealSanggaProvider(DataProvider):
    def __init__(self, real_dir: Path = REAL_DIR, data_dir: Path = DATA_DIR):
        self._real_dir = real_dir
        self._data_dir = data_dir

        self._buildings: dict[str, Any] = _read_json(real_dir / "buildings.json")
        self._market_data: dict[str, Any] = _read_json(real_dir / "market_data.json")
        self._region_stats: dict[str, Any] = _read_json(real_dir / "region_stats.json")
        self._meta: dict[str, Any] = (
            _read_json(real_dir / "meta.json") if (real_dir / "meta.json").is_file() else {}
        )
        # 인허가 요건은 두 API가 주지 않는 법령 정보라 기존 목업 JSON을 그대로 쓴다.
        self._permits: dict[str, Any] = _read_json(data_dir / "permits.json")

        logger.info(
            "RealSanggaProvider: 매물 %d건 / 지역 %d개 (수집 %s)",
            len(self._buildings),
            len(self._region_stats.get("regions", [])),
            self._meta.get("collected_at", "미상"),
        )

    # --- DataProvider 구현 ----------------------------------------------------

    def list_business_types(self) -> list[str]:
        return list(self._permits.keys())

    def get_region_stats(self) -> dict[str, Any]:
        return self._region_stats

    def list_buildings(self) -> list[dict[str, Any]]:
        return [
            {
                "id": building["id"],
                "name": building["name"],
                "address": building["address"],
                "risk_grade": building["risk_grade"],
                "thumbnail_color": building.get("thumbnail_color", "#EEEEEE"),
            }
            for building in self._buildings.values()
        ]

    def get_building(self, building_id: str) -> Optional[dict[str, Any]]:
        return self._buildings.get(building_id)

    def create_building_from_input(
        self,
        address: str,
        floor: Optional[int] = None,
        area_pyeong: Optional[float] = None,
        has_photo: bool = False,
    ) -> dict[str, Any]:
        """
        사용자가 입력한 주소로 수집된 공실 매물을 찾는다.

        캐시는 전북 전역 표본이라 임의 주소가 항상 들어 있지는 않다. 정확히
        맞는 매물이 없으면 주소 토큰이 가장 많이 겹치는 매물을 고르고,
        그것도 없으면 결정적 해시로 하나를 고른다(MockDataProvider와 동일한 폴백).
        입력된 층/평수는 사용자 입력이 우선이다.
        """
        matched = self._find_by_address(address, floor)

        building = dict(matched)
        building["address"] = address or matched["address"]
        if floor is not None:
            building["floor"] = floor
        if area_pyeong is not None:
            building["area_pyeong"] = area_pyeong
        building["matched_scenario_id"] = matched["id"]
        # 입력 주소가 캐시의 매물과 다르면 그 사실을 명시한다 (화면에서 구분 가능).
        building["address_exact_match"] = _normalize(address) in _normalize(matched["address"])
        return building

    def get_market_data(self, building_id: str) -> dict[str, dict[str, Any]]:
        return self._market_data.get(building_id, {})

    def get_permits(self, business_type: str) -> list[str]:
        return self._permits.get(business_type, [])

    def get_data_sources(self, building_id: str) -> dict[str, str]:
        """
        이 매물에 실제로 값이 채워진 필드만 출처를 돌려준다.
        값이 없는 필드에 배지를 띄우면 오히려 오해를 부른다.
        """
        building = self._buildings.get(building_id)
        if building is None:
            return {}

        sources: dict[str, str] = {}

        if building.get("built_year"):
            sources["built_year"] = DATA_SOURCE_MAP["built_year"]
        if building.get("area_pyeong"):
            sources["area_pyeong"] = DATA_SOURCE_MAP["area_pyeong"]
        if building.get("floor") is not None:
            sources["floor"] = DATA_SOURCE_MAP["floor"]
        if building.get("address"):
            sources["address"] = DATA_SOURCE_MAP["address"]
        if building.get("lat") is not None:
            sources["lat"] = DATA_SOURCE_MAP["lat"]
            sources["lng"] = DATA_SOURCE_MAP["lng"]
        if building.get("nearby_store_names"):
            sources["nearby_stores"] = DATA_SOURCE_MAP["nearby_stores"]

        register = building.get("register") or {}
        if register.get("structure"):
            sources["structure"] = DATA_SOURCE_MAP["structure"]
        if register.get("elevators"):
            sources["elevators"] = DATA_SOURCE_MAP["elevators"]

        vacancy = building.get("vacancy") or {}
        if vacancy.get("estimated"):
            sources["vacancy"] = "{} · 신뢰도 {}".format(
                DATA_SOURCE_MAP["vacancy"], _confidence_label(vacancy.get("confidence"))
            )
        if vacancy.get("register_purpose"):
            sources["register_purpose"] = DATA_SOURCE_MAP["register_purpose"]

        # 진단 3항목 — 앞의 둘은 실데이터 파생, 채광은 추정이다.
        sources["aging_score"] = DATA_SOURCE_MAP["aging_score"]
        sources["accessibility_score"] = DATA_SOURCE_MAP["accessibility_score"]
        sources["lighting_score"] = DATA_SOURCE_MAP["lighting_score"]

        # 시장 신호 — 경쟁포화도만 실측, 나머지는 추정이다.
        market = self._market_data.get(building_id) or {}
        any_entry = next(iter(market.values()), None) if market else None
        if isinstance(any_entry, dict):
            if any_entry.get("competitor_count") is not None:
                sources["competition_saturation_index"] = DATA_SOURCE_MAP[
                    "competition_saturation_index"
                ]
            for key in ("foot_traffic_index", "demographic_fit_index", "estimated_rent"):
                if key in any_entry:
                    sources[key] = DATA_SOURCE_MAP[key]

        return sources

    # --- 보조 ----------------------------------------------------------------

    @property
    def meta(self) -> dict[str, Any]:
        return self._meta

    def region_options(self) -> list[str]:
        """
        매칭 입력 화면의 '희망 지역' 선택지. 수집된 매물의 실제 지역명에서 만든다.
        매물이 없는 지역을 고르면 결과가 0건이 되므로 데이터에서 역산해야 한다.
        """
        counts: dict[str, int] = {}
        for building in self._buildings.values():
            region = (building.get("region") or "").strip()
            if region:
                counts[region] = counts.get(region, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return ["상관없음"] + [region for region, _ in ordered]

    def _find_by_address(self, address: str, floor: Optional[int]) -> dict[str, Any]:
        buildings = list(self._buildings.values())
        if not buildings:
            raise RuntimeError("수집된 매물이 없습니다. scripts/fetch_real_vacancies.py를 먼저 실행하세요.")

        query = _normalize(address)
        if query:
            # 1순위: 주소가 포함 관계이고 층까지 맞는 매물
            scored = []
            for building in buildings:
                candidate = _normalize(building.get("address", ""))
                overlap = _token_overlap(query, candidate)
                if overlap == 0:
                    continue
                floor_match = 1 if (floor is not None and building.get("floor") == floor) else 0
                scored.append((overlap + floor_match * 2, building))
            if scored:
                scored.sort(key=lambda item: item[0], reverse=True)
                return scored[0][1]

        # 폴백: 입력 주소 해시로 결정적 선택 (MockDataProvider와 같은 방식)
        digest = hashlib.sha256(address.strip().encode("utf-8")).hexdigest()
        return buildings[int(digest, 16) % len(buildings)]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    return "".join(text.split()).replace("전북특별자치도", "").replace("전라북도", "")


def _token_overlap(query: str, candidate: str) -> int:
    """
    두 주소 문자열의 3글자 묶음 겹침 수. 한국 주소는 띄어쓰기/법정동·도로명 표기가
    제각각이라 토큰 분리보다 n-gram 겹침이 안정적이다.
    """
    if len(query) < 3 or len(candidate) < 3:
        return 0
    grams = {query[i : i + 3] for i in range(len(query) - 2)}
    return sum(1 for i in range(len(candidate) - 2) if candidate[i : i + 3] in grams)


def _confidence_label(confidence: Optional[str]) -> str:
    return {"high": "높음", "medium": "보통", "low": "낮음"}.get(confidence or "", "미상")
