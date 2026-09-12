"""
사람이 전사한 실측 유동인구 (app/data/footfall_measured.json).

SK 유동인구 상품은 별도 계약이라 연결하지 않는다. 대신 소상공인시장진흥공단
상권정보시스템(sg.sbiz.or.kr) 상권분석 보고서에 보이는 값을 사람이 구역마다 옮겨 적고,
이 모듈이 그 값을 화면이 쓰는 24시간 배열로 펼친다. 전사 규격은 같은 폴더의
footfall_measured.README.md 참고.

보고서는 시간대를 6개 구간(00-06, 06-11, 11-14, 14-17, 17-21, 21-24) 비율로만 주므로
구간 안의 분포는 구역 profile 곡선(sk_footfall.PROFILES)의 모양을 빌린다.
구간 합계는 전사한 비율과 정확히 맞고, 곡선은 구간 안에서만 모양을 준다.

전사가 끝난 구역만 실측으로 나가고, 비어 있거나 잘못 적힌 구역은 기존 mock으로 남는다
(잘못 적힌 항목은 서버 로그와 /api/footfall/status의 measured.errors에 사유가 뜬다).

검사만 하려면:  cd backend && python -m app.services.footfall_measured
"""

from __future__ import annotations

import json
import logging
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "footfall_measured.json"

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")
WEEKEND = ("sat", "sun")
PCT_TOLERANCE = 2.0  # 보고서 반올림 때문에 합이 정확히 100이 안 나온다
_BAND = re.compile(r"^(\d{1,2})-(\d{1,2})$")


class MeasuredError(ValueError):
    """전사 항목 하나가 규격에 안 맞을 때. 메시지는 사람이 읽고 고칠 수 있게 쓴다."""


def _mtime() -> float:
    try:
        return DATA_PATH.stat().st_mtime
    except OSError:
        return 0.0


@lru_cache(maxsize=4)
def _load(path: Path, mtime: float) -> dict[str, Any]:
    # mtime을 캐시 키로 써서 파일을 고치면 서버 재시작 없이 다음 요청부터 반영된다.
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"areas": {}}
    except ValueError as exc:
        logger.warning("footfall_measured.json 파싱 실패: %s", exc)
        return {"areas": {}, "_parse_error": str(exc)}


def load() -> dict[str, Any]:
    return _load(DATA_PATH, _mtime())


def source_label() -> str:
    return load().get("source_label") or "상권정보시스템 유동인구 (전사)"


def _number(entry: dict, key: str, *, positive: bool = False) -> Optional[float]:
    value = entry.get(key)
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeasuredError(f"{key}: 숫자여야 합니다 (현재 {value!r})")
    if positive and value <= 0:
        raise MeasuredError(f"{key}: 0보다 커야 합니다 (현재 {value})")
    return float(value)


def _bands(entry: dict) -> Optional[list[tuple[int, int, float]]]:
    """time_bands_pct → [(시작시, 끝시, 비율)]. 0~24시를 빈틈·겹침 없이 덮어야 한다."""
    raw = entry.get("time_bands_pct")
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw:
        raise MeasuredError("time_bands_pct: {\"06-11\": 18.2, ...} 형태의 객체여야 합니다")
    bands = []
    for key, value in raw.items():
        match = _BAND.match(str(key).strip())
        if not match:
            raise MeasuredError(f"time_bands_pct: 구간 키는 'HH-HH' 형식이어야 합니다 (현재 {key!r})")
        start, end = int(match.group(1)), int(match.group(2))
        if not (0 <= start < end <= 24):
            raise MeasuredError(f"time_bands_pct: 구간 {key!r}는 0 ≤ 시작 < 끝 ≤ 24 이어야 합니다")
        if value is None or value == "":
            return None  # 아직 다 안 적었다 → 미전사로 본다
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise MeasuredError(f"time_bands_pct[{key}]: 0 이상의 숫자여야 합니다 (현재 {value!r})")
        bands.append((start, end, float(value)))
    bands.sort()
    cursor = 0
    for start, end, _ in bands:
        if start != cursor:
            raise MeasuredError(f"time_bands_pct: {cursor:02d}시~{start:02d}시 구간이 비었거나 겹칩니다")
        cursor = end
    if cursor != 24:
        raise MeasuredError(f"time_bands_pct: 마지막 구간이 24시까지 와야 합니다 (현재 {cursor}시)")
    total = sum(pct for _, _, pct in bands)
    if abs(total - 100.0) > PCT_TOLERANCE:
        raise MeasuredError(f"time_bands_pct: 비율 합이 100이어야 합니다 (현재 {total:.1f})")
    return bands


def _day_factors(entry: dict) -> tuple[float, float]:
    """
    요일별 비율(월~일, 합 100) → (평일 배수, 주말 배수).
    일평균 × 배수 = 해당 요일 유형의 하루 유동인구. 요일 비율이 없으면 둘 다 1.
    """
    raw = entry.get("weekday_pct")
    if raw is None or (isinstance(raw, dict) and all(v in (None, "") for v in raw.values())):
        return 1.0, 1.0
    if not isinstance(raw, dict):
        raise MeasuredError("weekday_pct: {\"mon\": 13.2, ..., \"sun\": 14.4} 형태의 객체여야 합니다")
    missing = [day for day in WEEKDAYS + WEEKEND if raw.get(day) in (None, "")]
    if missing:
        raise MeasuredError(f"weekday_pct: {', '.join(missing)} 값이 비어 있습니다 (7개 요일을 모두 적거나 전부 비우세요)")
    values = {}
    for day in WEEKDAYS + WEEKEND:
        value = raw[day]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise MeasuredError(f"weekday_pct[{day}]: 0 이상의 숫자여야 합니다 (현재 {value!r})")
        values[day] = float(value)
    total = sum(values.values())
    if abs(total - 100.0) > PCT_TOLERANCE:
        raise MeasuredError(f"weekday_pct: 비율 합이 100이어야 합니다 (현재 {total:.1f})")
    # 7일 평균 비율은 100/7. 평일 5일 평균 비율이 그보다 크면 평일이 더 붐빈다.
    weekday = sum(values[d] for d in WEEKDAYS) / len(WEEKDAYS) * 7 / 100
    weekend = sum(values[d] for d in WEEKEND) / len(WEEKEND) * 7 / 100
    return weekday, weekend


def _expand(daily: float, bands: list[tuple[int, int, float]], curve: list[float]) -> list[int]:
    """구간 비율을 24칸으로 펼친다. 구간 합은 전사값 그대로, 구간 안 모양은 profile 곡선."""
    hourly = [0.0] * 24
    for start, end, pct in bands:
        weights = curve[start:end]
        if sum(weights) <= 0:
            weights = [1.0] * (end - start)
        weight_sum = sum(weights)
        band_total = daily * pct / 100
        for offset, hour in enumerate(range(start, end)):
            hourly[hour] = band_total * weights[offset] / weight_sum
    return [int(round(v)) for v in hourly]


def parse_entry(entry: dict, curve: list[float]) -> Optional[dict[str, Any]]:
    """
    전사 항목 하나를 해석한다.
    None = 아직 안 적음(정상), dict = 실측, MeasuredError = 잘못 적음.
    """
    if not isinstance(entry, dict):
        raise MeasuredError("구역 항목은 객체여야 합니다")
    daily = _number(entry, "daily_average", positive=True)
    hourly_raw = entry.get("hourly")
    bands = _bands(entry)

    if hourly_raw not in (None, []):
        # 24칸을 직접 구한 경우 (드물다). 이 값이 있으면 구간 비율보다 우선한다.
        if not isinstance(hourly_raw, list) or len(hourly_raw) != 24:
            raise MeasuredError("hourly: 0시~23시 24개 숫자여야 합니다")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 for v in hourly_raw):
            raise MeasuredError("hourly: 0 이상의 숫자 24개여야 합니다")
        base = [float(v) for v in hourly_raw]
        if daily is not None and sum(base) > 0:
            # daily_average도 적었으면 24칸의 모양만 쓰고 합계는 일평균에 맞춘다.
            base = [v * daily / sum(base) for v in base]
    elif daily is None or bands is None:
        # 일평균이나 시간대 비율 중 하나라도 아직 비어 있으면 '전사 중'으로 보고 mock으로 둔다.
        return None
    else:
        base = None

    weekday_factor, weekend_factor = _day_factors(entry)
    result = {}
    for day_type, factor in (("weekday", weekday_factor), ("weekend", weekend_factor)):
        if base is not None:
            result[day_type] = [int(round(v * factor)) for v in base]
        else:
            result[day_type] = _expand(daily * factor, bands, curve)

    month = entry.get("reference_month")
    if month is not None and not re.match(r"^\d{4}-\d{2}$", str(month)):
        raise MeasuredError(f"reference_month: 'YYYY-MM' 형식이어야 합니다 (현재 {month!r})")
    return {
        "hourly": result,
        "reference_month": month,
        "collected_at": entry.get("collected_at"),
        "sbiz_area": entry.get("sbiz_area"),
    }


def coverage(areas: list[dict], profiles: dict[str, dict]) -> dict[str, Any]:
    """/api/footfall/status와 CLI가 쓰는 전사 진행 현황."""
    data = load()
    entries = data.get("areas") or {}
    measured, missing, errors = [], [], {}
    for area in areas:
        entry = entries.get(area["id"])
        if entry is None:
            missing.append(area["id"])
            continue
        curve = profiles.get(area.get("profile"), next(iter(profiles.values())))["curve"]
        try:
            parsed = parse_entry(entry, curve)
        except MeasuredError as exc:
            errors[area["id"]] = str(exc)
            continue
        (measured if parsed else missing).append(area["id"])
    unknown = sorted(set(entries) - {area["id"] for area in areas})
    result = {
        "file": str(DATA_PATH),
        "measured": measured,
        "missing": missing,
        "errors": errors,
        "unknown_ids": unknown,
    }
    if data.get("_parse_error"):
        result["parse_error"] = data["_parse_error"]
    return result


def area_hourly(area: dict, day_type: str, curve: list[float]) -> Optional[dict[str, Any]]:
    """
    구역 하나의 전사값. 없거나 잘못됐으면 None (호출부가 mock으로 폴백한다).
    반환: {"hourly": [24개], "reference_month": ..., "collected_at": ..., "sbiz_area": ...}
    """
    entry = (load().get("areas") or {}).get(area["id"])
    if entry is None:
        return None
    try:
        parsed = parse_entry(entry, curve)
    except MeasuredError as exc:
        logger.warning("footfall_measured.json [%s] 무시: %s", area["id"], exc)
        return None
    if parsed is None:
        return None
    return {**parsed, "hourly": parsed["hourly"][day_type]}


def _cli() -> int:
    from app.services import sk_footfall

    areas = sk_footfall.load_areas()["areas"]
    report = coverage(areas, sk_footfall.PROFILES)
    names = {area["id"]: area["name"] for area in areas}
    print(f"파일: {report['file']}")
    if report.get("parse_error"):
        print(f"JSON 문법 오류: {report['parse_error']}")
        return 1
    print(f"전사 완료 {len(report['measured'])} / {len(areas)} 구역")
    for area_id in report["measured"]:
        print(f"  ✔ {area_id} ({names[area_id]})")
    if report["missing"]:
        print("아직 비어 있음:")
        for area_id in report["missing"]:
            print(f"  · {area_id} ({names[area_id]})")
    if report["errors"]:
        print("고쳐야 함:")
        for area_id, message in report["errors"].items():
            print(f"  ✘ {area_id} ({names.get(area_id, '?')}): {message}")
    if report["unknown_ids"]:
        print(f"footfall_areas.json에 없는 id (무시됨): {', '.join(report['unknown_ids'])}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(_cli())
