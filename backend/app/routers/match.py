from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.models.schemas import MatchRequest, MatchResponse
from app.services import match_orchestrator, matching_agents
from app.services.data_provider import DataProvider, get_data_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["match"])

RANK_LABELS = ["gold", "silver", "bronze"]

_MARKET_KEYS = ["foot_traffic_index", "competition_saturation_index", "demographic_fit_index", "estimated_rent"]
_NEUTRAL_MARKET_ENTRY = {"foot_traffic_index": 50, "competition_saturation_index": 50, "demographic_fit_index": 50, "estimated_rent": 0}


def _resolve_market_entry(market_data: dict, business_type: str) -> dict:
    """
    business_type이 mock 5개 업종(카페/학원/병원/편의점/스터디카페)에 없는
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


@router.post("/match", response_model=MatchResponse)
def match_buildings(payload: MatchRequest, provider: DataProvider = Depends(get_data_provider)):
    """
    예비창업자 매칭 flow: 조건 입력 → 4-agent 스코어링 → 매물 추천 순위.
    기존 진단 flow(/business-fit)와 반대 방향이며, 상권/건물 컨디션 계산 로직은
    scoring.py를 그대로 재사용한다 (matching_agents.py 참고).
    """
    # 입점 희망 기간은 값만 남기고 스코어링에는 넣지 않는다.
    # TODO: 단기임대 가중치 반영은 로드맵 다음 단계
    if payload.occupancy_term:
        logger.info("match: occupancy_term=%s (스코어링 미반영)", payload.occupancy_term)

    priority_weights = matching_agents.get_priority_weights(payload.priority)
    user_budget = payload.budget.model_dump()

    matches = []
    for summary in provider.list_buildings():
        building = provider.get_building(summary["id"])
        if building is None:
            continue

        market_data = provider.get_market_data(building["id"])
        raw_entry = _resolve_market_entry(market_data, payload.business_type)

        # 매물 1건당 budget/market_fit/building_condition/space_vision을 병렬
        # fan-out으로 실행하고, aggregate(기존 orchestrator 가중합 그대로) →
        # explanation 순으로 이어지는 LangGraph StateGraph. 계산식은
        # matching_agents.py/space_vision_agent.py에서 그대로 재사용한다
        # (match_orchestrator.py는 실행 순서만 담당).
        # TODO: building["photo_url"]은 현재 실제 상가 사진이 아닌 플레이스홀더
        # 스톡이미지입니다. 실제 상가 외관 사진 확보 후 buildings.json의 photo_url을
        # 교체해야 합니다.
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
                "space_vision": result.get("space_vision"),
            }
        )

    matches.sort(key=lambda m: m["final_score"], reverse=True)
    for i, m in enumerate(matches):
        m["rank"] = RANK_LABELS[i] if i < len(RANK_LABELS) else None

    return MatchResponse(matches=matches)
