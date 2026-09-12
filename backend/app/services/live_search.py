"""
라이브 공실 검색 — 요청이 들어온 순간에 두 API를 직접 호출해 후보를 만든다.

기존 방식은 scripts/fetch_real_vacancies.py가 미리 수집해 둔 app/data/real/*.json을
서버 시작 시 한 번 읽는 것이었다. 그래서 검색 조건과 무관하게 항상 같은 표본(전북
전역에서 뽑힌 수십 건)만 후보가 됐고, 희망 지역을 바꿔도 목록이 거의 그대로였다.

여기서는 희망 지역 -> 대표 좌표 -> 반경 조회 순으로 매 요청마다 새로 훑는다.

## 호출 비용과 TTL 캐시

  상가정보 storeListInRadius   반경 1회당 2~5콜 (1000건/페이지) — 싸다
  건축물대장 표제부+층별개요    건물당 2콜 — 비싸다

건물 60개를 순차로 보면 26초쯤 걸려서(실측 100건 88초) 요청 안에서 돌릴 수 없다.
그래서 대장 조회는 스레드풀로 병렬화하고(REGISTER_WORKERS), 같은 (좌표, 반경)
검색 결과는 CACHE_TTL_SECONDS 동안 메모리에 들고 있는다. 공공데이터포털 개발계정은
일일 호출 한도가 있어, 캐시가 없으면 데모 중에 소진된다.

캐시 미스일 때만 실제 호출이 나가므로 첫 검색은 수 초, 이후 같은 지역 검색은 즉시다.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from app.services import (
    building_register_api,
    datagokr,
    register_cache,
    sangga_api,
    vacancy_estimator,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CENTERS_PATH = DATA_DIR / "region_stats.json"

# 검색 1회의 기본 반경. 수집 스크립트의 --radius 기본값과 맞춘다.
DEFAULT_RADIUS_M = 2000
# 반경 조회 최대 페이지 (1페이지 1000건). 도심 2km면 3~5천 건 수준이다.
MAX_STORE_PAGES = 5
# 대장을 조회할 건물 수 상한. 건물당 2콜이므로 이 값 x2가 검색 1회의 대장 호출 수다.
DEFAULT_MAX_BUILDINGS = 60
# 대장 조회 동시 실행 수. 실제 속도는 register_cache.limiter(호출 간 0.2초)가
# 정하므로, 워커는 캐시 적중분을 빠르게 흘려보내는 역할이 크다. 동시 8콜을 그냥
# 던지면 개발계정이 429를 뱉고 백오프가 겹쳐 오히려 느려진다(실측 68초).
REGISTER_WORKERS = 4

CACHE_TTL_SECONDS = 900  # 15분
CACHE_MAX_ENTRIES = 32

BUSINESS_TYPES = ("카페", "학원", "병원", "편의점", "스터디카페")

# region_pref가 비었거나 "상관없음"일 때 쓸 기본 중심. 시범 상권이 전주 원도심이다.
DEFAULT_CENTER_ID = "jeonju"
ANY_REGION = "상관없음"


@dataclass
class VacancySet:
    """
    한 번의 검색이 만들어 낸 공실 매물 집합.

    buildings/market은 캐시 JSON(app/data/real/*.json)과 같은 스키마다. 라우터와
    스코어링이 캐시 기반 provider와 라이브 검색을 구분하지 않고 쓰게 하기 위함이다.
    """

    buildings: dict[str, dict[str, Any]]
    market: dict[str, dict[str, dict[str, Any]]]
    meta: dict[str, Any] = field(default_factory=dict)
    live: bool = False

    def __len__(self) -> int:
        return len(self.buildings)


# --- 검색 중심 ------------------------------------------------------------------


_centers_cache: Optional[list[dict[str, Any]]] = None


def load_centers() -> list[dict[str, Any]]:
    """
    검색 중심 후보. region_stats.json의 시·군/상권 대표 좌표를 그대로 쓴다
    (수집 스크립트의 load_centers와 같은 출처 — 두 경로가 같은 지점을 본다).
    """
    global _centers_cache
    if _centers_cache is None:
        data = json.loads(CENTERS_PATH.read_text(encoding="utf-8"))
        _centers_cache = [
            {
                "id": item["id"],
                "region_name": item["region_name"],
                "lat": item["lat"],
                "lng": item["lng"],
                "scope": item.get("scope", "district"),
            }
            for item in data["regions"]
            if item.get("lat") is not None and item.get("lng") is not None
        ]
    return _centers_cache


def region_options() -> list[str]:
    """
    매칭 입력 화면의 '희망 지역' 선택지.

    캐시 방식에서는 수집된 매물의 법정동명("모현동1가" 등)을 역산해 보여 줬다.
    라이브 검색에서는 반대로, 중심 좌표가 있는 지역만 실제로 검색할 수 있으므로
    중심 목록이 그대로 선택지가 된다. 좁은 상권(neighborhood)을 먼저 보여 준다.
    """
    centers = load_centers()
    neighborhoods = [c["region_name"] for c in centers if c.get("scope") == "neighborhood"]
    districts = [c["region_name"] for c in centers if c.get("scope") != "neighborhood"]
    return [ANY_REGION] + neighborhoods + districts


def resolve_center(region_pref: Optional[str]) -> dict[str, Any]:
    """
    희망 지역명을 검색 중심 좌표로 바꾼다.

    지역명 표기가 화면/프리셋마다 제각각이라("전주", "전주시", "전주역") 완전 일치 ->
    부분 일치 순으로 찾고, 그래도 없으면 기본 중심으로 떨어진다. 매칭 실패로 검색이
    0건이 되는 것보다 기본 상권이라도 보여 주는 편이 낫다.
    """
    centers = load_centers()
    by_id = {c["id"]: c for c in centers}
    query = (region_pref or "").strip()

    if query and query != ANY_REGION:
        for center in centers:
            if center["region_name"] == query:
                return center
        for center in centers:
            name = center["region_name"]
            if query in name or name in query:
                return center
        logger.info("희망 지역 '%s'에 대응하는 검색 중심이 없어 기본 중심을 씁니다.", query)

    return by_id.get(DEFAULT_CENTER_ID) or centers[0]


# --- 가용성 ---------------------------------------------------------------------


def is_available() -> bool:
    """두 API의 서비스키가 모두 있는지. 하나라도 없으면 라이브 검색을 켤 수 없다."""
    return datagokr.has_service_key(sangga_api.KEY_ENV) and datagokr.has_service_key(
        building_register_api.KEY_ENV
    )


# --- 검색 -----------------------------------------------------------------------


def _collect_stores(center: dict[str, Any], radius_m: int) -> list[dict[str, Any]]:
    """중심 반경의 영업 점포. 쿼터 초과로 끊겨도 모은 만큼으로 진행한다."""
    stores: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        for raw in sangga_api.store_list_in_radius(
            center["lng"], center["lat"], radius_m, max_pages=MAX_STORE_PAGES
        ):
            store = sangga_api.normalize_store(raw)
            store_id = store.get("store_id")
            if store_id and store_id in seen:
                continue
            if store_id:
                seen.add(store_id)
            stores.append(store)
    except datagokr.DataGoKrError as exc:
        if not stores:
            raise
        logger.warning("상가정보 조회가 중단되어 %d건으로 진행합니다: %s", len(stores), exc)
    return stores


def _fetch_register(building: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    건물 1개의 대장(표제부+층별개요). 디스크 캐시를 먼저 보고, 없을 때만 호출한다
    (register_cache 참고 — 대장 값은 준공 이후 거의 바뀌지 않는다).
    실패는 None으로 삼키고 그 건물만 건너뛴다.
    """
    try:
        return register_cache.get_or_fetch(
            building["register_params"], building_register_api.fetch_building
        )
    except Exception as exc:  # 미등재 지번/쿼터/타임아웃 — 검색 전체를 죽이지 않는다.
        logger.debug("건축물대장 조회 실패 %s: %s", building.get("key"), exc)
        return None


def _build_market(
    index: vacancy_estimator.StoreIndex, candidates: Iterable[dict[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    candidates = list(candidates)
    references = vacancy_estimator.saturation_references(index, candidates, BUSINESS_TYPES)
    return {
        candidate["id"]: {
            business_type: vacancy_estimator.build_market_entry(
                index,
                candidate.get("lat"),
                candidate.get("lng"),
                business_type,
                candidate.get("signgu_name", ""),
                candidate.get("area_pyeong", 0) or 0,
                candidate.get("floor", 1),
                saturation_reference=references.get(business_type),
            )
            for business_type in BUSINESS_TYPES
        }
        for candidate in candidates
    }


def _run_search(
    center: dict[str, Any], radius_m: int, max_buildings: int, today: Optional[date]
) -> VacancySet:
    started = time.monotonic()

    stores = _collect_stores(center, radius_m)
    index = vacancy_estimator.StoreIndex(stores)
    grouped = sangga_api.group_by_building(stores)

    usable = [
        b
        for b in grouped.values()
        if b.get("register_params") and b.get("lat") is not None and b.get("lng") is not None
    ]
    usable.sort(key=vacancy_estimator.candidate_priority)
    selected = usable[:max_buildings]

    # 대장 조회가 검색 시간의 대부분이다. 순차로는 건물 60개에 26초쯤 걸려
    # 요청 안에서 돌릴 수 없으므로 병렬로 던진다.
    cached_before = sum(1 for b in selected if register_cache.get(b["register_params"])[0])
    if selected:
        with ThreadPoolExecutor(max_workers=REGISTER_WORKERS) as pool:
            registers = list(pool.map(_fetch_register, selected))
    else:
        registers = []

    candidates: list[dict[str, Any]] = []
    for building, register in zip(selected, registers):
        if register is None:
            continue
        candidates.extend(
            vacancy_estimator.candidates_for_building(building, register, today=today)
        )

    elapsed = time.monotonic() - started
    logger.info(
        "라이브 검색 %s(%.4f,%.4f) r=%dm — 점포 %d / 건물 %d(대장 %d, 캐시적중 %d) "
        "/ 공실 후보 %d / %.1f초",
        center.get("region_name"),
        center["lat"],
        center["lng"],
        radius_m,
        len(stores),
        len(usable),
        len(selected),
        cached_before,
        len(candidates),
        elapsed,
    )

    return VacancySet(
        buildings={candidate["id"]: candidate for candidate in candidates},
        market=_build_market(index, candidates),
        live=True,
        meta={
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "data_reference_month": (today or date.today()).strftime("%Y-%m"),
            "collection_mode": "live",
            "center": center,
            "radius_m": radius_m,
            "store_count": len(stores),
            "building_count": len(usable),
            "buildings_queried": len(selected),
            "register_cache_hits": cached_before,
            "register_found": sum(1 for r in registers if r is not None),
            "vacancy_candidates": len(candidates),
            "elapsed_seconds": round(elapsed, 1),
            "business_types": list(BUSINESS_TYPES),
            "sources": {
                "stores": "소상공인시장진흥공단_상가(상권)정보 API",
                "register": "국토교통부_건축HUB_건축물대장정보 서비스",
            },
        },
    )


# --- TTL 캐시 -------------------------------------------------------------------

# key -> (만료 시각, 결과). 검색 1회가 대장 호출 100여 회라 재검색을 그대로 흘려보내면
# 개발계정 일일 한도가 데모 중에 마른다.
_cache: dict[tuple, tuple[float, VacancySet]] = {}
_cache_lock = threading.Lock()
# key별 실행 락. 같은 지역 요청이 동시에 들어와도 API 호출은 한 번만 나가게 한다.
_search_locks: dict[tuple, threading.Lock] = {}


def _cache_key(center: dict[str, Any], radius_m: int, max_buildings: int) -> tuple:
    return (round(center["lat"], 4), round(center["lng"], 4), radius_m, max_buildings)


def _cache_get(key: tuple) -> Optional[VacancySet]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, result = entry
        if expires_at < time.monotonic():
            _cache.pop(key, None)
            return None
        return result


def _cache_put(key: tuple, result: VacancySet) -> None:
    with _cache_lock:
        if len(_cache) >= CACHE_MAX_ENTRIES:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            _cache.pop(oldest, None)
        _cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, result)


def _lock_for(key: tuple) -> threading.Lock:
    with _cache_lock:
        return _search_locks.setdefault(key, threading.Lock())


def clear_cache() -> None:
    """테스트/운영 편의 — 다음 검색이 반드시 실제 호출을 내게 한다."""
    with _cache_lock:
        _cache.clear()


def search(
    region_pref: Optional[str] = None,
    *,
    radius_m: int = DEFAULT_RADIUS_M,
    max_buildings: int = DEFAULT_MAX_BUILDINGS,
    today: Optional[date] = None,
    force: bool = False,
) -> VacancySet:
    """
    희망 지역 기준으로 공실 매물을 라이브 검색한다.

    Args:
        region_pref: 화면에서 고른 희망 지역명. None/"상관없음"이면 기본 중심.
        radius_m: 중심 반경(m).
        max_buildings: 대장을 조회할 건물 수 상한 (호출 수 = 이 값 x 2).
        force: True면 TTL 캐시를 무시하고 다시 호출한다.

    Raises:
        datagokr.DataGoKrError: 상가정보 조회가 한 건도 성공하지 못한 경우.
            호출부(LiveSanggaProvider)가 잡아서 디스크 캐시로 폴백한다.
    """
    center = resolve_center(region_pref)
    key = _cache_key(center, radius_m, max_buildings)

    if not force:
        cached = _cache_get(key)
        if cached is not None:
            logger.debug("라이브 검색 캐시 적중 %s", key)
            return cached

    # 같은 지역 동시 요청이 각자 API를 때리지 않도록 key 단위로 직렬화한다.
    with _lock_for(key):
        if not force:
            cached = _cache_get(key)
            if cached is not None:
                return cached
        result = _run_search(center, radius_m, max_buildings, today)
        _cache_put(key, result)
        return result
