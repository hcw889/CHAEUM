"""
매칭 flow 재사용 원칙 가드.

팝업 브랜드 role은 예비창업자와 동일한 /api/match 파이프라인을 그대로 쓴다.
이 테스트는 "역할이 늘어도 백엔드 스코어링은 갈라지지 않는다"를 고정한다.

실행: cd backend && python -m pytest tests/
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

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
