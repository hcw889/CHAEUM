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
        "lnoMnno": 123,
        "lnoSlno": 4,
        "bldMngNo": "5211110100101230004000001",
        "bldNm": "온잇빌딩",
        "rdnmAdr": "전북특별자치도 전주시 완산구 충경로 12",
        "flrNo": 1,
        "hoNo": "101",
        "lon": 127.140123,
        "lat": 35.818456,
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
        "lnoMnno": 123,
        "lnoSlno": 4,
        "bldMngNo": "5211110100101230004000001",
        "bldNm": "온잇빌딩",
        "rdnmAdr": "전북특별자치도 전주시 완산구 충경로 12",
        "flrNo": 2,
        "hoNo": "201",
        "lon": 127.140130,
        "lat": 35.818460,
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
        "lnoMnno": 123,
        "lnoSlno": 4,
        "bldMngNo": "5211110100101230004000001",
        "bldNm": "온잇빌딩",
        "rdnmAdr": "전북특별자치도 전주시 완산구 충경로 12",
        "flrNo": "B1",
        "hoNo": "B01",
        "lon": 127.140118,
        "lat": 35.818450,
    },
]

# 건축물대장 getBrTitleInfo 응답 봉투. 지상 4층 / 지하 1층.
TITLE_PAYLOAD = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
        "body": {
            "items": {
                "item": {
                    "mgmBldrgstPk": 1186122494,
                    "bldNm": "온잇빌딩",
                    "platPlc": "전북특별자치도 전주시 완산구 고사동 123-4",
                    "newPlatPlc": "전북특별자치도 전주시 완산구 충경로 12",
                    "useAprDay": "19950320",
                    "totArea": 820.5,
                    "archArea": 210.3,
                    "grndFlrCnt": 4,
                    "ugrndFlrCnt": 1,
                    "heit": 15.2,
                    "strctCdNm": "철근콘크리트구조",
                    "mainPurpsCdNm": "제2종근린생활시설",
                    "etcPurps": "소매점, 일반음식점",
                    "rideUseElvtCnt": 1,
                    "emgenUseElvtCnt": 0,
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
                        "flrNo": 1,
                        "flrNoNm": "지하1층",
                        "mainPurpsCdNm": "제2종근린생활시설",
                        "etcPurps": "일반음식점",
                        "area": 180.2,
                        "strctCdNm": "철근콘크리트구조",
                    },
                    {
                        "flrGbCdNm": "지상",
                        "flrNo": 1,
                        "flrNoNm": "1층",
                        "mainPurpsCdNm": "제1종근린생활시설",
                        "etcPurps": "소매점",
                        "area": 195.4,
                        "strctCdNm": "철근콘크리트구조",
                    },
                    {
                        "flrGbCdNm": "지상",
                        "flrNo": 2,
                        "flrNoNm": "2층",
                        "mainPurpsCdNm": "제2종근린생활시설",
                        "etcPurps": "미용원",
                        "area": 190.0,
                        "strctCdNm": "철근콘크리트구조",
                    },
                    {
                        "flrGbCdNm": "지상",
                        "flrNo": 3,
                        "flrNoNm": "3층",
                        "mainPurpsCdNm": "제2종근린생활시설",
                        "etcPurps": "사무소",
                        "area": 188.6,
                        "strctCdNm": "철근콘크리트구조",
                    },
                    {
                        "flrGbCdNm": "지상",
                        "flrNo": 4,
                        "flrNoNm": "4층",
                        "mainPurpsCdNm": "단독주택",
                        "etcPurps": "주인세대",
                        "area": 120.0,
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
    """층 표기가 없는 점포가 있으면 '이 층만 비었다'는 판정을 믿을 수 없다."""
    noisy = dict(building)
    noisy["stores_by_floor"] = {**building["stores_by_floor"], None: [{"name": "층미상가게"}]}
    noisy["stores"] = building["stores"] + [{"name": "층미상가게"}]

    candidate = vacancy_estimator.candidates_for_building(
        noisy, register, today=date(2026, 9, 1)
    )[0]
    # 층 표기 없는 점포가 바로 이 층에 있을 수 있다 — 가장 큰 오판 경로라 낮음이다.
    assert candidate["vacancy"]["confidence"] == "low"
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


# --- 서비스키 (API별로 각각) ----------------------------------------------------


def test_each_api_uses_its_own_service_key(monkeypatch):
    """
    두 API는 포털 활용신청이 각각이라 서비스키도 각각이다.
    상가정보 키를 건축물대장 호출에 쓰면 안 된다.
    """
    monkeypatch.delenv(datagokr.SHARED_SERVICE_KEY_ENV, raising=False)
    monkeypatch.setenv(datagokr.SANGGA_KEY_ENV, "SANGGA-KEY")
    monkeypatch.setenv(datagokr.BLDRGST_KEY_ENV, "BLDRGST-KEY")

    assert datagokr.service_key(datagokr.SANGGA_KEY_ENV) == "SANGGA-KEY"
    assert datagokr.service_key(datagokr.BLDRGST_KEY_ENV) == "BLDRGST-KEY"
    # 각 클라이언트 모듈이 자기 키를 가리킨다
    assert sangga_api.KEY_ENV == datagokr.SANGGA_KEY_ENV
    assert building_register_api.KEY_ENV == datagokr.BLDRGST_KEY_ENV


def test_shared_key_is_used_only_as_fallback(monkeypatch):
    """한 키로 두 API가 열리는 계정은 공통 키 하나만 넣어도 동작해야 한다."""
    monkeypatch.delenv(datagokr.SANGGA_KEY_ENV, raising=False)
    monkeypatch.delenv(datagokr.BLDRGST_KEY_ENV, raising=False)
    monkeypatch.setenv(datagokr.SHARED_SERVICE_KEY_ENV, "SHARED-KEY")

    assert datagokr.service_key(datagokr.SANGGA_KEY_ENV) == "SHARED-KEY"
    assert datagokr.service_key(datagokr.BLDRGST_KEY_ENV) == "SHARED-KEY"
    assert datagokr.has_service_key(datagokr.BLDRGST_KEY_ENV)

    # 전용 키가 있으면 그쪽이 이긴다
    monkeypatch.setenv(datagokr.BLDRGST_KEY_ENV, "BLDRGST-KEY")
    assert datagokr.service_key(datagokr.BLDRGST_KEY_ENV) == "BLDRGST-KEY"
    assert datagokr.service_key(datagokr.SANGGA_KEY_ENV) == "SHARED-KEY"


def test_missing_key_message_names_the_api(monkeypatch):
    monkeypatch.delenv(datagokr.SANGGA_KEY_ENV, raising=False)
    monkeypatch.delenv(datagokr.SHARED_SERVICE_KEY_ENV, raising=False)

    assert not datagokr.has_service_key(datagokr.SANGGA_KEY_ENV)
    message = datagokr.missing_key_message(datagokr.SANGGA_KEY_ENV)
    assert "소상공인시장진흥공단" in message
    assert datagokr.SANGGA_KEY_ENV in message


def test_get_json_demands_the_right_key(monkeypatch):
    """건축물대장 키만 있고 상가정보 키가 없으면 상가정보 호출이 막혀야 한다."""
    monkeypatch.delenv(datagokr.SANGGA_KEY_ENV, raising=False)
    monkeypatch.delenv(datagokr.SHARED_SERVICE_KEY_ENV, raising=False)
    monkeypatch.setenv(datagokr.BLDRGST_KEY_ENV, "BLDRGST-KEY")

    with pytest.raises(datagokr.DataGoKrError) as excinfo:
        datagokr.get_json("http://example.test/x", {}, key_env=datagokr.SANGGA_KEY_ENV)
    assert datagokr.SANGGA_KEY_ENV in str(excinfo.value)


# --- 실응답에서 드러난 케이스 ----------------------------------------------------


def test_rooftop_floor_does_not_merge_into_first_floor():
    """
    실측 사례: flrGbCdNm="옥탑", flrNo=1 이 지상 1층과 flrNo가 겹친다.
    층 번호만으로 묶으면 옥탑 계단실 면적이 1층에 더해지고 용도도 섞인다.
    """
    rows = [
        {"flrGbCdNm": "지상", "flrNo": 1, "flrNoNm": "1층",
         "mainPurpsCdNm": "기타제2종근린생활시설", "etcPurps": "제2종근린생활시설(일반음식점)",
         "area": 80.91, "strctCdNm": "철근콘크리트구조"},
        {"flrGbCdNm": "옥탑", "flrNo": 1, "flrNoNm": "옥탑1층",
         "mainPurpsCdNm": "기타제2종근린생활시설", "etcPurps": "계단실",
         "area": 6.76, "strctCdNm": "철근콘크리트구조"},
    ]
    floors = {entry["floor_label"]: entry for entry in building_register_api.parse_floors(rows)}

    assert set(floors) == {"1층", "옥탑1층"}, "옥탑이 1층과 합쳐지면 안 된다"
    assert floors["1층"]["area"] == 80.91, "옥탑 면적이 1층에 더해지면 안 된다"
    assert "계단실" not in floors["1층"]["purpose"]
    # 옥탑은 용도명이 근린생활시설로 적혀 있어도 임대 가능한 상가 층이 아니다
    assert floors["옥탑1층"]["is_non_leasable"] is True


def test_rooftop_is_never_a_vacancy_candidate():
    building = {
        "key": "mng:X", "bld_name": "테스트", "stores": [], "stores_by_floor": {},
        "signgu_name": "전주시 완산구", "ldong_name": "고사동",
        "road_address": "전북특별자치도 전주시 완산구 테스트로 1", "lat": 35.8, "lng": 127.1,
    }
    register = {
        "title": {"approval_year": 2002, "elevators": 0, "ground_floors": 1},
        "floors": building_register_api.parse_floors([
            {"flrGbCdNm": "옥탑", "flrNo": 1, "flrNoNm": "옥탑1층",
             "mainPurpsCdNm": "기타제2종근린생활시설", "etcPurps": "계단실", "area": 6.76},
        ]),
        "register_params": {},
    }
    assert vacancy_estimator.candidates_for_building(building, register) == []


def test_integer_jibun_fields_become_register_params():
    """상가정보는 lnoMnno/lnoSlno를 정수로 내려준다 (문서의 lnbrMnnm/lnbrSlno가 아니다)."""
    raw = {
        "ldongCd": "5211112700", "plotSctCd": "1",
        "lnoMnno": 222, "lnoSlno": 3,
    }
    params = sangga_api.building_register_params(sangga_api.normalize_store(raw))
    assert params == {
        "sigunguCd": "52111", "bjdongCd": "12700",
        "platGbCd": "0", "bun": "0222", "ji": "0003",
    }


def test_zero_subnumber_is_kept():
    """부번이 0(부번 없음)이어도 파라미터가 만들어져야 한다."""
    raw = {"ldongCd": "5211112700", "plotSctCd": "1", "lnoMnno": 15, "lnoSlno": 0}
    params = sangga_api.building_register_params(sangga_api.normalize_store(raw))
    assert params is not None and params["bun"] == "0015" and params["ji"] == "0000"


def test_empty_floor_number_is_unknown_not_zero():
    """flrNo가 빈 문자열인 레코드가 절반이다. 0층으로 오해하면 판정이 망가진다."""
    assert sangga_api.normalize_store({"flrNo": ""})["floor"] is None
    assert sangga_api.normalize_store({"flrNo": 1})["floor"] == 1
    assert sangga_api.normalize_store({"flrNo": "B1"})["floor"] == -1


def test_blank_building_name_is_treated_as_empty():
    """건축물대장 bldNm은 비어 있을 때 ' '(공백)으로 온다."""
    title = building_register_api.parse_title({"bldNm": " ", "dongNm": " ", "useAprDay": "20021128"})
    assert title["bld_name"] == ""
    assert title["approval_year"] == 2002


def test_short_floor_label_is_normalized():
    """실측: flrNoNm이 '지1'처럼 줄여 온다. 화면에 그대로 내보내면 안 된다."""
    rows = [
        {"flrGbCdNm": "지하", "flrNo": 1, "flrNoNm": "지1",
         "mainPurpsCdNm": "소매점", "etcPurps": "점포", "area": 29.0},
        {"flrGbCdNm": "지상", "flrNo": 1, "flrNoNm": "1층",
         "mainPurpsCdNm": "소매점", "etcPurps": "점포", "area": 80.0},
    ]
    labels = [entry["floor_label"] for entry in building_register_api.parse_floors(rows)]
    assert labels == ["지하1층", "1층"]


def test_non_retail_purposes_are_not_commercial():
    """
    골프연습장·사무실 전체 층까지 상가로 보면 카페 창업자에게 무의미한 후보가 올라온다
    (실수집에서 236평 골프연습장이 공실 후보로 잡혔다).
    """
    assert building_register_api.is_commercial_purpose("제2종근린생활시설 소매점")
    assert building_register_api.is_commercial_purpose("소매점 점포")
    assert building_register_api.is_commercial_purpose("판매시설")
    # 근린생활시설로 등재된 소규모 사무소/학원은 계속 포함된다
    assert building_register_api.is_commercial_purpose("제2종근린생활시설(사무소)")

    assert not building_register_api.is_commercial_purpose("운동시설 골프연습장")
    assert not building_register_api.is_commercial_purpose("업무시설 사무소")
    assert not building_register_api.is_commercial_purpose("교육연구시설")
    assert not building_register_api.is_commercial_purpose("숙박시설")
    assert not building_register_api.is_commercial_purpose("공동주택 아파트")


def test_utility_floors_under_commercial_main_purpose_are_excluded():
    """
    실수집 사례: 주용도가 "기타제1종근린생활시설"이어도 기타용도가 PIT층·보일러실·
    주택인 층이 공실 후보로 올라왔다. 세부용도 단어로 걸러야 한다.
    """
    rows = [
        {"flrGbCdNm": "지하", "flrNo": 1, "flrNoNm": "지하1층",
         "mainPurpsCdNm": "기타제1종근린생활시설", "etcPurps": "PIT층", "area": 17.08},
        {"flrGbCdNm": "지하", "flrNo": 2, "flrNoNm": "지하2층",
         "mainPurpsCdNm": "기타제1종근린생활시설", "etcPurps": "보일러실", "area": 30.0},
        {"flrGbCdNm": "지상", "flrNo": 4, "flrNoNm": "4층",
         "mainPurpsCdNm": "기타제1종근린생활시설", "etcPurps": "주택", "area": 90.0},
        {"flrGbCdNm": "지하", "flrNo": 3, "flrNoNm": "지하3층",
         "mainPurpsCdNm": "병원", "etcPurps": "의료시설(병원)", "area": 300.0},
        {"flrGbCdNm": "지하", "flrNo": 4, "flrNoNm": "지하4층",
         "mainPurpsCdNm": "장례식장", "etcPurps": "제2종근린생활시설(일반음식점)", "area": 120.0},
    ]
    floors = {entry["floor_label"]: entry for entry in building_register_api.parse_floors(rows)}
    for label in ("지하1층", "지하2층", "4층", "지하3층", "지하4층"):
        assert floors[label]["is_non_leasable"] is True, label


def test_floor_with_shop_and_utility_rows_keeps_shop_area_only():
    """
    같은 층에 "소매점 / 관리실"이 따로 온 경우, 관리실 때문에 층 전체가 제외되면
    안 되고 면적은 소매점 줄만 합산해야 한다 (남원축협빌딩 1층 실측).
    """
    rows = [
        {"flrGbCdNm": "지상", "flrNo": 1, "flrNoNm": "1층",
         "mainPurpsCdNm": "소매점", "etcPurps": "소매점", "area": 60.0},
        {"flrGbCdNm": "지상", "flrNo": 1, "flrNoNm": "1층",
         "mainPurpsCdNm": "기타사무소", "etcPurps": "관리실", "area": 12.0},
        {"flrGbCdNm": "지상", "flrNo": 1, "flrNoNm": "1층",
         "mainPurpsCdNm": "주차장", "etcPurps": "주차장", "area": 200.0},
    ]
    (floor,) = building_register_api.parse_floors(rows)
    assert floor["is_commercial"] is True
    assert floor["is_non_leasable"] is False
    assert floor["area"] == 60.0
    assert floor["purpose"] == "소매점 / 기타사무소 관리실 / 주차장"


def test_duplicate_main_and_etc_purpose_is_not_repeated():
    text = building_register_api._purpose_text({"mainPurpsCdNm": "휴게음식점", "etcPurps": "휴게음식점"})
    assert text == "휴게음식점"
    text = building_register_api._purpose_text(
        {"mainPurpsCdNm": "제2종근린생활시설", "etcPurps": "제2종근린생활시설(일반음식점)"}
    )
    assert text == "제2종근린생활시설(일반음식점)"


def test_junk_building_name_falls_back_to_dong():
    building = {"bld_name": "전체", "ldong_name": "모현동1가"}
    assert vacancy_estimator._display_name(building, "2층") == "모현동1가 상가 2층"


def _fake_buildings(counts: dict[str, int]) -> dict[str, dict]:
    buildings = {}
    for signgu, count in counts.items():
        for index in range(count):
            key = "{}#{}".format(signgu, index)
            buildings[key] = {
                "key": key, "signgu_name": signgu, "register_params": {"bun": "0001"},
                "lat": 35.8, "lng": 127.1, "stores": [], "stores_by_floor": {},
            }
    return buildings


def test_select_buildings_keeps_every_signgu_under_small_cap():
    """
    실수집(상한 100)에서 전주가 0건이었다. 시군마다 최소 10건을 주고 마지막에
    [:max_buildings]로 자르면 가나다순 뒤쪽 시군(전주·정읍·진안)이 통째로 빠진다.
    """
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "fetch_real_vacancies.py"
    spec = importlib.util.spec_from_file_location("fetch_real_vacancies", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    counts = {
        "고창군": 40, "군산시": 300, "김제시": 60, "남원시": 80, "무주군": 20, "부안군": 50,
        "순창군": 15, "완주군": 70, "익산시": 350, "임실군": 10, "장수군": 8,
        "전주시 완산구": 900, "전주시 덕진구": 700, "정읍시": 90, "진안군": 12,
    }
    selected = module.select_buildings(_fake_buildings(counts), 100)
    assert len(selected) == 100
    by_signgu = {}
    for building in selected:
        by_signgu[building["signgu_name"]] = by_signgu.get(building["signgu_name"], 0) + 1
    assert by_signgu["전주시 완산구"] >= 30, by_signgu
    assert by_signgu["전주시 덕진구"] >= 20, by_signgu
    assert by_signgu["정읍시"] >= 1, by_signgu

    only_jeonju = module.select_buildings(_fake_buildings(counts), 100, ["전주시"])
    assert {b["signgu_name"] for b in only_jeonju} == {"전주시 완산구", "전주시 덕진구"}
    assert len(only_jeonju) == 100


def test_confidence_reflects_measured_floor_coverage(building, register):
    """
    실수집 측정값 기준으로 등급이 갈려야 한다 (flrNo 50% 누락, 건물당 점포 1.8건).
    '층 찍힌 점포 3건 이상 = 높음' 같은 기준은 아무 매물도 높음이 되지 않는다.
    """
    def confidence_with(known: int, unknown: int) -> str:
        stub = dict(building)
        stores = [{"name": f"s{i}"} for i in range(known)]
        by_floor = {1: stores[:1], 2: stores[1:]} if known else {}
        if unknown:
            by_floor[None] = [{"name": "층미상"} for _ in range(unknown)]
        stub["stores"] = stores + by_floor.get(None, [])
        stub["stores_by_floor"] = by_floor
        return vacancy_estimator.candidates_for_building(stub, register)[0]["vacancy"]["confidence"]

    assert confidence_with(known=2, unknown=0) == "high"
    assert confidence_with(known=1, unknown=0) == "medium"
    assert confidence_with(known=0, unknown=0) == "low"
    # 층 미상 점포가 있으면 층이 많이 찍혀 있어도 믿을 수 없다
    assert confidence_with(known=5, unknown=1) == "low"


# --- 실패 진단 -------------------------------------------------------------------


def test_service_key_never_appears_in_error_text(monkeypatch):
    """
    httpx 예외 문구에는 쿼리스트링이 통째로 들어간다. 그대로 로그에 흘리면
    .env의 서비스키가 콘솔과 파일에 남는다.
    """
    monkeypatch.setenv(datagokr.SANGGA_KEY_ENV, "abcdef1234567890SECRETKEY")
    raw = (
        "Client error '403 Forbidden' for url "
        "'http://apis.data.go.kr/x?bun=0222&serviceKey=abcdef1234567890SECRETKEY'"
    )
    masked = datagokr.mask_secrets(raw)

    assert "abcdef1234567890SECRETKEY" not in masked
    assert "<SERVICE_KEY>" in masked
    assert "403 Forbidden" in masked, "진단에 필요한 정보는 남아야 한다"


def test_mask_secrets_handles_unknown_keys():
    """환경변수에 없는 키도 쿼리스트링 패턴으로 가려야 한다."""
    masked = datagokr.mask_secrets("url?serviceKey=someKeyNotInEnv123&pageNo=1")
    assert "someKeyNotInEnv123" not in masked
    assert "pageNo=1" in masked


def test_auth_error_is_detected_so_collection_stops_early():
    """
    키가 거부되면 남은 건물도 전부 같은 이유로 실패한다. 조용히 세기만 하면
    '오류 100'만 남고 원인을 알 수 없다 (실제로 겪은 문제).
    """
    assert building_register_api.is_auth_error(
        "Client error '403 Forbidden' for url 'http://...'"
    )
    assert building_register_api.is_auth_error("SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    assert building_register_api.is_auth_error("등록되지 않은 서비스키")

    # 정상적인 '그 지번에 대장이 없음'은 키 문제가 아니다 — 멈추면 안 된다
    assert not building_register_api.is_auth_error("resultCode=03 NODATA_ERROR")
    assert not building_register_api.is_auth_error("ReadTimeout")
