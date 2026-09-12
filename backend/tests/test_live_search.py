"""
라이브 공실 검색 검증 — 요청 시점에 두 API를 부르는 경로.

네트워크를 타지 않는다. sangga_api.store_list_in_radius와
building_register_api.fetch_building을 가짜로 바꿔 놓고, 검색 범위 결정 ->
반경 조회 -> 건물 그룹핑 -> 대장 조인 -> 공실 후보 -> 시장 신호까지 이어지는지 본다.

여기서 검증하고 싶은 것은 "지역을 바꾸면 후보가 실제로 바뀌는가"다. 캐시 방식은
검색 조건과 무관하게 항상 같은 표본을 돌려줬고, 그래서 추천 결과가 지역과 무관하게
산발적으로 보였다.
"""

from __future__ import annotations

import pytest

from app.services import building_register_api, live_search, register_cache, sangga_api
from app.services.live_data_provider import LiveSanggaProvider

# --- 가짜 API 응답 ---------------------------------------------------------------

# 두 상권. 좌표가 멀어서 반경 2km로는 서로 섞이지 않는다.
GAEKSA = (127.143, 35.818)
GUNSAN = (126.7369, 35.9676)


def _store(bizes_id, name, lng, lat, floor, *, bld="0001", signgu="52111", dong="11700"):
    """상가정보 storeListInRadius 응답 1건 형태."""
    return {
        "bizesId": bizes_id,
        "bizesNm": name,
        "indsLclsNm": "음식",
        "indsMclsNm": "비알콜 음료점업",
        "indsSclsNm": "커피전문점/카페/다방",
        "ctprvnCd": "52",
        "signguCd": signgu,
        "signguNm": "전주시완산구" if signgu == "52111" else "군산시",
        "adongNm": "중앙동",
        "ldongCd": signgu + dong[:2] + "0100",
        "ldongNm": "고사동" if signgu == "52111" else "동충동",
        "plotSctCd": "1",
        "lnoMnno": int(bld),
        "lnoSlno": 0,
        "bldMngNo": signgu + dong + "10" + bld.zfill(6),
        "bldNm": "테스트빌딩" + bld,
        "rdnmAdr": "전북특별자치도 어딘가 {}".format(bld),
        "flrNo": floor,
        "hoNo": "101",
        "lon": lng,
        "lat": lat,
    }


def _register(approval="20100301", floors=None):
    """건축물대장 표제부+층별개요 파싱 결과 형태 (fetch_building의 반환값)."""
    return {
        "title": {
            "approval_year": int(approval[:4]),
            "structure": "철근콘크리트구조",
            "elevators": 1,
            "ground_floors": 4,
            "underground_floors": 1,
            "total_area": 1200.0,
            "main_purpose": "제2종근린생활시설",
            "mgm_bldrgst_pk": "pk-test",
        },
        "floors": floors
        if floors is not None
        else [
            {
                "floor": 1,
                "floor_label": "1층",
                "purpose": "제2종근린생활시설(일반음식점)",
                "area": 120.0,
                "is_commercial": True,
                "is_non_leasable": False,
            },
            {
                "floor": 3,
                "floor_label": "3층",
                "purpose": "제2종근린생활시설(사무소)",
                "area": 100.0,
                "is_commercial": True,
                "is_non_leasable": False,
            },
        ],
        "register_params": {},
    }


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """TTL 캐시와 대장 디스크 캐시를 테스트마다 비운다."""
    live_search.clear_cache()
    monkeypatch.setattr(register_cache, "_conn", None)
    monkeypatch.setattr(register_cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(register_cache, "CACHE_PATH", tmp_path / "register.sqlite3")
    monkeypatch.setattr(register_cache, "limiter", register_cache.RateLimiter(0))
    yield
    live_search.clear_cache()
    register_cache._conn = None


@pytest.fixture
def fake_apis(monkeypatch):
    """중심 좌표에 따라 다른 점포를 돌려주는 가짜 반경 조회 + 가짜 대장."""
    calls = {"radius": [], "register": 0}

    def store_list_in_radius(lng, lat, radius_m, **kwargs):
        calls["radius"].append((lng, lat, radius_m))
        if abs(lng - GUNSAN[0]) < 0.05:
            # 군산: 건물 1개, 1층에만 점포 -> 3층이 공실 후보
            return iter(
                [
                    _store("G1", "군산카페", GUNSAN[0], GUNSAN[1], 1, bld="7", signgu="52130"),
                    _store("G2", "군산분식", GUNSAN[0], GUNSAN[1], 1, bld="7", signgu="52130"),
                ]
            )
        # 전주: 건물 2개
        return iter(
            [
                _store("J1", "전주카페", GAEKSA[0], GAEKSA[1], 1, bld="1"),
                _store("J2", "전주서점", GAEKSA[0], GAEKSA[1], 1, bld="1"),
                _store("J3", "전주분식", GAEKSA[0], GAEKSA[1], 3, bld="2"),
                _store("J4", "전주약국", GAEKSA[0], GAEKSA[1], 3, bld="2"),
            ]
        )

    def fetch_building(params):
        calls["register"] += 1
        return _register()

    monkeypatch.setattr(sangga_api, "store_list_in_radius", store_list_in_radius)
    monkeypatch.setattr(building_register_api, "fetch_building", fetch_building)
    return calls


# --- 검색 범위 -------------------------------------------------------------------


def test_region_pref_resolves_to_its_own_center():
    assert live_search.resolve_center("객사길")["id"] == "gaeksa"
    assert live_search.resolve_center("군산시")["id"] == "gunsan"
    # 표기가 달라도 부분 일치로 찾는다.
    assert live_search.resolve_center("전주")["id"] == "jeonju"


def test_unknown_or_any_region_falls_back_to_default_center():
    """검색 중심을 못 찾아도 0건이 되는 대신 기본 상권을 본다."""
    assert live_search.resolve_center("상관없음")["id"] == live_search.DEFAULT_CENTER_ID
    assert live_search.resolve_center("없는동네")["id"] == live_search.DEFAULT_CENTER_ID
    assert live_search.resolve_center(None)["id"] == live_search.DEFAULT_CENTER_ID


def test_region_options_only_lists_searchable_centers():
    options = live_search.region_options()
    assert options[0] == live_search.ANY_REGION
    assert "객사길" in options and "군산시" in options
    # 모든 선택지가 실제 중심으로 해석되어야 한다 — 아니면 결과가 엉뚱한 지역으로 간다.
    for option in options[1:]:
        assert live_search.resolve_center(option)["region_name"] == option


# --- 검색 ------------------------------------------------------------------------


def test_search_queries_the_requested_region_center(fake_apis):
    live_search.search("군산시")
    lng, lat, radius = fake_apis["radius"][0]
    assert (round(lng, 4), round(lat, 4)) == GUNSAN
    assert radius == live_search.DEFAULT_RADIUS_M


def test_different_regions_yield_different_candidates(fake_apis):
    """캐시 방식이 못 하던 것 — 지역을 바꾸면 후보 집합이 실제로 바뀐다."""
    jeonju = live_search.search("객사길")
    gunsan = live_search.search("군산시")

    assert jeonju.buildings and gunsan.buildings
    assert set(jeonju.buildings) != set(gunsan.buildings)
    assert {b["signgu_name"] for b in jeonju.buildings.values()} == {"전주시완산구"}
    assert {b["signgu_name"] for b in gunsan.buildings.values()} == {"군산시"}


def test_candidates_carry_vacancy_basis_and_market_signals(fake_apis):
    result = live_search.search("객사길")

    assert result.live is True
    for building_id, building in result.buildings.items():
        assert building["vacancy"]["estimated"] is True
        assert building["vacancy"]["confidence"] in ("high", "medium", "low")
        assert building["vacancy"]["basis"]
        entry = result.market[building_id]["카페"]
        assert set(entry) >= {
            "foot_traffic_index",
            "competition_saturation_index",
            "demographic_fit_index",
            "estimated_rent",
        }


def test_occupied_floors_are_not_reported_vacant(fake_apis):
    """1층에 점포가 있는 건물은 1층이 후보가 되면 안 된다 (3층만 공실)."""
    result = live_search.search("객사길")
    floors_by_building = {}
    for building in result.buildings.values():
        floors_by_building.setdefault(building["register"]["bld_mng_no"], set()).add(
            building["floor"]
        )
    # J1/J2가 1층에 있는 건물은 3층만, J3/J4가 3층에 있는 건물은 1층만 남는다.
    assert sorted(sorted(f) for f in floors_by_building.values()) == [[1], [3]]


# --- 캐시 -------------------------------------------------------------------------


def test_repeat_search_hits_ttl_cache_without_new_api_calls(fake_apis):
    live_search.search("객사길")
    radius_calls = len(fake_apis["radius"])
    register_calls = fake_apis["register"]

    live_search.search("객사길")

    assert len(fake_apis["radius"]) == radius_calls
    assert fake_apis["register"] == register_calls


def test_register_disk_cache_survives_ttl_expiry(fake_apis):
    """
    TTL 캐시가 만료돼도 대장은 다시 부르지 않는다. 상가정보(공실 신호)만 새로
    받으면 되고, 대장 값은 준공 이후 거의 바뀌지 않기 때문이다.
    """
    live_search.search("객사길")
    register_calls = fake_apis["register"]
    assert register_calls > 0

    live_search.clear_cache()
    result = live_search.search("객사길")

    assert fake_apis["register"] == register_calls  # 대장은 추가 호출 없음
    assert len(fake_apis["radius"]) == 2  # 상가정보는 다시 조회
    assert result.meta["register_cache_hits"] == result.meta["buildings_queried"]


# --- provider 폴백 -----------------------------------------------------------------


def test_provider_falls_back_to_disk_cache_when_live_search_fails(monkeypatch):
    """쿼터 초과/포털 점검으로 라이브가 죽어도 화면이 비지 않는다."""

    def boom(*args, **kwargs):
        raise RuntimeError("429 Too Many Requests")

    monkeypatch.setattr(live_search, "search", boom)
    provider = LiveSanggaProvider()

    result = provider.search_vacancies("객사길")

    assert result.live is False
    assert "429" in result.meta["fallback_reason"]


def test_provider_remembers_results_for_follow_up_lookups(fake_apis):
    """
    매칭 응답의 building_id로 프론트가 상세/대시보드를 다시 부른다. 그때는 검색
    조건이 없으므로, 방금 검색한 매물이 조회로도 잡혀야 404가 안 난다.
    """
    provider = LiveSanggaProvider()
    result = provider.search_vacancies("객사길")

    assert result.live is True
    for building_id in result.buildings:
        assert provider.get_building(building_id) is not None
        assert provider.get_market_data(building_id)
        assert provider.get_data_sources(building_id)
