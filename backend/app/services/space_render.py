"""
채움(Chaeum) 공간 시각화 — 공실 사진을 팝업/업종 컨셉이 적용된 모습으로 변환한다.

팝업 브랜드 담당자가 "이 공간이 내가 기획한 팝업을 구현하기에 적당한가"를
입지 탐색 단계에서 눈으로 확인하는 것이 목적이며, 매칭 flow(/api/match)의
스코어링과는 완전히 분리된 별도 기능이다. (매칭 재사용 원칙: match.py 무변경)

실행 모드는 환경에 따라 3단계로 폴백한다.

    hf_api : HF_TOKEN 있음 -> HuggingFace Inference Providers의 image-to-image.
             호스팅 API 스펙에 mask_image 파라미터가 없으므로 마스크 없이
             프롬프트 기반 편집만 수행한다 (FLUX.1-Kontext 계열).
    local  : CHAEUM_RENDER_MODE=local -> 로컬 diffusers AutoPipelineForInpainting.
             https://huggingface.co/docs/diffusers/using-diffusers/inpaint 의
             마스크 인페인팅 그대로. GPU 필요.
    mock   : 그 외 / 모든 예외 -> Pillow 기반 플레이스홀더.

explanation_agent(matching_agents.py)와 동일하게, 어떤 실패에서도 예외를 밖으로
던지지 않고 mock으로 떨어뜨린다. 데모 중 화면이 죽지 않는 것이 최우선이다.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GENERATED_DIR = Path(__file__).resolve().parent.parent / "data" / "generated"

# 호스팅 API용 기본 모델. image-to-image(편집) 태스크이며 마스크를 지원하지 않는다.
DEFAULT_HF_MODEL = "black-forest-labs/FLUX.1-Kontext-dev"
# 로컬 diffusers용 기본 모델. 마스크 인페인팅 전용 체크포인트.
DEFAULT_LOCAL_MODEL = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"

MAX_SIDE = 1024
DEFAULT_STRENGTH = 0.65
NEGATIVE_PROMPT = (
    "blurry, distorted architecture, deformed structure, warped walls, "
    "text artifacts, watermark, lowres, oversaturated"
)

# 입점 희망 기간별 연출 방향. 단기(팝업)는 가설 집기, 장기는 고정 인테리어.
OCCUPANCY_STYLE = {
    "단기": "modular pop-up fixtures, temporary display units, removable signage, event-like staging",
    "장기": "permanent built-in interior, fixed shelving and counters, durable finishes",
}
# 매칭 wizard의 commercial_style_pref 값과 동일한 키를 쓴다 (lib/types.ts STYLE_OPTIONS).
COMMERCIAL_STYLE = {
    "유동인구중심": "bright storefront facing heavy foot traffic, eye-catching street-level display",
    "조용한골목상권": "calm alleyway storefront, warm and intimate lighting, cozy scale",
    "학생상권": "casual and youthful atmosphere, approachable styling",
}

_local_pipeline = None  # 로컬 모드에서 파이프라인 재사용 (로딩에 수십 초 걸린다)


def _token() -> Optional[str]:
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")


def resolve_mode() -> str:
    """CHAEUM_RENDER_MODE로 강제 지정 가능. 미지정이면 토큰 유무로 자동 결정."""
    forced = (os.environ.get("CHAEUM_RENDER_MODE") or "").strip().lower()
    if forced in {"hf_api", "local", "mock"}:
        return forced
    return "hf_api" if _token() else "mock"


def build_prompt(
    concept: str,
    commercial_style_pref: Optional[str] = None,
    occupancy_term: Optional[str] = None,
    building: Optional[dict] = None,
) -> str:
    """
    wizard 입력(컨셉/상권 분위기/입점 기간)과 건물 메타를 하나의 편집 프롬프트로 합성한다.

    occupancy_term은 매칭 스코어링에는 반영하지 않기로 한 값이지만, 이미지 연출
    방향에는 반영한다 — 단기 팝업과 장기 임대는 집기 구성 자체가 다르기 때문이다.
    """
    parts = [
        f"interior of a small Korean street-level retail space redesigned as: {concept}",
        "renovated, clean, professionally styled, realistic architectural photography",
    ]

    style = COMMERCIAL_STYLE.get(commercial_style_pref or "")
    if style:
        parts.append(style)

    term = OCCUPANCY_STYLE.get(occupancy_term or "")
    if term:
        parts.append(term)

    if building:
        parts.append(f"{building.get('area_pyeong', 15)} pyeong, floor {building.get('floor', 1)}")
        lighting = (building.get("diagnosis") or {}).get("lighting_score")
        if isinstance(lighting, (int, float)):
            # 채광 점수가 낮은 매물은 조명 계획이 중요하다는 점을 이미지에도 반영한다.
            parts.append("bright natural daylight" if lighting >= 70 else "warm supplemental interior lighting")

    parts.append("keep the original room geometry, window positions and ceiling height unchanged")
    return ", ".join(parts)


# --- 이미지 유틸 -------------------------------------------------------------


def decode_data_url(data_url: str):
    """data:image/png;base64,... 또는 순수 base64 문자열을 PIL Image로 변환."""
    from PIL import Image

    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    return Image.open(io.BytesIO(base64.b64decode(raw))).convert("RGB")


def _to_data_url(image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _fit(image):
    """긴 변을 MAX_SIDE 이하로 줄이고 8의 배수로 정렬 (diffusion 모델 입력 요건)."""
    w, h = image.size
    scale = min(MAX_SIDE / max(w, h), 1.0)
    w = max(8, int(w * scale) // 8 * 8)
    h = max(8, int(h * scale) // 8 * 8)
    return image.resize((w, h))


def _placeholder_source(building: Optional[dict]):
    """사진 업로드가 없을 때 쓰는 기본 이미지 — 건물 thumbnail_color 기반 단색 배경."""
    from PIL import Image

    color = (building or {}).get("thumbnail_color", "#D8CFC4")
    return Image.new("RGB", (768, 576), color)


def auto_mask(image):
    """
    마스크 미제공 시 자동 생성하는 기본 마스크 (local 모드 전용).
    흰색 = 다시 그릴 영역. 천장/바닥 가장자리를 남기고 벽면 중앙부만 교체해
    방의 구조가 무너지지 않게 한다.
    """
    from PIL import Image, ImageDraw

    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle(
        [int(w * 0.08), int(h * 0.12), int(w * 0.92), int(h * 0.88)], fill=255
    )
    return mask


# --- 렌더 모드별 구현 ---------------------------------------------------------


def _render_hf_api(image, mask, prompt: str, strength: float):
    """
    HuggingFace Inference Providers image-to-image.

    주의: 호스팅 image-to-image 스펙에는 mask_image 파라미터가 없다. 따라서 mask가
    주어져도 무시되며 프롬프트 기반 편집으로만 동작한다. 마스크 인페인팅이 꼭
    필요하면 local 모드를 쓴다.
    """
    from huggingface_hub import InferenceClient

    model = os.environ.get("CHAEUM_HF_MODEL", DEFAULT_HF_MODEL)
    client = InferenceClient(api_key=_token(), timeout=120)
    result = client.image_to_image(
        image,
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        model=model,
    )
    return result, model


def _render_local(image, mask, prompt: str, strength: float):
    """로컬 diffusers 마스크 인페인팅. diffusers 문서의 AutoPipelineForInpainting 그대로."""
    global _local_pipeline

    import torch
    from diffusers import AutoPipelineForInpainting

    model = os.environ.get("CHAEUM_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
    if _local_pipeline is None:
        _local_pipeline = AutoPipelineForInpainting.from_pretrained(
            model, torch_dtype=torch.float16, variant="fp16"
        )
        _local_pipeline.enable_model_cpu_offload()

    if mask is None:
        mask = auto_mask(image)
    # 마스크 경계를 흐려 원본과의 이음새를 자연스럽게 만든다 (문서의 mask blur).
    mask = _local_pipeline.mask_processor.blur(mask, blur_factor=24)

    result = _local_pipeline(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        image=image,
        mask_image=mask,
        strength=strength,
        guidance_scale=7.5,
    ).images[0]
    return result, model


def _render_mock(image, mask, prompt: str, strength: float):
    """
    Pillow만으로 만드는 "리뉴얼 후" 느낌의 플레이스홀더.
    실제 생성 결과가 아니라는 점은 응답의 mode='mock'로 UI에 표시된다.
    """
    from PIL import Image, ImageEnhance, ImageFilter

    out = ImageEnhance.Brightness(image).enhance(1.0 + 0.25 * strength)
    out = ImageEnhance.Color(out).enhance(1.0 + 0.5 * strength)
    out = ImageEnhance.Contrast(out).enhance(1.08)
    out = out.filter(ImageFilter.SMOOTH_MORE)
    warm = Image.new("RGB", out.size, "#FFD9A0")  # 따뜻한 조명 톤 오버레이
    return Image.blend(out, warm, 0.12 * strength), "mock-placeholder"


_RENDERERS = {"hf_api": _render_hf_api, "local": _render_local, "mock": _render_mock}


# --- 진입점 ------------------------------------------------------------------


def render_space(
    *,
    concept: str,
    photo_data_url: Optional[str] = None,
    mask_data_url: Optional[str] = None,
    commercial_style_pref: Optional[str] = None,
    occupancy_term: Optional[str] = None,
    strength: float = DEFAULT_STRENGTH,
    building: Optional[dict] = None,
) -> dict:
    """
    Returns:
        {
            "mode": "hf_api" | "local" | "mock",
            "model": str,
            "prompt": str,
            "before_image": data URL,
            "after_image": data URL,
            "note": str | None,   # 폴백/안내 사유
        }
    """
    prompt = build_prompt(concept, commercial_style_pref, occupancy_term, building)
    mode = resolve_mode()
    note = None

    try:
        source = decode_data_url(photo_data_url) if photo_data_url else _placeholder_source(building)
        mask = decode_data_url(mask_data_url).convert("L") if mask_data_url else None
    except Exception as exc:  # 잘못된 base64 / 손상된 이미지
        logger.warning("space_render: 입력 이미지 디코딩 실패 (%s)", exc)
        source = _placeholder_source(building)
        mask = None
        note = "업로드한 이미지를 읽지 못해 기본 이미지로 대체했습니다."

    source = _fit(source)
    if mask is not None:
        mask = mask.resize(source.size)

    if photo_data_url is None and note is None:
        note = "사진을 업로드하면 실제 공간 사진을 기반으로 생성됩니다."

    cache_key = _cache_key(mode, prompt, strength, source)
    cached = _load_cached(cache_key)
    if cached is not None:
        return {
            "mode": mode,
            "model": "cached",
            "prompt": prompt,
            "before_image": _to_data_url(source),
            "after_image": cached,
            "note": note,
        }

    try:
        result, model = _RENDERERS[mode](source, mask, prompt, strength)
    except Exception as exc:
        # 토큰 만료, 모델 cold start, 네트워크 차단, torch/diffusers 미설치 등
        # 모든 실패를 흡수하고 mock으로 떨어뜨린다.
        logger.warning("space_render: %s 모드 실패 -> mock 폴백 (%s)", mode, exc)
        note = f"이미지 생성에 실패해 미리보기로 대체했습니다. ({type(exc).__name__})"
        mode = "mock"
        result, model = _render_mock(source, mask, prompt, strength)

    if mode != "mock":
        _save_cached(cache_key, result)

    return {
        "mode": mode,
        "model": model,
        "prompt": prompt,
        "before_image": _to_data_url(source),
        "after_image": _to_data_url(result),
        "note": note,
    }


# --- 캐시 --------------------------------------------------------------------
# 발표 중 같은 매물/컨셉을 반복 시연할 때 재생성 대기(수십 초)를 없앤다.


def _cache_key(mode: str, prompt: str, strength: float, source) -> str:
    buf = io.BytesIO()
    source.save(buf, format="PNG")
    digest = hashlib.sha256()
    digest.update(f"{mode}|{prompt}|{strength:.2f}|".encode())
    digest.update(buf.getvalue())
    return digest.hexdigest()[:24]


def _load_cached(key: str) -> Optional[str]:
    path = GENERATED_DIR / f"{key}.png"
    if not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _save_cached(key: str, image) -> None:
    try:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        image.save(GENERATED_DIR / f"{key}.png", format="PNG")
    except Exception as exc:
        logger.warning("space_render: 캐시 저장 실패 (%s)", exc)
