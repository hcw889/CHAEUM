"""
채움(Chaeum) 예비창업자 매칭 flow — 4-agent 스코어링.

기존 진단 flow(scoring.py의 calculate_fit_score)는 "이 건물에 어떤 업종이 맞는가"를
계산하고, 이 모듈은 반대 방향인 "이 조건의 창업자에게 어떤 매물이 맞는가"를 계산한다.
상권 관련 raw score/가중치 계산은 새로 만들지 않고 scoring.py의
market_raw_scores / market_fit_score / building_condition_score를 그대로 재사용한다.
"""

from __future__ import annotations

from app.services import llm, scoring

# 보증금 mock 데이터가 없으므로, 월세 추정치의 배수로 보증금을 추정한다.
# (전주 원도심 상가 관행상 월세의 약 10배 수준을 mock 기준으로 사용)
ESTIMATED_DEPOSIT_MULTIPLIER = 10

PRIORITY_WEIGHTS: dict[str, dict[str, float]] = {
    "예산절약": {"budget": 0.5, "market_fit": 0.3, "condition": 0.2},
    "매출잠재력": {"budget": 0.2, "market_fit": 0.6, "condition": 0.2},
    "건물안정성": {"budget": 0.2, "market_fit": 0.2, "condition": 0.6},
}
DEFAULT_PRIORITY_WEIGHTS = {"budget": 1 / 3, "market_fit": 1 / 3, "condition": 1 / 3}


def get_priority_weights(priority: str) -> dict[str, float]:
    return PRIORITY_WEIGHTS.get(priority, DEFAULT_PRIORITY_WEIGHTS)


def _ratio_score(estimate: float, budget: float) -> float:
    """budget 대비 estimate 비율 기반 점수. 예산 이내면 90~100점, 초과하면 급격히 감점."""
    if budget <= 0:
        return 50.0
    ratio = estimate / budget
    if ratio <= 1:
        return round(100 - (1 - ratio) * 10, 1)
    return round(max(0.0, 100 - (ratio - 1) * 80), 1)


def budget_agent(user_budget: dict, market_data: dict) -> dict:
    """
    예산(보증금+월세) vs 매물 추정 임대료 적합도.

    Args:
        user_budget: {"deposit": number, "monthly_rent": number}
        market_data: 해당 건물/업종 조합의 raw 시장 신호 (estimated_rent 포함)
    """
    estimated_rent = market_data.get("estimated_rent", 0)
    estimated_deposit = estimated_rent * ESTIMATED_DEPOSIT_MULTIPLIER

    rent_score = _ratio_score(estimated_rent, user_budget.get("monthly_rent", 0))
    deposit_score = _ratio_score(estimated_deposit, user_budget.get("deposit", 0))
    score = round(rent_score * 0.6 + deposit_score * 0.4, 1)

    detail = (
        f"예상 월세 {estimated_rent:,.0f}원(추정 보증금 {estimated_deposit:,.0f}원) "
        f"vs 예산 월세 {user_budget.get('monthly_rent', 0):,.0f}원 기준 적합도 {score}점"
    )
    return {"score": score, "detail": detail}


def market_fit_agent(business_type: str, region_pref: str, market_data: dict) -> dict:
    """
    상권 적합도. scoring.market_fit_score()로 유동인구/경쟁포화도/인구통계 가중합을 계산하고,
    희망 지역(region_pref)과의 일치 여부를 가감점으로 반영한다.

    market_data는 raw 시장 신호에 building의 "region"이 병합된 dict를 받는다.
    """
    base = scoring.market_fit_score(business_type, market_data)
    score = base["score"]
    region = market_data.get("region")

    if region_pref and region_pref != "상관없음" and region:
        if region_pref == region:
            score = min(100.0, score + 5)
            region_note = f"희망 지역({region_pref})과 일치"
        else:
            score = max(0.0, score - 15)
            region_note = f"희망 지역({region_pref})과 다른 지역({region})"
    else:
        region_note = "희망 지역 조건 없음"

    detail = f"{business_type} 상권 적합도 {base['score']}점 · {region_note}"
    return {"score": round(score, 1), "detail": detail}


def building_condition_agent(building_diagnosis: dict) -> dict:
    """건물 컨디션(노후도/접근성/채광 평균). scoring.building_condition_score() 재사용."""
    score = round(scoring.building_condition_score(building_diagnosis), 1)
    detail = (
        f"노후도 {building_diagnosis.get('aging_score', 0)} · "
        f"접근성 {building_diagnosis.get('accessibility_score', 0)} · "
        f"채광 {building_diagnosis.get('lighting_score', 0)} (평균 {score}점)"
    )
    return {"score": score, "detail": detail}


def fallback_explanation(business_type: str) -> str:
    """LLM을 호출하지 않는(또는 실패한) 매물에 쓰는 템플릿 문구."""
    return f"예산 조건과 {business_type} 상권 적합도가 특히 잘 맞는 매물입니다."


def explanation_agent(building: dict, scores: dict) -> str:
    """
    3개 에이전트 점수를 받아 "왜 이 매물이 맞는지" 한 줄 자연어 생성.
    Gemini 호출을 시도하고, 실패/타임아웃/키 미설정 시 템플릿으로 폴백한다
    (데모 중 죽지 않도록 llm.generate_text가 모든 예외를 흡수하고 None을 돌려준다).
    """
    business_type = scores.get("business_type", "이 업종")
    fallback = fallback_explanation(business_type)

    prompt = (
        f"매물 주소: {building.get('address', '')}\n"
        f"예산적합도 {scores.get('budget')}점, "
        f"상권적합도 {scores.get('market_fit')}점, "
        f"건물컨디션 {scores.get('condition')}점.\n"
        f"'{business_type}' 창업 희망자에게 이 매물이 왜 적합한지 "
        "한국어 한 문장으로만 설명해줘."
    )
    # 한 문장이라 출력 자체는 100토큰 이하지만, 상한에 사고 토큰이 함께 잡히므로
    # 여유를 둔다 (llm.THINKING_LEVEL 주석 참고).
    #
    # timeout은 Anthropic 시절의 5초에서 올렸다. 실측 응답이 4~6초라 5초로 두면
    # 절반가량이 타임아웃으로 폴백해, 어떤 매물은 LLM 문장이고 어떤 매물은 템플릿인
    # 뒤섞인 결과가 나온다.
    text = llm.generate_text(prompt, max_output_tokens=1024, timeout_s=15.0)
    return text or fallback


def orchestrator(scores: dict, priority_weights: dict) -> float:
    """
    final_score = w1*budget + w2*market_fit + w3*condition

    Args:
        scores: {"budget": number, "market_fit": number, "condition": number}
        priority_weights: {"budget": w1, "market_fit": w2, "condition": w3}
    """
    final = (
        priority_weights.get("budget", 0) * scores.get("budget", 0)
        + priority_weights.get("market_fit", 0) * scores.get("market_fit", 0)
        + priority_weights.get("condition", 0) * scores.get("condition", 0)
    )
    return round(final, 1)
