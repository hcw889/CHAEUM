"""
LiveSanggaProvider — 매칭 요청이 들어올 때마다 두 API를 직접 호출해 공실을 찾는다.

RealSanggaProvider(디스크 캐시)를 상속하고 search_vacancies()만 라이브로 바꾼다.
나머지 메서드(get_building / get_market_data / get_data_sources / get_permits)는
그대로 물려받는데, 그러려면 라이브 검색 결과가 그 조회들에서도 보여야 한다.
그래서 검색이 끝날 때마다 결과를 _remember()로 인메모리 인덱스에 합친다.

  1) /api/match          -> search_vacancies()로 라이브 검색 + 결과를 인덱스에 등록
  2) /api/buildings/{id} -> 방금 등록된 매물을 get_building()이 그대로 찾는다
     /api/buildings/{id}/dashboard, /api/report/... 도 같은 경로다

라이브 검색이 실패하면(키 만료, 쿼터 초과, 포털 점검) 디스크 캐시로 조용히
내려간다 — 데모 도중 결과가 0건이 되는 것보다 낫다. 어느 쪽이 쓰였는지는
VacancySet.live와 meta에 남고, /api/match/options가 화면에 그대로 내려 준다.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

from app.services import live_search
from app.services.data_provider import DATA_DIR
from app.services.live_search import VacancySet
from app.services.real_data_provider import REAL_DIR, RealSanggaProvider

logger = logging.getLogger(__name__)

# 인메모리 인덱스 상한. 여러 지역을 검색하면 계속 쌓이므로 오래된 것부터 버린다.
# 검색 1회가 수십 건이라 2,000이면 30회 남짓의 검색 이력을 들고 있는 셈이다.
REMEMBER_LIMIT = 2000

LIVE_SOURCE_NOTE = (
    "검색하신 지역을 기준으로 소상공인시장진흥공단 상가(상권)정보 API와 "
    "국토교통부 건축HUB 건축물대장정보 API를 지금 조회한 결과입니다. "
    "두 API 모두 공실 여부를 직접 제공하지 않아, 건축물대장상 근린생활시설·판매시설 "
    "층 중 등록 점포가 0건인 층을 공실로 추정했습니다."
)


class LiveSanggaProvider(RealSanggaProvider):
    def __init__(
        self,
        real_dir: Path = REAL_DIR,
        data_dir: Path = DATA_DIR,
        *,
        radius_m: int = live_search.DEFAULT_RADIUS_M,
        max_buildings: int = live_search.DEFAULT_MAX_BUILDINGS,
    ):
        super().__init__(real_dir=real_dir, data_dir=data_dir)
        self._radius_m = radius_m
        self._max_buildings = max_buildings
        # _buildings/_market_data는 요청 스레드에서 갱신되므로 잠근다.
        self._lock = threading.Lock()
        self._last_meta: dict[str, Any] = {}
        # 상속받은 디스크 캐시는 폴백 전용으로 따로 들고 있는다.
        self._disk_buildings = dict(self._buildings)
        self._disk_market = dict(self._market_data)

        logger.info(
            "LiveSanggaProvider: 요청 시점 라이브 검색 (반경 %dm / 건물 %d개 / 캐시 %d분)",
            radius_m,
            max_buildings,
            live_search.CACHE_TTL_SECONDS // 60,
        )

    # --- 라이브 검색 -----------------------------------------------------------

    def search_vacancies(self, region_pref: str = live_search.ANY_REGION) -> VacancySet:
        try:
            result = live_search.search(
                region_pref, radius_m=self._radius_m, max_buildings=self._max_buildings
            )
        except Exception as exc:  # 쿼터/네트워크/포털 점검 — 디스크 캐시로 내려간다.
            logger.warning("라이브 검색 실패, 디스크 캐시로 폴백합니다 (%s): %s", region_pref, exc)
            return self._disk_fallback(region_pref, reason=str(exc))

        if not result.buildings:
            # 좁은 상권이라 후보가 안 나오는 경우다. 빈 화면보다 캐시가 낫다.
            logger.info("라이브 검색 결과 0건 (%s) — 디스크 캐시로 폴백합니다.", region_pref)
            return self._disk_fallback(region_pref, reason="라이브 검색 결과 0건")

        self._remember(result)
        return result

    def _disk_fallback(self, region_pref: str, *, reason: str) -> VacancySet:
        fallback = VacancySet(
            buildings=dict(self._disk_buildings),
            market=dict(self._disk_market),
            meta={**self._meta, "collection_mode": "cache", "fallback_reason": reason},
            live=False,
        )
        with self._lock:
            self._last_meta = fallback.meta
        return fallback

    def _remember(self, result: VacancySet) -> None:
        """
        검색 결과를 조회용 인덱스에 합친다.

        매칭 응답의 building_id로 프론트가 상세/대시보드/리포트를 다시 부르는데,
        그때는 검색 조건이 없어서 라이브로 다시 찾을 수 없다. 방금 검색에서 나온
        매물을 들고 있어야 그 후속 호출들이 404가 되지 않는다.
        """
        with self._lock:
            self._buildings.update(result.buildings)
            self._market_data.update(result.market)
            self._last_meta = result.meta
            self._trim_locked()

    def _trim_locked(self) -> None:
        """상한을 넘으면 먼저 들어온 것부터 버린다 (디스크 캐시 매물은 남긴다)."""
        overflow = len(self._buildings) - REMEMBER_LIMIT
        if overflow <= 0:
            return
        for building_id in list(self._buildings):
            if overflow <= 0:
                break
            if building_id in self._disk_buildings:
                continue
            self._buildings.pop(building_id, None)
            self._market_data.pop(building_id, None)
            overflow -= 1

    # --- 화면에 내려 줄 메타 ----------------------------------------------------

    @property
    def meta(self) -> dict[str, Any]:
        """마지막 검색의 메타. 아직 검색 전이면 디스크 캐시의 수집 정보."""
        return self._last_meta or self._meta

    def region_options(self) -> list[str]:
        """
        라이브 검색은 중심 좌표가 있는 지역만 조회할 수 있으므로, 수집된 매물에서
        역산하던 캐시 방식과 달리 검색 중심 목록이 그대로 선택지가 된다.
        """
        return live_search.region_options()

    @property
    def source_note(self) -> str:
        return LIVE_SOURCE_NOTE


def is_enabled() -> bool:
    """
    라이브 검색을 쓸 수 있는지. 두 API 서비스키가 모두 있어야 한다.
    CHAEUM_LIVE_SEARCH=0 으로 끄면 기존 디스크 캐시 방식으로 돌아간다.
    """
    if os.environ.get("CHAEUM_LIVE_SEARCH", "1") == "0":
        return False
    return live_search.is_available()
