"""
채움(Chaeum) 예비창업자 매칭 flow — space_vision_agent.

Vision-LLM(Anthropic API) 단일 호출로 상가 외관 사진에서 공간 특징(쇼윈도/간판/
유리비율/테라스/노출도/유동인구·차량 체감 등)을 추출하고, 이를 노출성/접근성/
팝업 적합도 점수로 변환한다. YOLO 등 별도 CV 모델은 쓰지 않는다.

기존 4-agent 파이프라인(matching_agents.py)과는 완전히 독립적인 모듈이며,
final_score/agent_scores 계산에는 전혀 관여하지 않는다. 라우터에서 매물별로
별도 필드(space_vision)로만 나란히 붙인다.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "space_vision_cache.json"

# analyze_storefront_features()의 모든 실패 케이스(API 키 없음/타임아웃/파싱 실패 등)에서
# 사용하는 폴백값. explanation_agent(matching_agents.py)와 동일한 폴백 패턴을 따른다.
FALLBACK_FEATURES: dict[str, Any] = {
    "show_window_count": 2,
    "signage": True,
    "glass_ratio": 50,
    "terrace": False,
    "exposure_score": 60,
    "aging_signs": False,
    "foot_traffic_estimate": "보통",
    "vehicle_presence": "보통",
}

_PROMPT = """이 상가 외관 사진을 보고 아래 JSON 형식으로만 답하라.
- show_window_count: 쇼윈도 개수 (정수 추정)
- signage: 간판 유무 (boolean)
- glass_ratio: 전면 유리 비율 (0-100 추정)
- terrace: 테라스/외부공간 유무 (boolean)
- exposure_score: 외부 노출면 확보 정도 (0-100)
- aging_signs: 노후 시설 흔적 유무 (boolean)
- foot_traffic_estimate: 사진에 보이는 유동인구/보행자 체감 수준 ('낮음' | '보통' | '높음')
- vehicle_presence: 사진에 보이는 차량/주차 체감 수준 ('낮음' | '보통' | '높음')
다른 텍스트 없이 이 JSON 객체만 출력하라."""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_TRAFFIC_SCORE = {"낮음": 30, "보통": 60, "높음": 90}
_VEHICLE_SCORE = {"낮음": 30, "보통": 60, "높음": 90}


def _is_remote(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")


def _build_image_source(image_path: str) -> dict[str, Any]:
    if _is_remote(image_path):
        return {"type": "url", "url": image_path}

    import base64

    data = Path(image_path).read_bytes()
    media_type = _MEDIA_TYPES.get(Path(image_path).suffix.lower(), "image/jpeg")
    return {
        "type": "base64",
        "media_type": media_type,
        "data": base64.standard_b64encode(data).decode("utf-8"),
    }


def _parse_features(text: str) -> Optional[dict[str, Any]]:
    """모델 응답에서 JSON 객체를 파싱한다. 순수 JSON이 아니면(설명 텍스트가 섞이면)
    첫 번째 {...} 블록만 추출해 재시도한다."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def analyze_storefront_features(image_path: str) -> dict:
    """
    Vision-LLM(Anthropic API, model="claude-sonnet-4-6")에 이미지+프롬프트를 전달해
    상가 외관 사진의 공간 특징을 추출한다.

    API 키 없음/네트워크 차단/타임아웃/응답 파싱 실패 등 모든 실패 케이스에서
    FALLBACK_FEATURES를 반환하며, 어떤 경우에도 예외를 전파하지 않는다
    (matching_agents.explanation_agent와 동일한 폴백 패턴 — 데모 중 500 방지).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return dict(FALLBACK_FEATURES)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=15.0)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": _build_image_source(image_path)},
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )
        text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text").strip()
        parsed = _parse_features(text)
        if not parsed:
            return dict(FALLBACK_FEATURES)
        # 일부 키만 파싱된 경우를 대비해 폴백값 위에 덮어쓴다.
        return {**FALLBACK_FEATURES, **parsed}
    except Exception:
        # 네트워크 차단, API 키 오류, 타임아웃, 이미지 로드 실패, 파싱 실패 등
        # 모든 실패 케이스에서 데모가 멈추지 않도록 폴백값으로 대체한다.
        return dict(FALLBACK_FEATURES)


def _build_visual_summary(
    glass_ratio: float, exposure_score: float, accessibility_score: float, terrace: bool, aging_signs: bool
) -> str:
    parts = []
    if glass_ratio >= 60 and exposure_score >= 60:
        parts.append("전면 유리 비율이 높고 외부 노출성이 좋습니다")
    elif exposure_score >= 60:
        parts.append("외부 노출성이 양호한 편입니다")
    else:
        parts.append("외부 노출성은 다소 제한적입니다")

    if accessibility_score >= 70:
        parts.append("유동인구·차량 접근성도 우수합니다")
    elif accessibility_score >= 50:
        parts.append("접근성은 무난한 수준입니다")
    else:
        parts.append("접근성은 다소 아쉬운 편입니다")

    if terrace:
        parts.append("테라스 등 외부공간을 팝업 연출에 활용할 수 있습니다")
    if aging_signs:
        parts.append("다만 노후 시설 흔적이 일부 보입니다")

    return " · ".join(parts)


def calculate_space_score(storefront_features: dict) -> dict:
    """
    storefront_features(analyze_storefront_features의 반환값) 하나만 입력으로 받아
    Space Score(노출성/접근성/팝업 적합도)를 산출한다.

    visual_summary는 규칙 기반 템플릿 문장 조립으로 생성한다(LLM 추가 호출 없음 —
    비용/실패 지점을 늘리지 않기 위함).
    """
    glass_ratio = float(storefront_features.get("glass_ratio", 50))
    raw_exposure = float(storefront_features.get("exposure_score", 60))
    signage = bool(storefront_features.get("signage", True))
    terrace = bool(storefront_features.get("terrace", False))
    show_window_count = int(storefront_features.get("show_window_count", 2))
    aging_signs = bool(storefront_features.get("aging_signs", False))
    foot_traffic = storefront_features.get("foot_traffic_estimate", "보통")
    vehicle_presence = storefront_features.get("vehicle_presence", "보통")

    exposure_score = glass_ratio * 0.5 + raw_exposure * 0.4 + (10 if signage else 0)
    exposure_score = round(max(0.0, min(100.0, exposure_score)), 1)

    accessibility_score = _TRAFFIC_SCORE.get(foot_traffic, 60) * 0.6 + _VEHICLE_SCORE.get(vehicle_presence, 60) * 0.4
    accessibility_score = round(max(0.0, min(100.0, accessibility_score)), 1)

    popup_fit_score = (exposure_score + accessibility_score) / 2 + (10 if terrace else 0)
    popup_fit_score = round(max(0.0, min(100.0, popup_fit_score)), 1)

    detected_elements = [
        f"쇼윈도 {show_window_count}개",
        "간판 있음" if signage else "간판 없음",
        f"유동인구 {foot_traffic}",
        f"차량 통행 {vehicle_presence}",
        "테라스 있음" if terrace else "테라스 없음",
    ]
    if aging_signs:
        detected_elements.append("노후 시설 흔적 있음")

    return {
        "exposure_score": exposure_score,
        "accessibility_score": accessibility_score,
        "popup_fit_score": popup_fit_score,
        "detected_elements": detected_elements,
        "visual_summary": _build_visual_summary(glass_ratio, exposure_score, accessibility_score, terrace, aging_signs),
    }


def space_vision_agent(building_photo_path: Optional[str]) -> dict:
    """
    analyze_storefront_features -> calculate_space_score 순서로 호출하는 진입점.

    photo_path가 None이거나 로컬 파일이 존재하지 않으면 Vision-LLM 호출 자체를
    시도하지 않고 즉시 전체 폴백값을 반환한다 (불필요한 API 비용 방지).
    """
    if not building_photo_path:
        return calculate_space_score(FALLBACK_FEATURES)
    if not _is_remote(building_photo_path) and not Path(building_photo_path).is_file():
        return calculate_space_score(FALLBACK_FEATURES)

    features = analyze_storefront_features(building_photo_path)
    return calculate_space_score(features)


def _load_cache() -> dict[str, Any]:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# 서버 프로세스 시작 시 1회 로드. 매물별 Vision-LLM 호출 결과를 building_id 기준으로
# 캐싱해 /match 호출마다 재계산하지 않도록 한다.
_cache: dict[str, Any] = _load_cache()


def get_space_vision(building_id: str, building_photo_path: Optional[str]) -> dict:
    """
    building_id 기준 파일 캐시(app/data/space_vision_cache.json)를 우선 조회하고,
    없을 때만 space_vision_agent()를 호출해 계산한 뒤 캐시에 저장한다.
    """
    if building_id in _cache:
        return _cache[building_id]

    result = space_vision_agent(building_photo_path)

    # 사진이 없으면 결과가 FALLBACK_FEATURES에서 나온 상수라서 캐시할 가치가 없다.
    # 실데이터 매물(상가정보+건축물대장 조인)은 외관 사진이 없어 수백 건이 들어오는데,
    # 그걸 전부 캐시에 쓰면 파일만 불어나고 매 요청마다 디스크 쓰기가 반복된다.
    if not building_photo_path:
        return result

    _cache[building_id] = result
    _save_cache(_cache)
    return result
