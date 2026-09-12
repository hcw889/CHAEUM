"""
상가정보 API + 건축물대장 API 조인 기반 공실 추정 로직 검증.

네트워크를 타지 않는다. 두 API의 실제 응답 형태를 그대로 흉내 낸 고정 payload를
파서에 넣어, 조인 키 생성 -> 층별 공실 판정 -> 매물 레코드 -> 시장 신호까지
한 줄로 통과하는지 본다. 응답 필드명이 바뀌면 여기서 먼저 깨진다.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.services import building_register_api, datagokr, sangga_api, vacancy_estimator
from app.services.real_data_provider import RealSanggaProvider

# --- 고정 payload (실제 응답 형태) -------------------------------------------

# 상가정보 storeListInAdmi 응답 1건. 전주 고사동 한 건물의 1층/2층 점포.
SANGGA_RAW = [
    {
        "bizesId": "MA0101202012A0000001",
        "bizesNm": "온잇커피",
        "brchNm": "",
        "indsLclsCd": "Q",
        "indsLclsNm": "음식",
        "indsMclsCd": "Q12",
        "indsMclsNm": "비알콜 음료점업",
        "indsSclsCd": "Q12A01",
        "indsSclsNm": "커피전문점/카페/다방",
        "ctprvnCd": "52",
        "ctprvnNm": "전북특별자치도",
        "signguCd": "52111",
        "signguNm": "전주시완산구",
        "adongCd": "5211156000",
        "adongNm": "중앙동",
        "ldongCd": "5211110100",
        "ldongNm": "고사동",
        "plotSctCd": "1",
        "lnbrMnnm": "123",
        "lnbrSlno": "4",
        "bldMngNo": "5211110100101230004000001",
        "bldNm": "온잇빌딩",
        "rdnmAdr": "전북특별자치도 전주시 완산구 충경로 12",
        "flrNo": "1",
        "hoNo": "101",
        "lon": "127.140123",
        "lat": "35.818456",
    },
    {
        "bizesId": "MA0101202012A0000002",
        "bizesNm": "온잇미용실",
        "indsLclsNm": "수리·개인",
        "indsMclsNm": "이용·미용",
        "indsSclsNm": "미용실",
        "signguCd": "52111",
        "signguNm": "전주시완산구",
        "adongNm": "중앙동",
        "ldongCd": "5211110100",
        "ldongNm": "고사동",
        "plotSctCd": "1",
        "lnbrMnnm": "123",
        "lnbrSlno": "4",
        "bldMngNo": "5211110100101230004000001",
        "bldNm": "온잇빌딩",
        "rdnmAdr": "전북특별자치도 전주시 완산구 충경로 12",
        "flrNo": "2",
        "hoNo": "201",
        "lon": "127.140130",
        "lat": "35.818460",
    },
    {
        "bizesId": "MA0101202012A0000003",
        "bizesNm": "충경로분식",
        "indsLclsNm": "음식",
        "indsMclsNm": "기타 간이 음식점업",
        "indsSclsNm": "분식전문점",
        "signguCd": "52111",
        "signguNm": "전주시완산구",
        "adongNm": "중앙동",
        "ldongCd": "5211110100",
        "ldongNm": "고사동",
        "plotSctCd": "1",
        "lnbrMnnm": "123",
        "lnbrSlno": "4",
        "bldMngNo": "5211110100101230004000001",
        "bldNm": "온잇빌딩",
        "rdnmAdr": "전북특별자치도 전주시 완산구 충경로 12",
        "flrNo": "B1",
        "hoNo": "B01",
        "lon": "127.140118",
        "lat": "35.818450",
    },
]

# 건축물대장 getBrTitleInfo 응답 봉투. 지상 4층 / 지하 1층.
TITLE_PAYLOAD = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
        "body": {
            "items": {
                "item": {
                    "mgmBldrgstPk": "52111-100123456",
                    "bldNm": "온잇빌딩",
                    "platPlc": "전북특별자치도 전주시 완산구 고사동 123-4",
                    "newPlatPlc": "전북특별자치도 전주시 완산구 충경로 12",
                    "useAprDay": "19950320",
                    "totArea": "820.5",
                    "archArea": "210.3",
                    "grndFlrCnt": "4",
                    "ugrndFlrCnt": "1",
                    "heit": "15.2",
                    "strctCdNm": "철근콘크리트구조",
                    "mainPurpsCdNm": "제2종근린생활시설",
                    "etcPurps": "소매점, 일반음식점",
                    "rideUseElvtCnt": "1",
                    "emgenUseElvtCnt": "0",
                }
            },
            "numOfRows": 50,
            "pageNo": 1,
            "totalCount": 1,
        },
    }
}

# getBrFlrOulnInfo 응답. 지하1~4층. 3층과 4층은 상업용도인데 점포가 없다 -> 공실 후보.
FLOOR_PAYLOAD = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
        "body": {
            "items": {
                "item": [
                    {
                        "flrGbCdNm": "지하",
                        "flrNo": "1",
                        "flrNoNm": "지하1층",
                        "mainPurpsCdNm": "제2종근린생활시설",
                        "etcPurps": "일반음식점",
                        "area": "180.2",
                        "strctCdNm": "철근콘크리트구조",
                    },
                    {
                        "flrGbCdNm": "지상",
                        "flrNo": "1",
                        "flrNoNm": "1층",
                        "mainPurpsCdNm": "제1종근린생활시설",
                        "etcPurps": "소매점",
                        "area": "195.4",
                        "strctCdNm": "철근콘크리트구조",
                    },
                    {
                        "flrGbCdNm": "지상",
                        "flrNo": "2",
                        "flrNoNm": "2층",
                        "mainPurpsCdNm": "제2종근린생활시설",
                        "etcPurps": "미용원",
                        "area": "190.0",
                        "strctCdNm": "철근콘크리트구조",
                    },
                    {
                        "flrGbCdNm": "지상",
                        "flrNo": "3",
                        "flrNoNm": "3층",
                        "mainPurpsCdNm": "제2종근린생활시설",
                        "etcPurps": "사무소",
                        "area": "188.6",
                        "strctCdNm": "철근콘크리트구조",
                    },
                    {
                        "flrGbCdNm": "지상",
                        "flrNo": "4",
                        "flrNoNm": "4층",
                        "mainPurpsCdNm": "단독주택",
                        "etcPurps": "주인세대",
                        "area": "120.0",
                        "strctCdNm": "철근콘크리트구조",
                    },
                ]
            },
            "totalCount": 5,
        },
    }
}


@pytest.fixture
def stores():
    return [sangga_api.normalize_store(raw) for raw in SANGGA_RAW]


@pytest.fixture
def building(stores):
    grouped = sangga_api.group_by_building(stores)
    assert len(grouped) == 1, "같은 건물관리번호는 하나로 묶여야 한다"
    return next(iter(grouped.values()))


@pytest.fixture
def register():
    title = building_register_api.parse_title(
        datagokr.extract_items(TITLE_PAYLOAD)[0]
    )
    floors = building_register_api.parse_floors(datagokr.extract_items(FLOOR_PAYLOAD))
    return {"title": title, "floors": floors, "register_params": {"sigunguCd": "52111"}}


# --- 봉투 파싱 ----------------------------------------------------------------


def test_extract_items_handles_both_envelopes():
    """상가정보(body.items 리스트)와 건축물대장(response.body.items.item) 둘 다."""
    assert len(datagokr.extract_items({"body": {"items": SANGGA_RAW}})) == 3
    assert len(datagokr.extract_items(FLOOR_PAYLOAD)) == 5
    # 단건은 dict로 내려온다
    assert len(datagokr.extract_items(TITLE_PAYLOAD)) == 1
    # 0건일 때 items가 빈 문자열
    assert datagokr.extract_items({"response": {"body": {"items": ""}}}) == []


def test_check_header_rejects_error_code():
    bad = {"response": {"header": {"resultCode": "30", "resultMsg": "SERVICE KEY IS NOT REGISTERED"}}}
    with pytest.raises(datagokr.DataGoKrError):
        datagokr.check_header(bad)
    datagokr.check_header(TITLE_PAYLOAD)  # 정상이면 조용히 통과


# --- 조인 키 ------------------------------------------------------------------


def test_building_register_params_from_store(stores):
    """상가정보의 법정동코드/지번이 건축물대장 파라미터로 정확히 쪼개진다."""
    params = sangga_api.building_register_params(stores[0])
    assert params == {
        "sigunguCd": "52111",
        "bjdongCd": "10100",
        "platGbCd": "0",
        "bun": "0123",
        "ji": "0004",
    }


def test_floor_parsing_handles_basement(stores):
    assert [store["floor"] for store in stores] == [1, 2, -1]


def test_building_key_prefers_management_number(stores):
    assert sangga_api.building_key(stores[0]) == "mng:5211110100101230004000001"
    # 건물관리번호가 없으면 지번 기반 키로 폴백한다
    without = {**stores[0], "bld_mng_no": ""}
    assert sangga_api.building_key(without) == "jibun:5211110100-0-0123-0004"


def test_group_by_building_indexes_floors(building):
    assert building["bld_name"] == "온잇빌딩"
    assert len(building["stores"]) == 3
    assert sorted(k for k in building["stores_by_floor"] if k is not None) == [-1, 1, 2]


# --- 대장 파싱 ----------------------------------------------------------------


def test_parse_title_reads_real_fields(register):
    title = register["title"]
    assert title["approval_year"] == 1995
    assert title["ground_floors"] == 4
    assert title["underground_floors"] == 1
    assert title["elevators"] == 1
    assert title["structure"] == "철근콘크리트구조"
    assert title["is_commercial"] is True


def test_parse_floors_signs_basement_and_flags_purpose(register):
    floors = {entry["floor"]: entry for entry in register["floors"]}
    assert sorted(floors) == [-1, 1, 2, 3, 4]
    assert floors[-1]["floor_label"] == "지하1층"
    assert floors[1]["is_commercial"] is True
    assert floors[3]["is_commercial"] is True
    # 4층은 단독주택 -> 상가 공실 대상이 아니다
    assert floors[4]["is_non_leasable"] is True


# --- 공실 판정 ----------------------------------------------------------------


def test_vacancy_found_only_on_commercial_floor_without_stores(building, register):
    candidates = vacancy_estimator.candidates_for_building(
        building, register, today=date(2026, 9, 1)
    )
    floors = sorted(candidate["floor"] for candidate in candidates)

    # 지하1층/1층/2층에는 영업 점포가 있고, 4층은 주택이다. 3층만 공실 후보다.
    assert floors == [3], "상업용도인데 등록 점포가 0건인 층만 공실이어야 한다"


def test_vacancy_record_carries_basis_and_confidence(building, register):
    candidate = vacancy_estimator.candidates_for_building(
        building, register, today=date(2026, 9, 1)
    )[0]
    vacancy = candidate["vacancy"]

    assert vacancy["estimated"] is True
    assert vacancy["method"] == "층별 미등록 추론"
    assert vacancy["floor_store_count"] == 0
    assert vacancy["building_store_count"] == 3
    # 층이 찍힌 점포가 3건이고 층 미상 점포가 없으므로 신뢰도가 가장 높다
    assert vacancy["confidence"] == "high"
    assert any("건축물대장" in line for line in vacancy["basis"])
    assert any("상가정보" in line for line in vacancy["basis"])


def test_unknown_floor_stores_lower_confidence(building, register):
    """층 표기가 없는 점포가 있으면 '이 층만 비었다'는 판정을 덜 믿어야 한다."""
    noisy = dict(building)
    noisy["stores_by_floor"] = {**building["stores_by_floor"], None: [{"name": "층미상가게"}]}
    noisy["stores"] = building["stores"] + [{"name": "층미상가게"}]

    candidate = vacancy_estimator.candidates_for_building(
        noisy, register, today=date(2026, 9, 1)
    )[0]
    assert candidate["vacancy"]["confidence"] == "medium"
    assert any("층 표기가 없는" in line for line in candidate["vacancy"]["basis"])


def test_candidate_record_matches_buildings_schema(building, register):
    """기존 buildings.json을 읽는 라우터/스코어링이 그대로 쓸 수 있어야 한다."""
    candidate = vacancy_estimator.candidates_for_building(
        building, register, today=date(2026, 9, 1)
    )[0]

    for field in (
        "id", "name", "address", "floor", "area_pyeong", "built_year",
        "risk_grade", "region", "thumbnail_color", "diagnosis", "data_reference_month",
    ):
        assert field in candidate, field

    assert candidate["built_year"] == 1995
    assert candidate["region"] == "고사동"
    assert candidate["signgu_name"] == "전주시완산구"
    # 188.6제곱미터 / 3.305785 = 57.05평
    assert candidate["area_pyeong"] == pytest.approx(57.1, abs=0.2)
    assert set(candidate["diagnosis"]) == {"aging_score", "accessibility_score", "lighting_score"}
    assert "3층" in candidate["address"]


def test_candidate_id_is_stable(building, register):
    first = vacancy_estimator.candidates_for_building(building, register)[0]["id"]
    second = vacancy_estimator.candidates_for_building(building, register)[0]["id"]
    assert first == second, "재수집해도 같은 층이면 같은 id여야 한다"


# --- 실데이터 파생 점수 --------------------------------------------------------


def test_aging_score_tracks_approval_year():
    today = date(2026, 9, 1)
    new_building = vacancy_estimator.aging_score(2024, today=today)
    old_building = vacancy_estimator.aging_score(1975, today=today)
    assert new_building > old_building
    assert vacancy_estimator.aging_score(None, today=today) == 50.0  # 승인일 미상은 중립


def test_accessibility_score_prefers_first_floor():
    with_elevator = {"elevators": 1}
    without = {"elevators": 0}
    assert vacancy_estimator.accessibility_score(1, without) > vacancy_estimator.accessibility_score(
        4, without
    )
    assert vacancy_estimator.accessibility_score(4, with_elevator) > vacancy_estimator.accessibility_score(
        4, without
    )


def test_competition_count_is_measured_not_estimated(stores):
    """경쟁포화도는 반경 내 실제 동일업종 점포 수에서 나온다."""
    index = vacancy_estimator.StoreIndex(stores)
    cafes, total = vacancy_estimator.count_competitors(index, 35.8184, 127.1401, "카페")

    assert total == 3, "반경 300m 안의 전체 점포"
    assert cafes == 1, "커피전문점/카페/다방 1건만 카페로 잡혀야 한다"

    hair, _ = vacancy_estimator.count_competitors(index, 35.8184, 127.1401, "병원")
    assert hair == 0


def test_store_index_excludes_far_stores(stores):
    index = vacancy_estimator.StoreIndex(stores)
    # 약 10km 떨어진 지점에서는 하나도 안 잡혀야 한다
    _, total = vacancy_estimator.count_competitors(index, 35.9100, 127.1401, "카페")
    assert total == 0


def test_market_entry_keeps_legacy_keys(stores):
    """scoring.py / matching_agents.py가 기대하는 4개 키가 그대로 있어야 한다."""
    index = vacancy_estimator.StoreIndex(stores)
    entry = vacancy_estimator.build_market_entry(
        index, 35.8184, 127.1401, "카페", "전주시완산구", 57.1, 3
    )

    for key in (
        "foot_traffic_index",
        "competition_saturation_index",
        "demographic_fit_index",
        "estimated_rent",
    ):
        assert key in entry, key
    assert 0 <= entry["competition_saturation_index"] <= 100
    assert entry["estimated_rent"] > 0
    # 실측 카운트도 함께 들고 나온다 (화면 근거 표시용)
    assert entry["competitor_count"] == 1
    assert entry["nearby_store_count"] == 3


def test_estimated_rent_drops_on_upper_floors():
    first = vacancy_estimator.estimated_rent("전주시완산구", 30, 1)
    third = vacancy_estimator.estimated_rent("전주시완산구", 30, 3)
    assert first > third


# --- Provider ------------------------------------------------------------------


@pytest.fixture
def real_provider(tmp_path, building, register):
    """수집 스크립트 출력과 같은 캐시를 만들어 RealSanggaProvider에 물린다."""
    candidates = vacancy_estimator.candidates_for_building(
        building, register, today=date(2026, 9, 1)
    )
    index = vacancy_estimator.StoreIndex(building["stores"])

    buildings = {candidate["id"]: candidate for candidate in candidates}
    market = {
        candidate["id"]: {
            "카페": vacancy_estimator.build_market_entry(
                index,
                candidate["lat"],
                candidate["lng"],
                "카페",
                candidate["signgu_name"],
                candidate["area_pyeong"],
                candidate["floor"],
            )
        }
        for candidate in candidates
    }

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "buildings.json").write_text(json.dumps(buildings, ensure_ascii=False), encoding="utf-8")
    (real_dir / "market_data.json").write_text(json.dumps(market, ensure_ascii=False), encoding="utf-8")
    (real_dir / "region_stats.json").write_text(
        json.dumps({"is_mock": False, "regions": []}, ensure_ascii=False), encoding="utf-8"
    )

    from app.services.data_provider import DATA_DIR

    return RealSanggaProvider(real_dir=real_dir, data_dir=DATA_DIR), candidates[0]["id"]


def test_provider_exposes_candidates(real_provider):
    provider, building_id = real_provider
    summaries = provider.list_buildings()
    assert len(summaries) == 1
    assert summaries[0]["id"] == building_id
    assert provider.get_building(building_id)["vacancy"]["confidence"] == "high"


def test_data_sources_separate_real_from_estimated(real_provider):
    """화면 배지가 실데이터와 추정을 구분할 수 있어야 한다."""
    provider, building_id = real_provider
    sources = provider.get_data_sources(building_id)

    assert sources["built_year"].startswith("실데이터")
    assert "건축HUB" in sources["built_year"]
    assert sources["area_pyeong"].startswith("실데이터")
    assert sources["address"].startswith("실데이터")
    assert "상가(상권)정보" in sources["competition_saturation_index"]

    # 실데이터가 없는 항목은 추정값으로 표시돼야 한다
    assert sources["lighting_score"].startswith("추정값")
    assert sources["estimated_rent"].startswith("추정값")
    assert sources["demographic_fit_index"].startswith("추정값")
    assert sources["foot_traffic_index"].startswith("추정값")
    # 공실 자체가 추정임을 명시한다
    assert sources["vacancy"].startswith("추정값")
    assert "신뢰도 높음" in sources["vacancy"]


def test_provider_finds_building_by_address(real_provider):
    provider, building_id = real_provider
    found = provider.create_building_from_input("전주시 완산구 충경로 12", floor=3)
    assert found["matched_scenario_id"] == building_id


def test_region_options_come_from_collected_data(real_provider):
    provider, _ = real_provider
    options = provider.region_options()
    assert options[0] == "상관없음"
    assert "고사동" in options


# --- /api/match 통합 ------------------------------------------------------------


@pytest.fixture
def client_with_real_provider(real_provider):
    """RealSanggaProvider를 /api/match에 물려 응답 스키마까지 확인한다."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.data_provider import get_data_provider

    provider, building_id = real_provider
    app.dependency_overrides[get_data_provider] = lambda: provider
    try:
        yield TestClient(app), building_id
    finally:
        app.dependency_overrides.clear()


MATCH_PAYLOAD = {
    "business_type": "카페",
    "area_pyeong": 55,
    "budget": {"deposit": 30_000_000, "monthly_rent": 1_500_000},
    "region_pref": "고사동",
    "priority": "매출잠재력",
}


def test_match_returns_real_vacancy_candidate(client_with_real_provider):
    client, building_id = client_with_real_provider
    body = client.post("/api/match", json=MATCH_PAYLOAD).json()

    assert body["data_mode"] == "real"
    assert "건축물대장" in body["source_note"]
    assert body["total_candidates"] == 1

    match = body["matches"][0]
    assert match["building_id"] == building_id
    assert match["rank"] == "gold"
    assert match["built_year"] == 1995
    assert match["floor"] == 3
    assert match["region"] == "고사동"
    assert match["vacancy"]["confidence"] == "high"
    assert match["vacancy"]["method"] == "층별 미등록 추론"
    assert match["data_sources"]["built_year"].startswith("실데이터")
    assert match["competitor_count"] == 1
    assert match["nearby_store_count"] == 3
    assert "온잇커피" in match["nearby_stores"]


def test_match_keeps_results_when_filters_are_narrow(client_with_real_provider):
    """조건을 만족하는 매물이 없어도 추천이 비어서는 안 된다."""
    client, _ = client_with_real_provider
    narrow = {**MATCH_PAYLOAD, "region_pref": "없는동", "area_pyeong": 3}
    body = client.post("/api/match", json=narrow).json()

    assert body["total_candidates"] == 0, "조건을 만족한 후보는 0건"
    assert body["matches"], "그래도 차선책 매물은 돌려줘야 한다"


def test_match_options_lists_collected_regions(client_with_real_provider):
    client, _ = client_with_real_provider
    body = client.get("/api/match/options").json()

    assert body["data_mode"] == "real"
    assert body["region_options"][0] == "상관없음"
    assert "고사동" in body["region_options"]
    assert body["building_count"] == 1
