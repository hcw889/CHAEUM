"""
매칭 flow 재사용 원칙 가드.

팝업 브랜드 role은 예비창업자와 동일한 /api/match 파이프라인을 그대로 쓴다.
이 테스트는 "역할이 늘어도 백엔드 스코어링은 갈라지지 않는다"를 고정한다.

실행: cd backend && python -m pytest tests/
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import building_photo

# 매물 사진은 저작권 확인이 끝난 것만 커밋하므로 저장소에 없을 수 있다
# (backend/app/data/photos/README.md 참고). 사진에 의존하는 테스트는 건너뛴다.
requires_after_photo = pytest.mark.skipif(
    building_photo.find_after_file("b1") is None,
    reason="b1 시공 후 사진이 없는 환경 (photos/b1.after.* 미배치)",
)
requires_before_photo = pytest.mark.skipif(
    building_photo.find_photo_file("b1") is None,
    reason="b1 시공 전 사진이 없는 환경 (photos/b1.* 미배치)",
)

client = TestClient(app)

BASE_PAYLOAD = {
    "business_type": "카페",
    "area_pyeong": 15,
    "budget": {"deposit": 10_000_000, "monthly_rent": 1_000_000},
    "region_pref": "객사길",
    "commercial_style_pref": "유동인구중심",
    "priority": "매출잠재력",
}


def test_occupancy_term_does_not_change_scoring():
    """입점 희망 기간은 전달·로깅만 되고 추천 결과를 바꾸지 않는다."""
    baseline = client.post("/api/match", json=BASE_PAYLOAD).json()

    for term in ("단기", "장기"):
        result = client.post("/api/match", json={**BASE_PAYLOAD, "occupancy_term": term}).json()
        assert result == baseline, f"occupancy_term={term}이(가) 스코어링에 영향을 줬다"


def test_match_response_shape_unchanged():
    """결과는 TOP3 랭크 + 3개 에이전트 점수 구조를 유지한다."""
    matches = client.post("/api/match", json=BASE_PAYLOAD).json()["matches"]

    assert [m["rank"] for m in matches[:3]] == ["gold", "silver", "bronze"]
    assert all(m["rank"] is None for m in matches[3:])
    for m in matches:
        assert set(m["agent_scores"]) == {"budget", "market_fit", "condition"}
        assert m["explanation"]


def test_scoring_modules_have_no_role_branching():
    """
    스코어링 계층에 role/팝업 전용 분기가 들어오지 않았는지 확인한다.
    role별 분기는 프론트 문구(lib/roleCopy.ts)에만 존재해야 한다.
    """
    services = Path(__file__).resolve().parent.parent / "app" / "services"
    # role 식별자 자체를 찾는다. anthropic 메시지의 {"role": "user"}처럼 무관한
    # 'role' 문자열까지 잡지 않도록 실제 role 값과 분기 패턴만 본다.
    forbidden = ('"brand"', "'brand'", '"founder"', "'founder'", '"official"', "'official'", "팝업", "user_role")

    for name in ("matching_agents.py", "scoring.py"):
        source = (services / name).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{name}에 role 분기로 보이는 '{token}'이 있다"


def test_match_router_does_not_weight_occupancy_term():
    """
    match.py가 occupancy_term을 가중치 계산에 쓰지 않는지 확인한다.
    로깅 한 줄 외에 다른 용도로 등장하면 이 테스트가 깨진다.
    """
    source = (Path(__file__).resolve().parent.parent / "app" / "routers" / "match.py").read_text(encoding="utf-8")
    usages = [line.strip() for line in source.splitlines() if "occupancy_term" in line]

    assert usages, "occupancy_term 전달 경로가 사라졌다"
    assert all(
        line.startswith("#") or line.startswith("if payload.") or line.startswith("logger.")
        for line in usages
    ), f"occupancy_term이 로깅 외 용도로 쓰이고 있다: {usages}"


def test_building_photo_is_served_without_upload():
    """
    매물 사진은 사용자 업로드 없이 매물 데이터에서 공급되어야 한다.
    (시각화 화면의 사용자는 공간을 찾는 쪽이라 공실 사진을 갖고 있지 않다.)
    """
    body = client.get("/api/buildings/b1/photo").json()

    assert body["image"].startswith("data:image/png;base64,")
    assert body["source"] in {"file", "placeholder"}
    assert client.get("/api/buildings/does-not-exist/photo").status_code == 404


def test_render_uses_building_photo_when_no_upload():
    """사진을 올리지 않아도 매물 사진을 before로 써서 생성이 성립한다."""
    body = client.post("/api/buildings/b1/visualize", json={"concept": "플라워 팝업"}).json()

    assert body["before_image"].startswith("data:image/png;base64,")
    assert body["after_image"] != body["before_image"]


@requires_after_photo
def test_curated_before_after_pair_is_labeled_as_demo():
    """
    시공 전/후 실제 촬영본이 있는 매물(b1)은 생성 모델 없이도 전/후를 보여준다.
    단 컨셉 입력을 반영한 결과가 아니므로 mode가 "demo"로 구분되어야 한다
    (생성물로 오인되면 안 된다).
    """
    body = client.post("/api/buildings/b1/visualize", json={"concept": "플라워 팝업"}).json()

    assert body["mode"] == "demo"
    assert body["model"] == "curated-photo"
    assert body["before_image"] != body["after_image"]

    # 컨셉을 바꿔도 같은 고정 이미지가 나온다
    other = client.post("/api/buildings/b1/visualize", json={"concept": "서점"}).json()
    assert other["after_image"] == body["after_image"]


@requires_before_photo
def test_curated_pair_not_used_for_user_uploaded_photo():
    """사용자가 직접 올린 사진은 그 공간의 전/후가 아니므로 큐레이션 사진을 쓰면 안 된다."""
    import base64

    photo = "data:image/png;base64," + base64.b64encode(
        (Path(__file__).resolve().parent.parent / "app" / "data" / "photos" / "b1.png").read_bytes()
    ).decode()

    body = client.post(
        "/api/buildings/b1/visualize", json={"concept": "카페", "photo_data_url": photo}
    ).json()
    assert body["mode"] != "demo"


def test_buildings_without_after_photo_fall_back():
    """시공 후 사진이 없는 매물은 기존 폴백(mock)을 그대로 탄다."""
    body = client.post("/api/buildings/b2/visualize", json={"concept": "카페"}).json()
    assert body["mode"] == "mock"
