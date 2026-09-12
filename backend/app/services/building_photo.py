"""
매물 사진 조달.

시각화 화면의 사용자는 팝업 브랜드/예비창업자, 즉 "공간을 찾는 쪽"이다. 가보지도
않은 공실의 사진을 그들이 갖고 있을 리 없으므로, 사진은 매물 데이터에 딸려 있어야
한다. 이 모듈이 그 사진을 공급한다.

우선순위:
    1. app/data/photos/{building_id}.{jpg,jpeg,png,webp} — 실제 촬영본이 있으면 그것
    2. 없으면 매물 속성으로 만든 공실 내부 플레이스홀더 (source="placeholder")

실제 사진이 생기면 photos/ 에 파일만 떨궈 넣으면 코드 변경 없이 1번으로 바뀐다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from random import Random
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PHOTO_DIR = DATA_DIR / "photos"
PLACEHOLDER_CACHE_DIR = DATA_DIR / "generated"

SUPPORTED_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
SIZE = (768, 576)


def find_photo_file(building_id: str) -> Optional[Path]:
    for suffix in SUPPORTED_SUFFIXES:
        path = PHOTO_DIR / f"{building_id}{suffix}"
        if path.exists():
            return path
    return None


def find_after_file(building_id: str) -> Optional[Path]:
    """
    시공 후 실제 촬영본 (`{id}.after.{확장자}`).

    실제로 리뉴얼이 끝난 매물은 전/후 사진이 함께 있는 경우가 있다. 생성 모델이
    연결되지 않은 환경에서는 이 사진을 "적용 후"로 보여주는 편이 색보정 미리보기보다
    훨씬 정확하다. 단, 입력한 컨셉과 무관한 고정 이미지이므로 생성 결과로 오인되지
    않도록 별도 모드(demo)로 표시한다 (space_render.py 참고).
    """
    for suffix in SUPPORTED_SUFFIXES:
        path = PHOTO_DIR / f"{building_id}.after{suffix}"
        if path.exists():
            return path
    return None


def load_after_photo(building_id: str):
    """시공 후 사진을 PIL Image로. 없으면 None."""
    from PIL import Image

    path = find_after_file(building_id)
    if path is None:
        return None
    try:
        return Image.open(path).convert("RGB").resize(SIZE)
    except Exception as exc:
        logger.warning("building_photo: %s 읽기 실패 (%s)", path, exc)
        return None


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#D8CFC4").lstrip("#")
    if len(value) != 6:
        value = "D8CFC4"
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _shade(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """factor < 1이면 어둡게, > 1이면 밝게."""
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)  # type: ignore[return-value]


def render_placeholder(building: dict):
    """
    매물 속성으로 공실 내부를 단순 투시도로 그린다.

    단색 배경 대신 바닥/벽/천장/창문 구조를 그리는 이유는 두 가지다.
      - 사람이 보기에 "빈 가게"로 읽혀야 Before/After 비교가 의미를 가진다.
      - diffusion 모델에 넘길 때 구조가 있어야 편집 결과가 공간처럼 나온다.

    진단 점수를 반영한다: 채광 점수는 창문 밝기로, 노후도는 벽 얼룩의 양으로.
    """
    from PIL import Image, ImageDraw, ImageFilter

    w, h = SIZE
    base = _hex_to_rgb(building.get("thumbnail_color", "#D8CFC4"))
    diagnosis = building.get("diagnosis") or {}
    lighting = float(diagnosis.get("lighting_score", 60))
    aging = float(diagnosis.get("aging_score", 50))

    image = Image.new("RGB", (w, h), _shade(base, 0.9))
    draw = ImageDraw.Draw(image)

    # 뒷벽 — 소실점을 화면 중앙보다 살짝 위에 둔다
    bx0, by0, bx1, by1 = int(w * 0.24), int(h * 0.22), int(w * 0.76), int(h * 0.70)

    draw.polygon([(0, 0), (w, 0), (bx1, by0), (bx0, by0)], fill=_shade(base, 1.02))  # 천장
    draw.polygon([(0, h), (w, h), (bx1, by1), (bx0, by1)], fill=_shade(base, 0.62))  # 바닥
    draw.polygon([(0, 0), (bx0, by0), (bx0, by1), (0, h)], fill=_shade(base, 0.78))  # 좌측벽
    draw.polygon([(w, 0), (bx1, by0), (bx1, by1), (w, h)], fill=_shade(base, 0.86))  # 우측벽
    draw.rectangle([bx0, by0, bx1, by1], fill=_shade(base, 0.94))  # 뒷벽

    # 좌측벽 창문 — 채광 점수가 높을수록 밝다
    glow = 0.95 + (lighting / 100) * 0.75
    draw.polygon(
        [
            (int(w * 0.03), int(h * 0.20)),
            (int(w * 0.20), int(h * 0.29)),
            (int(w * 0.20), int(h * 0.67)),
            (int(w * 0.03), int(h * 0.76)),
        ],
        fill=_shade((245, 242, 232), glow),
    )

    # 뒷벽 하단 걸레받이 + 바닥 경계선으로 공간감을 준다
    draw.line([(bx0, by1), (bx1, by1)], fill=_shade(base, 0.45), width=3)
    draw.line([(0, h), (bx0, by1)], fill=_shade(base, 0.5), width=2)
    draw.line([(w, h), (bx1, by1)], fill=_shade(base, 0.5), width=2)

    # 노후도 — 점수가 낮을수록(=노후할수록) 벽 얼룩이 많아진다
    rng = Random(building.get("id", "b0"))
    for _ in range(int((100 - aging) / 4)):
        sx = rng.randint(bx0, bx1)
        sy = rng.randint(by0, by1)
        radius = rng.randint(8, 28)
        draw.ellipse([sx, sy, sx + radius, sy + radius // 2], fill=_shade(base, rng.uniform(0.80, 0.90)))

    return image.filter(ImageFilter.GaussianBlur(1.2))


def load_photo(building: dict) -> tuple[object, str]:
    """
    Returns:
        (PIL.Image, source) — source는 "file"(실제 촬영본) 또는 "placeholder".
    """
    from PIL import Image

    building_id = building.get("id", "unknown")

    path = find_photo_file(building_id)
    if path is not None:
        try:
            return Image.open(path).convert("RGB").resize(SIZE), "file"
        except Exception as exc:
            logger.warning("building_photo: %s 읽기 실패, 플레이스홀더로 대체 (%s)", path, exc)

    # 플레이스홀더는 매물 속성만으로 결정되므로 한 번 그린 뒤 캐시한다.
    cache_path = PLACEHOLDER_CACHE_DIR / f"placeholder-{building_id}.png"
    if cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGB"), "placeholder"
        except Exception:
            pass  # 캐시가 깨졌으면 다시 그린다

    image = render_placeholder(building)
    try:
        PLACEHOLDER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        image.save(cache_path, format="PNG")
    except Exception as exc:
        logger.warning("building_photo: 플레이스홀더 캐시 저장 실패 (%s)", exc)

    return image, "placeholder"
