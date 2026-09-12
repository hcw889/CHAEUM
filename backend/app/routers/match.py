from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends

from app.models.schemas import MatchRequest, MatchResponse
from app.services import match_orchestrator, matching_agents
from app.services.building_location import get_building_location
from app.services.data_provider import DataProvider, MockDataProvider, get_data_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["match"])

RANK_LABELS = ["gold", "silver", "bronze"]

_MARKET_KEYS = ["foot_traffic_index", "competition_saturation_index", "demographic_fit_index", "estimated_rent"]
_NEUTRAL_MARKET_ENTRY = {"foot_traffic_index": 50, "competition_saturation_index": 50, "demographic_fit_index": 50, "estimated_rent": 0}

# 실데이터는 매물이 수백~수천 건이라 전수를 4-agent로 돌리면 응답이 수 분 단위가 된다
# (매물당 LangGraph fan-out + Vision/LLM 호출). 값싼 사전 필터로 후보를 좁힌 뒤
# 상위 SCORING_LIMIT건만 본 스코어링에 넣고, 화면에는 RESPONSE_LIMIT건만 돌려준다.
SCORING_LIMIT = 40
RESPONSE_LIMIT = 12

# 요청 평수 대비 허용 범위. 너무 좁히면 후보가 0건이 되므로 넉넉하게 둔다.
AREA_MIN_RATIO = 0.5
AREA_MAX_RATIO = 2.0
# 월세 추정치가 예산의 이 배수를 넘으면 사전 필터에서 떨어뜨린다.
RENT_MAX_RATIO = 2.5

REAL_SOURCE_NOTE = (
    "소상공인시장진흥공단 상가(상권)정보 API와 국토교통부 건축HUB 건축물대장정보 API를 "
    "건물 단위로 조인한 공실 추정 매물입니다. 두 API 모두 공실 여부를 직접 제공하지 않아, "
    "건축물대장상 근린생활시설·판매시설 층 중 등록 점포가 0건인 층을 공실로 추정했습니다. "
    "각 매물의 판정 근거와 신뢰도를 함께 확인하세요."
)
MOCK_SOURCE_NOTE = (
    "시연용 목업 데이터입니다. 실데이터로 바꾸려면 backend에서 "
    "python scripts/fetch_real_vacancies.py 를 실행하세요."
)


def _resolve_market_entry(market_data: dict, business_type: str) -> dict:
    """
    business_type이 수집된 업종 목록(카페/학원/병원/편의점/스터디카페)에 없는
    커스텀 입력(예: "베이커리")일 경우, 해당 건물의 업종별 평균 신호로 대체한다.
    """
    if business_type in market_data:
        return market_data[business_type]
    if not market_data:
        return dict(_NEUTRAL_MARKET_ENTRY)
    return {
        key: sum(entry.get(key, 0) for entry in market_data.values()) / len(market_data)
        for key in _MARKET_KEYS
    }


def _region_matches(building: dict, region_pref: str) -> bool:
    """희망 지역과 매물 지역이 맞는지. 지역명 단위가 섞여 있어 부분 일치로 본다."""
    if not region_pref or region_pref == "상관없음":
        return True
    region = (building.get("region") or "").strip()
    if not region:
        return True  # 지역 미상은 배제하지 않는다
    return region_pref in region or region in region_pref


def _passes_filter(building: dict, raw_entry: dict, payload: MatchRequest) -> bool:
    """
    4-agent 스코어링 전에 돌리는 값싼 선별 조건.

    "떨어지면 결과에서 사라진다"가 아니라 "먼저 볼 후보를 고른다"는 뜻이다.
    조건을 만족하는 매물이 SCORING_LIMIT보다 적으면 _candidate_pool()이
    나머지를 점수순으로 채워 넣는다. 희망 지역/평수/예산을 좁게 넣었을 때
    결과가 한두 건으로 쪼그라드는 일을 막기 위한 설계다.
    """
    if not _region_matches(building, payload.region_pref):
        return False

    if payload.area_pyeong:
        area = building.get("area_pyeong")
        if area and not (
            payload.area_pyeong * AREA_MIN_RATIO <= area <= payload.area_pyeong * AREA_MAX_RATIO
        ):
            return False

    monthly_rent = payload.budget.monthly_rent
    if monthly_rent > 0:
        estimated = raw_entry.get("estimated_rent") or 0
        if estimated and estimated > monthly_rent * RENT_MAX_RATIO:
            return False

    return True


def _prefilter_score(building: dict, raw_entry: dict, payload: MatchRequest) -> float:
    """
    사전 정렬용 근사 점수. 본 스코어링(matching_agents)과 같은 방향이지만
    LLM/Vision 호출 없이 숫자만 본다.
    """
    # 예산 여유: 추정 월세가 예산 이하일수록 높게
    monthly_rent = payload.budget.monthly_rent or 1
    rent_ratio = (raw_entry.get("estimated_rent") or 0) / monthly_rent
    budget = max(0.0, 100 - max(0.0, rent_ratio - 1) * 80) if rent_ratio > 1 else 100 - (1 - rent_ratio) * 10

    market = (
        (raw_entry.get("foot_traffic_index") or 0) * 0.4
        + (100 - (raw_entry.get("competition_saturation_index") or 0)) * 0.35
        + (raw_entry.get("demographic_fit_index") or 0) * 0.25
    )

    diagnosis = building.get("diagnosis") or {}
    condition = sum(diagnosis.get(key, 0) for key in ("aging_score", "accessibility_score", "lighting_score")) / 3

    weights = matching_agents.get_priority_weights(payload.priority)
    score = (
        weights.get("budget", 0) * budget
        + weights.get("market_fit", 0) * market
        + weights.get("condition", 0) * condition
    )

    # 희망 지역 일치와 공실 추정 신뢰도를 가산한다. 본 스코어링에서도 반영되는
    # 요소지만, 사전 정렬 단계에서 같은 지역/신뢰도 높은 매물을 앞세워야
    # SCORING_LIMIT에서 잘려 나가지 않는다.
    if _region_matches(building, payload.region_pref) and payload.region_pref != "상관없음":
        score += 8.0

    confidence_bonus = {"high": 6.0, "medium": 3.0, "low": 0.0}
    vacancy = building.get("vacancy") or {}
    return score + confidence_bonus.get(vacancy.get("confidence", ""), 0.0)


def _candidate_pool(provider: DataProvider, payload: MatchRequest) -> tuple[list[dict], list[dict], int]:
    """
    (스코어링 대상 건물, 각 건물의 raw 시장 신호, 조건을 만족한 후보 수).

    조건을 만족한 매물을 점수순으로 먼저 담고, SCORING_LIMIT에 못 미치면 나머지
    매물로 채운다. 그래서 조건을 좁게 넣어도 추천 목록이 비지 않고, 매물이 수백
    건인 실데이터에서는 조건에 맞는 것들이 자연스럽게 앞을 차지한다.
    """
    matched: list[tuple[float, dict, dict]] = []
    others: list[tuple[float, dict, dict]] = []

    for summary in provider.list_buildings():
        building = provider.get_building(summary["id"])
        if building is None:
            continue

        market_data = provider.get_market_data(building["id"])
        raw_entry = _resolve_market_entry(market_data, payload.business_type)
        entry = (_prefilter_score(building, raw_entry, payload), building, raw_entry)

        if _passes_filter(building, raw_entry, payload):
            matched.append(entry)
        else:
            others.append(entry)

    matched.sort(key=lambda item: item[0], reverse=True)
    others.sort(key=lambda item: item[0], reverse=True)

    selected = matched[:SCORING_LIMIT]
    if len(selected) < SCORING_LIMIT:
        # 조건을 만족한 매물이 적으면 차선책으로 채운다 (스코어링이 어차피 감점한다).
        selected = selected + others[: SCORING_LIMIT - len(selected)]

    logger.info(
        "match: 조건 만족 %d건 / 전체 %d건 → 스코어링 %d건",
        len(matched),
        len(matched) + len(others),
        len(selected),
    )
    return [item[1] for item in selected], [item[2] for item in selected], len(matched)


def _vacancy_payload(building: dict) -> Optional[dict[str, Any]]:
    """실데이터 매물의 공실 추정 정보. 목업에는 없으므로 None."""
    vacancy = building.get("vacancy")
    return vacancy if isinstance(vacancy, dict) and vacancy.get("confidence") else None


@router.post("/match", response_model=MatchResponse)
def match_buildings(payload: MatchRequest, provider: DataProvider = Depends(get_data_provider)):
    """
    예비창업자 매칭 flow: 조건 입력 → 사전 필터 → 4-agent 스코어링 → 매물 추천 순위.
    기존 진단 flow(/business-fit)와 반대 방향이며, 상권/건물 컨디션 계산 로직은
    scoring.py를 그대로 재사용한다 (matching_agents.py 참고).

    provider가 RealSanggaProvider면 상가정보 API + 건축물대장 API 조인으로 추정한
    실제 공실 매물이 후보가 되고, 캐시가 없으면 MockDataProvider 목업이 쓰인다.
    """
    # 입점 희망 기간은 값만 남기고 스코어링에는 넣지 않는다.
    # TODO: 단기임대 가중치 반영은 로드맵 다음 단계
    if payload.occupancy_term:
        logger.info("match: occupancy_term=%s (스코어링 미반영)", payload.occupancy_term)

    is_real = not isinstance(provider, MockDataProvider)
    priority_weights = matching_agents.get_priority_weights(payload.priority)
    user_budget = payload.budget.model_dump()

    buildings, raw_entries, total_candidates = _candidate_pool(provider, payload)

    matches = []
    for building, raw_entry in zip(buildings, raw_entries):
        # 매물 1건당 budget/market_fit/building_condition/space_vision을 병렬
        # fan-out으로 실행하고, aggregate(기존 orchestrator 가중합 그대로) →
        # explanation 순으로 이어지는 LangGraph StateGraph. 계산식은
        # matching_agents.py/space_vision_agent.py에서 그대로 재사용한다
        # (match_orchestrator.py는 실행 순서만 담당).
        # building["photo_url"]은 실제 상가 사진이 아닌 플레이스홀더 스톡이미지다.
        # 결과 화면은 카카오 로드뷰(lat/lng 기준)로 실물을 보여주므로, photo_url은
        # space_vision_agent의 Vision-LLM 입력으로만 쓴다. 로드뷰 실패를 임시 사진으로 대체하지 않는다.
        # 실데이터 매물에는 photo_url이 아예 없고 로드뷰만 쓴다.
        result = match_orchestrator.run_match_for_building(
            building_id=building["id"],
            building=building,
            user_budget=user_budget,
            business_type=payload.business_type,
            region_pref=payload.region_pref,
            raw_market_entry=raw_entry,
            priority_weights=priority_weights,
            photo_url=building.get("photo_url"),
        )

        matches.append(
            {
                "building_id": building["id"],
                "address": building["address"],
                "final_score": result["final_score"],
                "agent_scores": result["agent_scores"],
                "explanation": result["explanation"],
                "photo_url": building.get("photo_url"),
                "lat": building.get("lat"),
                "lng": building.get("lng"),
                "space_vision": result.get("space_vision"),
                "name": building.get("name"),
                "floor": building.get("floor"),
                "area_pyeong": building.get("area_pyeong"),
                "built_year": building.get("built_year") or None,
                "region": building.get("region"),
                "risk_grade": building.get("risk_grade"),
                "vacancy": _vacancy_payload(building),
                "data_sources": provider.get_data_sources(building["id"]),
                "competitor_count": raw_entry.get("competitor_count"),
                "nearby_store_count": raw_entry.get("nearby_store_count"),
                "nearby_stores": building.get("nearby_store_names") or [],
                "location": get_building_location(building),
            }
        )

    matches.sort(key=lambda m: m["final_score"], reverse=True)
    matches = matches[:RESPONSE_LIMIT]
    for i, m in enumerate(matches):
        m["rank"] = RANK_LABELS[i] if i < len(RANK_LABELS) else None

    return MatchResponse(
        matches=matches,
        data_mode="real" if is_real else "mock",
        source_note=REAL_SOURCE_NOTE if is_real else MOCK_SOURCE_NOTE,
        total_candidates=total_candidates,
    )


@router.get("/match/options")
def match_options(provider: DataProvider = Depends(get_data_provider)):
    """
    매칭 입력 화면의 선택지. 실데이터에서는 수집된 매물이 실제로 존재하는
    지역만 보여야 한다 (없는 지역을 고르면 결과가 비어 버린다).
    """
    is_real = not isinstance(provider, MockDataProvider)
    regions = None
    if hasattr(provider, "region_options"):
        regions = provider.region_options()  # type: ignore[attr-defined]

    meta = getattr(provider, "meta", {}) or {}
    return {
        "data_mode": "real" if is_real else "mock",
        "region_options": regions,
        "business_types": provider.list_business_types(),
        "building_count": len(provider.list_buildings()),
        "collected_at": meta.get("collected_at"),
        "data_reference_month": meta.get("data_reference_month"),
        "sources": meta.get("sources"),
        "source_note": REAL_SOURCE_NOTE if is_real else MOCK_SOURCE_NOTE,
    }
