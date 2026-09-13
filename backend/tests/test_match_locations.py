"""매칭 위치 응답이 유동인구 조회·스코어링과 독립적인지 검증한다."""

from fastapi.testclient import TestClient

from app.main import app
from app.services import building_location, data_provider
from app.services.sk_footfall import load_areas

client = TestClient(app)


def setup_module() -> None:
    # 이 테스트는 데모 매물 15건(mock)을 전제한다. app/data/real/ 캐시가 있으면
    # RealSanggaProvider가 선택돼 실패하므로 목업을 강제한다.
    import os

    os.environ["CHAEUM_FORCE_MOCK"] = "1"
    data_provider.reload_provider()


def teardown_module() -> None:
    import os

    os.environ.pop("CHAEUM_FORCE_MOCK", None)
    data_provider.reload_provider()
PAYLOAD = {
    "business_type": "카페",
    "budget": {"deposit": 10000000, "monthly_rent": 1000000},
    "region_pref": "상관없음",
    "priority": "매출잠재력",
}


def test_match_and_legacy_location_lookup_share_demo_coordinates():
    locations_response = client.get("/api/buildings/locations")
    assert locations_response.status_code == 200
    locations = locations_response.json()
    centers = load_areas()["buildings"]
    matches = client.post("/api/match", json=PAYLOAD).json()["matches"]
    assert len(locations) == 15
    # 위치 목록은 전체 데모 매물을, 매칭 응답은 상위 12건을 제공한다.
    assert len(matches) == 12

    for match in matches:
        location = match["location"]
        assert location == locations[match["building_id"]]
        assert location["is_approximate"] is True
        center = centers[match["building_id"]]
        assert (location["lat"], location["lng"]) == (center["lat"], center["lng"])


def test_missing_coordinates_do_not_change_recommendations(monkeypatch):
    baseline = client.post("/api/match", json=PAYLOAD).json()["matches"]
    monkeypatch.setattr(building_location, "_demo_locations", lambda: {})
    result = client.post("/api/match", json=PAYLOAD).json()["matches"]
    assert client.get("/api/buildings/locations").json() == {}
    assert all(match["location"] is None for match in result)
    assert [{k: v for k, v in match.items() if k != "location"} for match in result] == [
        {k: v for k, v in match.items() if k != "location"} for match in baseline
    ]
