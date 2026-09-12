"""
사람이 전사한 실측 유동인구(footfall_measured.json) 가드.

전사 규격(footfall_measured.README.md)대로 적은 구역은 실측으로, 비어 있거나
잘못 적은 구역은 mock으로 남는지 고정한다.

실행: cd backend && python -m pytest tests/test_footfall_measured.py
"""

from __future__ import annotations

import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import footfall_measured, sk_footfall

client = TestClient(app)

GAEKSA = {
    "name": "객사길",
    "sbiz_area": "객사길 상권",
    "collected_at": "2026-09-13",
    "reference_month": "2026-07",
    "daily_average": 20000,
    "time_bands_pct": {"00-06": 4, "06-11": 16, "11-14": 20, "14-17": 20, "17-21": 28, "21-24": 12},
    "weekday_pct": {"mon": 13, "tue": 13, "wed": 13, "thu": 13, "fri": 14, "sat": 18, "sun": 16},
}


@pytest.fixture(autouse=True)
def force_mock(monkeypatch):
    monkeypatch.setenv("SK_FOOTFALL_MODE", "mock")


@pytest.fixture
def measured_file(tmp_path, monkeypatch):
    """테스트용 전사 파일. 저장소의 실제 footfall_measured.json은 건드리지 않는다."""
    path = tmp_path / "footfall_measured.json"
    monkeypatch.setattr(footfall_measured, "DATA_PATH", path)

    def write(areas: dict, **extra):
        path.write_text(json.dumps({"source_label": "테스트 실측", "areas": areas, **extra}, ensure_ascii=False), encoding="utf-8")
        # 로더는 mtime으로 변경을 감지한다. 같은 초에 두 번 쓰면 구분이 안 되므로 mtime을 강제로 올린다.
        _mtimes.append(_mtimes[-1] + 1)
        os.utime(path, (_mtimes[-1], _mtimes[-1]))

    return write


_mtimes = [time.time()]


def _area(body: dict, area_id: str) -> dict:
    return next(a for a in body["areas"] if a["id"] == area_id)


def test_template_in_repo_is_valid_and_lists_every_area():
    """저장소의 템플릿은 21개 구역 id를 모두 갖고, 규격 오류가 없어야 한다."""
    areas = sk_footfall.load_areas()["areas"]
    report = footfall_measured.coverage(areas, sk_footfall.PROFILES)
    assert report["errors"] == {}
    assert report["unknown_ids"] == []
    assert set(report["measured"]) | set(report["missing"]) == {a["id"] for a in areas}


def test_measured_area_replaces_mock_and_keeps_band_totals(measured_file):
    measured_file({"gaeksa": GAEKSA})
    body = client.get("/api/buildings/b2/footfall?day_type=weekday").json()

    area = _area(body, "gaeksa")
    assert area["source"] == "measured" and area["is_mock"] is False
    assert area["reference_month"] == "2026-07"
    # 평일 배수 = 평일 5일 평균(13.2) × 7 / 100 = 0.924
    expected_daily = 20000 * (13 * 4 + 14) / 5 * 7 / 100
    assert abs(area["daily_total"] - expected_daily) <= 3
    # 구간 합계는 전사한 비율을 그대로 따른다 (06-11시 = 16%).
    assert abs(sum(area["hourly"][6:11]) - expected_daily * 0.16) <= 3

    # 나머지 구역은 아직 mock이고, 응답 전체는 '실측 있음'으로 표시된다.
    others = [a for a in body["areas"] if a["id"] != "gaeksa"]
    assert all(a["source"] == "mock" and a["is_mock"] for a in others)
    assert body["is_mock"] is False
    assert body["measured_count"] == 1
    assert body["source_label"] == "테스트 실측"
    assert body["data_reference_month"] == "2026-07"
    assert body["note"] and all(a["name"] in body["note"] for a in others)


def test_weekend_uses_weekend_share(measured_file):
    measured_file({"gaeksa": GAEKSA})
    weekday = _area(client.get("/api/buildings/b2/footfall?day_type=weekday").json(), "gaeksa")
    weekend = _area(client.get("/api/buildings/b2/footfall?day_type=weekend").json(), "gaeksa")
    # 주말 비율(18+16)/2 = 17 > 평일 13.2 → 주말이 더 많다.
    assert weekend["daily_total"] > weekday["daily_total"]
    assert abs(weekend["daily_total"] - 20000 * 17 * 7 / 100) <= 3


def test_no_weekday_pct_means_same_total_both_days(measured_file):
    entry = {**GAEKSA, "weekday_pct": None}
    measured_file({"gaeksa": entry})
    weekday = _area(client.get("/api/buildings/b2/footfall?day_type=weekday").json(), "gaeksa")
    weekend = _area(client.get("/api/buildings/b2/footfall?day_type=weekend").json(), "gaeksa")
    assert weekday["daily_total"] == weekend["daily_total"]
    assert abs(weekday["daily_total"] - 20000) <= 3


def test_direct_hourly_is_accepted(measured_file):
    hourly = [100] * 24
    measured_file({"gaeksa": {"hourly": hourly, "reference_month": "2026-08"}})
    area = _area(client.get("/api/buildings/b2/footfall").json(), "gaeksa")
    assert area["source"] == "measured" and area["hourly"] == hourly


def test_all_measured_has_no_note(measured_file):
    areas = sk_footfall.load_areas()["areas"]
    measured_file({a["id"]: {**GAEKSA, "name": a["name"]} for a in areas})
    body = client.get("/api/buildings/b2/footfall").json()
    assert body["note"] is None
    assert body["measured_count"] == len(body["areas"])
    assert all(a["source"] == "measured" for a in body["areas"])


@pytest.mark.parametrize(
    "broken, fragment",
    [
        ({**GAEKSA, "time_bands_pct": {**GAEKSA["time_bands_pct"], "17-21": 40}}, "합이 100"),
        ({**GAEKSA, "time_bands_pct": {"00-06": 20, "06-14": 40, "17-24": 40}}, "비었거나 겹칩니다"),
        ({**GAEKSA, "time_bands_pct": {"00-12": 50, "12-23": 50}}, "24시까지"),
        ({**GAEKSA, "daily_average": 0}, "0보다 커야"),
        ({**GAEKSA, "daily_average": "많음"}, "숫자여야"),
        ({**GAEKSA, "weekday_pct": {"mon": 50, "tue": 50}}, "비어 있습니다"),
        ({**GAEKSA, "reference_month": "2026.07"}, "YYYY-MM"),
        ({**GAEKSA, "hourly": [1, 2, 3]}, "24개"),
    ],
)
def test_broken_entry_falls_back_to_mock_and_is_reported(measured_file, broken, fragment):
    measured_file({"gaeksa": broken})
    area = _area(client.get("/api/buildings/b2/footfall").json(), "gaeksa")
    assert area["source"] == "mock"

    report = client.get("/api/footfall/status").json()["measured"]
    assert "gaeksa" in report["errors"] and fragment in report["errors"]["gaeksa"]
    assert "gaeksa" not in report["measured"]


def test_partially_filled_entry_counts_as_missing(measured_file):
    """일평균만 적고 시간대 비율을 아직 안 적었으면 오류가 아니라 '비어 있음'이다."""
    measured_file({"gaeksa": {**GAEKSA, "time_bands_pct": {"00-06": 4, "06-11": None}}})
    report = client.get("/api/footfall/status").json()["measured"]
    assert "gaeksa" in report["missing"] and report["errors"] == {}


def test_file_edit_is_picked_up_without_restart(measured_file):
    measured_file({})
    assert _area(client.get("/api/buildings/b2/footfall").json(), "gaeksa")["source"] == "mock"
    measured_file({"gaeksa": GAEKSA})
    assert _area(client.get("/api/buildings/b2/footfall").json(), "gaeksa")["source"] == "measured"


def test_unknown_id_is_reported(measured_file):
    measured_file({"nowhere": GAEKSA})
    report = client.get("/api/footfall/status").json()["measured"]
    assert report["unknown_ids"] == ["nowhere"]
