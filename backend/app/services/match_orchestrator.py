"""
채움(Chaeum) 예비창업자 매칭 flow — LangGraph 기반 실행 레이어.

matching_agents.py의 4개 에이전트(budget_agent/market_fit_agent/
building_condition_agent/orchestrator)와 explanation_agent, 그리고
space_vision_agent의 계산식은 이 모듈에서 단 한 줄도 바꾸지 않는다.
이 모듈은 그 함수들을 StateGraph 노드로 감싸 다음 순서로 실행하는
"실행 레이어"만 제공한다:

    START ─┬─> budget_node ──────────────┐
           ├─> market_fit_node ──────────┼─> aggregate_node ─> END
           ├─> building_condition_node ──┘
           └─> space_vision_node ──────────────────────────────> END

budget/market_fit/building_condition은 서로 독립적이라 병렬 fan-out으로 실행되고,
aggregate_node(기존 orchestrator의 가중합 계산을 그대로 이식)가 세 결과를 모은다.
space_vision_node는 4-agent 스코어링과 완전히 독립적이라 병렬로 실행되며
final_score/agent_scores 계산에는 전혀 관여하지 않는다.

추천 사유 생성(explanation_agent)은 이 그래프에 들어 있지 않다. 매물마다 실행하면
정렬 뒤 버려질 매물까지 LLM을 호출하게 되어, 라우터가 순위를 확정한 다음
generate_explanations()로 상위 몇 건에만 호출한다.

각 노드는 실패 시 그래프 전체가 죽지 않도록 노드 레벨에서 예외를 흡수한다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services import matching_agents, space_vision_agent


class MatchState(TypedDict, total=False):
    # --- 입력 ---
    building_id: str
    building: dict[str, Any]
    user_budget: dict[str, Any]
    business_type: str
    region_pref: str
    raw_market_entry: dict[str, Any]  # budget_agent에 넘기는 raw 시장 신호 (estimated_rent 포함)
    priority_weights: dict[str, float]
    photo_url: Optional[str]

    # --- 각 노드의 중간 산출물 ---
    budget_score: float
    budget_detail: str
    market_fit_score: float
    market_fit_detail: str
    building_condition_score: float
    building_condition_detail: str
    space_vision: Optional[dict[str, Any]]

    # --- 최종 산출물 (응답 스키마와 1:1 대응) ---
    # explanation은 그래프 밖에서 생성한다 (generate_explanations 참고).
    final_score: float
    agent_scores: dict[str, float]


def _budget_node(state: MatchState) -> dict:
    try:
        result = matching_agents.budget_agent(state["user_budget"], state["raw_market_entry"])
        return {"budget_score": result["score"], "budget_detail": result["detail"]}
    except Exception:
        # budget_agent는 원래 외부 호출이 없어 예외를 던지지 않지만, 그래프 전체가
        # 죽지 않도록 노드 레벨에서 방어적으로 흡수한다.
        return {"budget_score": 0.0, "budget_detail": ""}


def _market_fit_node(state: MatchState) -> dict:
    try:
        market_entry = {**state["raw_market_entry"], "region": state["building"].get("region")}
        result = matching_agents.market_fit_agent(state["business_type"], state["region_pref"], market_entry)
        return {"market_fit_score": result["score"], "market_fit_detail": result["detail"]}
    except Exception:
        return {"market_fit_score": 0.0, "market_fit_detail": ""}


def _building_condition_node(state: MatchState) -> dict:
    try:
        result = matching_agents.building_condition_agent(state["building"].get("diagnosis", {}))
        return {"building_condition_score": result["score"], "building_condition_detail": result["detail"]}
    except Exception:
        return {"building_condition_score": 0.0, "building_condition_detail": ""}


def _space_vision_node(state: MatchState) -> dict:
    try:
        result = space_vision_agent.get_space_vision(state["building_id"], state.get("photo_url"))
        return {"space_vision": result}
    except Exception:
        # space_vision_agent 자체가 이미 모든 실패 케이스를 내부에서 폴백 처리하지만,
        # 캐시 I/O 등 예상 밖의 예외까지 대비해 노드 레벨에서 한 번 더 감싼다.
        # final_score/agent_scores에는 관여하지 않는 필드이므로 None으로 두어도 안전하다.
        return {"space_vision": None}


def _aggregate_node(state: MatchState) -> dict:
    """기존 orchestrator()의 가중합 계산을 그대로 이식한다 (계산식 변경 없음)."""
    scores = {
        "budget": state["budget_score"],
        "market_fit": state["market_fit_score"],
        "condition": state["building_condition_score"],
        "business_type": state["business_type"],
    }
    final_score = matching_agents.orchestrator(scores, state["priority_weights"])
    return {
        "final_score": final_score,
        "agent_scores": {
            "budget": scores["budget"],
            "market_fit": scores["market_fit"],
            "condition": scores["condition"],
        },
    }


def _build_graph():
    graph = StateGraph(MatchState)

    graph.add_node("budget", _budget_node)
    graph.add_node("market_fit", _market_fit_node)
    graph.add_node("building_condition", _building_condition_node)
    graph.add_node("space_vision", _space_vision_node)
    graph.add_node("aggregate", _aggregate_node)

    # 병렬 fan-out: budget/market_fit/building_condition/space_vision은 서로 독립적이다.
    graph.add_edge(START, "budget")
    graph.add_edge(START, "market_fit")
    graph.add_edge(START, "building_condition")
    graph.add_edge(START, "space_vision")

    # aggregate는 3개 스코어링 에이전트가 모두 끝난 뒤 실행된다 (fan-in).
    graph.add_edge("budget", "aggregate")
    graph.add_edge("market_fit", "aggregate")
    graph.add_edge("building_condition", "aggregate")

    graph.add_edge("aggregate", END)
    # space_vision은 4-agent 스코어링과 무관하게 독립적으로 끝난다.
    graph.add_edge("space_vision", END)

    return graph.compile()


_compiled_graph = _build_graph()


def run_match_for_building(
    *,
    building_id: str,
    building: dict[str, Any],
    user_budget: dict[str, Any],
    business_type: str,
    region_pref: str,
    raw_market_entry: dict[str, Any],
    priority_weights: dict[str, float],
    photo_url: Optional[str],
) -> MatchState:
    """
    매물 1건에 대해 컴파일된 매칭 그래프를 실행한다. /api/match 라우터가 매물마다
    한 번씩 호출하는 진입점이며, 반환값은 MatchState(TypedDict)로 응답 스키마의
    각 필드와 1:1 대응된다.
    """
    initial_state: MatchState = {
        "building_id": building_id,
        "building": building,
        "user_budget": user_budget,
        "business_type": business_type,
        "region_pref": region_pref,
        "raw_market_entry": raw_market_entry,
        "priority_weights": priority_weights,
        "photo_url": photo_url,
    }
    return _compiled_graph.invoke(initial_state)


# 추천 사유 생성은 동시에 몇 건까지 던질지. 대상이 상위 5건뿐이라 전부 한 번에 보낸다.
EXPLANATION_WORKERS = 5


def _one_explanation(target: tuple[dict[str, Any], dict[str, Any]]) -> str:
    building, scores = target
    try:
        return matching_agents.explanation_agent(building, scores)
    except Exception:
        # explanation_agent는 이미 내부에서 모든 실패 케이스를 폴백 처리하지만,
        # 스레드에서 올라온 예외가 응답 전체를 죽이지 않도록 한 번 더 감싼다.
        return matching_agents.fallback_explanation(scores.get("business_type", "이 업종"))


def generate_explanations(
    targets: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    max_workers: int = EXPLANATION_WORKERS,
) -> list[str]:
    """
    (building, scores) 목록을 받아 같은 순서의 추천 사유 문자열 목록을 돌려준다.

    LLM 호출 1건이 실측 4~6초라 순차로 돌리면 건수만큼 그대로 곱해진다. 매물 사이에
    의존관계가 없으므로 스레드풀로 동시에 던져 전체 대기를 1건 수준으로 줄인다
    (explanation_agent는 blocking HTTP 호출이라 스레드로 충분하다).
    """
    if not targets:
        return []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(targets))) as pool:
        return list(pool.map(_one_explanation, targets))
