"""
채움(Chaeum) LLM 호출 래퍼 — Gemini API (google-genai).

LLM을 쓰는 곳은 matching_agents.explanation_agent(텍스트 한 문장)와
space_vision_agent.analyze_storefront_features(이미지+텍스트 JSON 추출) 두 곳뿐이다.
클라이언트 생성·키 조회·예외 흡수가 양쪽에 중복되지 않도록 여기로 모은다.

호출 실패(키 미설정/네트워크 차단/타임아웃/빈 응답)에서 예외를 전파하지 않고 None을
돌려준다. 폴백 문구와 폴백 상수는 도메인마다 다르므로 무엇으로 대체할지는 호출부가 정한다.
다만 조용히 삼키지는 않고 warning 로그를 남긴다 — 폴백값과 실제 응답이 겉보기에
구분되지 않아서, 로그가 없으면 "키를 넣었는데도 계속 폴백"인 상황을 알아챌 수 없다.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 환경변수 GEMINI_MODEL로 덮어쓸 수 있다.
#
# gemini-3.8-flash(최신 stable Flash)는 무료 등급 한도가 하루 20건이라, 검색 한 번에
# 수십 건을 호출하는 이 앱에서는 첫 검색만으로 소진된다. 두 작업 모두 한 문장 생성과
# 8필드 JSON 추출이라 상위 모델이 필요 없어서 lite로 내렸다 (모델별로 한도 버킷이
# 따로라 실제 여유는 AI Studio의 rate limit 페이지에서 확인할 것).
# gemini-2.5 계열은 신규 사용자에게 더 이상 열리지 않는다(404).
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Gemini 3 계열은 thinking이 기본 on(medium)이고, max_output_tokens에 사고 토큰이
# 포함된다. 이 프로젝트의 두 작업은 추론이 거의 필요 없는 짧은 생성이라 thinking_level을
# 낮춘다. 출력 상한도 넉넉히 잡아야 한다 — 상한을 조이면 사고 토큰이 먼저 소진되어
# output_text가 빈 문자열로 돌아오고, 호출은 성공했는데 폴백이 나가는 형태가 된다.
THINKING_LEVEL = "low"


def model_name() -> str:
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def is_configured() -> bool:
    """키가 없으면 호출부가 API를 때리지 않고 즉시 폴백하도록 하기 위한 조회."""
    return bool(os.environ.get("GEMINI_API_KEY"))


def generate_text(
    prompt: str,
    *,
    max_output_tokens: int,
    timeout_s: float,
    image: Optional[tuple[bytes, str]] = None,
    json_schema: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """
    Gemini에 프롬프트(+선택적 이미지)를 보내고 응답 텍스트를 돌려준다.

    Args:
        image: (원본 바이트, mime_type). 원격 URL은 호출부가 미리 받아서 넘긴다 —
            Gemini는 임의의 https 이미지 주소를 대신 받아주지 않는다.
        json_schema: 주면 JSON 응답을 스키마로 강제한다.

    Returns:
        응답 텍스트. 키 미설정을 포함한 모든 실패에서 None.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image is not None:
            data, mime_type = image
            content.insert(
                0,
                {
                    "type": "image",
                    "data": base64.standard_b64encode(data).decode("ascii"),
                    "mime_type": mime_type,
                },
            )

        request: dict[str, Any] = {
            "model": model_name(),
            "input": content,
            "generation_config": {
                "max_output_tokens": max_output_tokens,
                "thinking_level": THINKING_LEVEL,
            },
        }
        if json_schema is not None:
            request["response_format"] = {
                "type": "text",
                "mime_type": "application/json",
                "schema_": json_schema,
            }

        client = genai.Client(api_key=api_key)
        interaction = client.interactions.create(timeout=timeout_s, **request)
        text = (interaction.output_text or "").strip()
        if not text:
            logger.warning("Gemini 응답이 비어 있다 (model=%s, status=%s)", model_name(), interaction.status)
            return None
        return text
    except Exception:
        logger.warning("Gemini 호출 실패 — 폴백으로 처리한다 (model=%s)", model_name(), exc_info=True)
        return None
