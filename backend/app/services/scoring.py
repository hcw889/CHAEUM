"""
채움(Chaeum) 업종 적합도 스코어링 스텁.

가중합(weighted scorecard) 방식으로 fit_score를 계산한다.
market_data 파라미터는 실제 데이터 연동 시 동일한 키 구조
(foot_traffic_index, competition_saturation_index, demographic_fit_index,
estimated_rent)를 유지하는 것을 전제로 하므로, 실데이터 연동 시에는
이 파일의 WEIGHTS_BY_TYPE 튜닝 정도만 필요하고 함수 시그니처/로직은
그대로 재사용할 수 있다.
"""

from __future__ import annotations

DEFAULT_WEIGHTS = {
    "foot_traffic": 0.30,
    "competition_saturation": 0.25,
    "demographic_fit": 0.25,
    "building_condition": 0.20,
}

# 업종별 가중치. 합은 1.0.
WEIGHTS_BY_TYPE: dict[str, dict[str, float]] = {
    "카페": {
        "foot_traffic": 0.35,
        "competition_saturation": 0.20,
        "demographic_fit": 0.20,
        "building_condition": 0.25,
    },
    "학원": {
        "foot_traffic": 0.15,
        "competition_saturation": 0.20,
        "demographic_fit": 0.40,
        "building_condition": 0.25,
    },
    "병원": {
        "foot_traffic": 0.10,
        "competition_saturation": 0.15,
        "demographic_fit": 0.45,
        "building_condition": 0.30,
    },
    "편의점": {
        "foot_traffic": 0.40,
        "competition_saturation": 0.30,
        "demographic_fit": 0.15,
        "building_condition": 0.15,
    },
    "스터디카페": {
        "foot_traffic": 0.20,
        "competition_saturation": 0.20,
        "demographic_fit": 0.45,
        "building_condition": 0.15,
    },
}


def building_condition_score(diagnosis: dict) -> float:
    """진단 항목(노후도/접근성/채광) 평균. 매칭 flow의 building_condition_agent도 재사용."""
    scores = [
        diagnosis.get("aging_score", 0),
        diagnosis.get("accessibility_score", 0),
        diagnosis.get("lighting_score", 0),
    ]
    return sum(scores) / len(scores) if scores else 0.0


def _building_condition_score(building: dict) -> float:
    return building_condition_score(building.get("diagnosis", {}))


def market_raw_scores(market_data: dict) -> dict:
    """유동인구/경쟁여유도/인구통계 원점수 (0-100, 높을수록 유리하도록 정규화)."""
    return {
        "foot_traffic": market_data.get("foot_traffic_index", 0),
        # 경쟁포화도는 높을수록 불리하므로 역변환해서 "낮은 경쟁도 점수"로 사용
        "competition_saturation": 100 - market_data.get("competition_saturation_index", 0),
        "demographic_fit": market_data.get("demographic_fit_index", 0),
    }


def _market_weights(business_type: str) -> dict:
    """건물 컨디션을 제외한 상권 3요소 가중치를 1.0 기준으로 재정규화."""
    weights = WEIGHTS_BY_TYPE.get(business_type, DEFAULT_WEIGHTS)
    market_weights = {k: v for k, v in weights.items() if k != "building_condition"}
    total = sum(market_weights.values()) or 1.0
    return {k: v / total for k, v in market_weights.items()}


def market_fit_score(business_type: str, market_data: dict) -> dict:
    """
    건물 컨디션을 제외한 상권 적합도만 분리 계산.
    calculate_fit_score와 동일한 raw score/가중치 테이블을 재사용하며,
    매칭 flow의 market_fit_agent에서 호출한다.
    """
    weights = _market_weights(business_type)
    raw = market_raw_scores(market_data)

    breakdown = {}
    score = 0.0
    for factor, weight in weights.items():
        contribution = weight * raw.get(factor, 0)
        score += contribution
        breakdown[f"{factor}_weight"] = round(weight, 3)
        breakdown[f"{factor}_raw_score"] = round(raw.get(factor, 0), 1)
        breakdown[f"{factor}_contribution"] = round(contribution, 1)

    return {"score": round(score, 1), "breakdown": breakdown}


def calculate_fit_score(building: dict, business_type: str, market_data: dict) -> dict:
    """
    Args:
        building: building.json 스키마를 따르는 dict (diagnosis 포함)
        business_type: "카페" | "학원" | "병원" | "편의점" | "스터디카페" 등
        market_data: 해당 building/업종 조합에 대한 raw 시장 신호
            {foot_traffic_index, competition_saturation_index, demographic_fit_index}
            (0-100 스케일, competition_saturation_index는 높을수록 경쟁이 치열함을 의미)

    Returns:
        {
          "fit_score": float (0-100),
          "breakdown": {
             "<factor>_weight": float,
             "<factor>_raw_score": float,
             "<factor>_contribution": float,
          } for factor in [foot_traffic, competition_saturation, demographic_fit, building_condition]
        }
    """
    weights = WEIGHTS_BY_TYPE.get(business_type, DEFAULT_WEIGHTS)

    raw_scores = {
        **market_raw_scores(market_data),
        "building_condition": _building_condition_score(building),
    }

    breakdown = {}
    fit_score = 0.0
    for factor, weight in weights.items():
        raw = raw_scores.get(factor, 0)
        contribution = weight * raw
        fit_score += contribution
        breakdown[f"{factor}_weight"] = weight
        breakdown[f"{factor}_raw_score"] = round(raw, 1)
        breakdown[f"{factor}_contribution"] = round(contribution, 1)

    return {
        "fit_score": round(fit_score, 1),
        "breakdown": breakdown,
    }
