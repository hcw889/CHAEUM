"""
주변 유동인구 API 가드.

SK open API 키가 없는 환경(= 채점자/팀원 로컬)에서도 유동인구 시각화 화면이
항상 값을 받도록, mock 폴백과 집계 규칙을 고정한다.

실행: cd backend && python -m pytest tests/
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import sk_footfall

client = TestClient(app)


@pytest.fixture(autouse=True)
def force_mock(monkeypatch):
    """실제 SK 호출 없이 테스트한다."""
    monkeypatch.setenv("SK_FOOTFALL_MODE", "mock")


@pytest.mark.parametrize("building_id", ["b1", "b2", "b3", "b4", "b5"])
def test_every_demo_building_has_footfall(building_id):
    response = client.get(f"/api/buildings/{building_id}/footfall")
    assert response.status_code == 200
    body = response.json()

    config = sk_footfall.load_areas()
    assert len(body["areas"]) >= config["min_areas"]
    assert body["mode"] == "mock" and body["is_mock"] is True

    for area in body["areas"]:
        assert len(area["hourly"]) == 24
        assert area["daily_total"] == sum(area["hourly"])
        assert 0 <= area["peak_hour"] <= 23
        assert area["hourly"][area["peak_hour"]] == max(area["hourly"])

    assert body["summary"]["daily_total"] == sum(a["daily_total"] for a in body["areas"])
    assert round(sum(a["share_pct"] for a in body["areas"])) == 100
    # 구역은 매물에서 가까운 순으로 골라야 한다.
    assert body["areas"] == sorted(body["areas"], key=lambda a: a["distance_m"])


def test_unknown_building_returns_404():
    assert client.get("/api/buildings/없는매물/footfall").status_code == 404


def test_real_building_uses_its_own_coordinates(monkeypatch):
    """
    실데이터 매물(vacancy 필드, region 비어 있음, 데모 표에 없는 id)은 상가정보 API 좌표를
    중심으로 쓴다. 예전에는 데모 표/지역명만 봐서 404가 났고 유동인구 지도가 비어 있었다.
    """
    from app.services.data_provider import get_data_provider

    real = {
        "id": "rtest000001",
        "address": "전북특별자치도 군산시 중앙로 1",
        "region": "",
        "lat": 35.9676,
        "lng": 126.7369,
        "vacancy": {"status": "likely_vacant"},
    }

    class Provider:
        def get_building(self, building_id):
            return real if building_id == real["id"] else None

    app.dependency_overrides[get_data_provider] = lambda: Provider()
    try:
        response = client.get(f"/api/buildings/{real['id']}/footfall")
    finally:
        app.dependency_overrides.pop(get_data_provider, None)

    assert response.status_code == 200
    body = response.json()
    assert (body["center_lat"], body["center_lng"]) == (real["lat"], real["lng"])
    assert body["address"] == real["address"]
    # 반경 밖이어도 가장 가까운 구역을 min_areas개까지 채워 지도가 비지 않는다.
    assert len(body["areas"]) >= sk_footfall.load_areas()["min_areas"]


def test_weekend_differs_from_weekday():
    weekday = client.get("/api/buildings/b1/footfall?day_type=weekday").json()
    weekend = client.get("/api/buildings/b1/footfall?day_type=weekend").json()
    assert weekday["summary"]["daily_total"] != weekend["summary"]["daily_total"]
    assert weekday["date"] != weekend["date"]


def test_mock_is_deterministic():
    first = client.get("/api/buildings/b2/footfall").json()
    second = client.get("/api/buildings/b2/footfall").json()
    assert first["areas"] == second["areas"]


def test_invalid_day_type_is_rejected():
    assert client.get("/api/buildings/b1/footfall?day_type=holiday").status_code == 422


def test_parse_hourly_accepts_varied_field_names():
    """SK 상품별 응답 구조가 달라도 시간/인구 쌍만 있으면 24칸으로 정규화된다."""
    payload = {
        "status": {"code": "00"},
        "contents": {"raw": [{"hour": h, "totPop": 100 + h} for h in range(24)]},
    }
    assert sk_footfall._parse_hourly(payload) == [100 + h for h in range(24)]

    # 시간대 값이 절반도 안 되면 실패로 보고 mock으로 폴백한다.
    assert sk_footfall._parse_hourly({"data": [{"hh": 1, "cnt": 10}]}) is None
