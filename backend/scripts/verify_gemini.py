"""
Gemini 연결 확인 스크립트.

에이전트 5·6은 실패해도 폴백값을 돌려주도록 설계돼 있어서, 서버를 띄워 화면만 봐서는
"LLM이 실제로 돌았는지"와 "조용히 폴백했는지"를 구분할 수 없다. 이 스크립트는 폴백을
거치지 않고 llm.generate_text를 직접 불러, 실패하면 원인을 그대로 드러낸다.

    cd backend && .venv/Scripts/python scripts/verify_gemini.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 윈도우 기본 콘솔(cp949)에서 한글·em-dash가 UnicodeEncodeError로 죽는다.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.services import llm, space_vision_agent  # noqa: E402

# llm.py는 실패를 warning으로만 남기고 None을 돌려준다. 원인을 보려면 로그를 켜야 한다.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SAMPLE_PHOTO = "https://picsum.photos/seed/onit-storefront-b1/800/600"


def main() -> int:
    if not llm.is_configured():
        print("FAIL  GEMINI_API_KEY가 없다. backend/.env에 채워라.")
        return 1
    print(f"model = {llm.model_name()}")

    print("\n[1/2] 텍스트 — 추천 사유 생성 경로")
    text = llm.generate_text(
        "전주 원도심 상가에 카페를 여는 사람에게 건넬 한 문장을 한국어로만 써라.",
        max_output_tokens=1024,
        timeout_s=15.0,
    )
    if not text:
        print("FAIL  응답 없음 (위 warning 로그 참고)")
        return 1
    print(f"OK    {text}")

    print("\n[2/2] 이미지 — Space Vision 경로")
    image = space_vision_agent._load_image(SAMPLE_PHOTO)
    if image is None:
        print(f"FAIL  샘플 이미지를 못 받았다: {SAMPLE_PHOTO}")
        return 1
    print(f"      이미지 {len(image[0]):,}바이트 / {image[1]}")

    features = space_vision_agent.analyze_storefront_features(SAMPLE_PHOTO)
    if features == space_vision_agent.FALLBACK_FEATURES:
        print("FAIL  폴백값이 그대로 나왔다 — 호출이 실패했거나 응답이 비었다")
        return 1
    print("OK    " + json.dumps(features, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
