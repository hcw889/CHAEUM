"""
국토교통부_건축HUB_건축물대장정보 서비스 클라이언트.

이 API가 주는 것은 "건물 제원"이다. 역시 공실 여부는 없다. 우리가 쓰는 두 가지:

  표제부   getBrTitleInfo   — 사용승인일, 연면적/건축면적, 지상/지하 층수,
                              주용도, 구조, 승강기 대수
  층별개요 getBrFlrOulnInfo — 층별 용도명과 전용면적

층별개요의 "상업용도 층"과 상가정보의 "그 층에 등록된 점포"를 맞춰 보면,
대장에는 근린생활시설로 등재돼 있는데 영업 점포가 0건인 층이 나온다.
그 층이 공실 후보다 (vacancy_estimator.py).

조회 파라미터는 지번 기반이다: sigunguCd(5) + bjdongCd(5) + platGbCd + bun(4) + ji(4).
이 값들은 상가정보 응답의 ldongCd / plotSctCd / lnbrMnnm / lnbrSlno에서 그대로 나온다
(sangga_api.building_register_params).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from app.services import datagokr

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://apis.data.go.kr/1613000/BldRgstHubService"
# 건축HUB 이전 세대 서비스. 개발계정이 구 서비스만 승인된 경우를 위한 폴백.
FALLBACK_BASE_URL = "http://apis.data.go.kr/1613000/BldRgstService_v2"

TITLE_OP = "getBrTitleInfo"
FLOOR_OP = "getBrFlrOulnInfo"

# 건축물대장 주용도/층용도 문자열 중 "상가로 쓸 수 있는 용도".
# 대장 용도명은 "제2종근린생활시설", "판매시설", "근린생활시설(소매점)" 등으로
# 표기가 흔들리므로 부분 문자열로 본다.
COMMERCIAL_PURPOSE_KEYWORDS = (
    "근린생활시설",
    "판매시설",
    "판매및영업시설",
    "위락시설",
    "숙박시설",
    "업무시설",
    "운동시설",
    "문화및집회시설",
    "교육연구시설",
    "소매점",
    "일반음식점",
    "휴게음식점",
    "상점",
)

# 공실 후보에서 제외할 용도. 주거/주차/기계실은 비어 있어도 "상가 공실"이 아니다.
NON_LEASABLE_PURPOSE_KEYWORDS = (
    "주차장",
    "기계실",
    "전기실",
    "계단실",
    "승강기",
    "물탱크",
    "공용",
    "다가구주택",
    "다세대주택",
    "아파트",
    "단독주택",
    "연립주택",
    "기숙사",
    "창고",
    "발전시설",
    "정화조",
    "피난",
)


def base_url() -> str:
    return (os.environ.get("BLDRGST_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def _endpoint(operation: str, base: Optional[str] = None) -> str:
    root = (base or base_url()).rstrip("/")
    return root + "/" + operation


def _fetch(operation: str, params: dict[str, str], rows: int) -> list[dict[str, Any]]:
    payload = datagokr.get_json(
        _endpoint(operation),
        {**params, "_type": "json", "numOfRows": rows, "pageNo": 1},
    )
    datagokr.check_header(payload)
    return datagokr.extract_items(payload)


def fetch_title(params: dict[str, str]) -> Optional[dict[str, Any]]:
    """
    표제부 1건. 같은 지번에 동이 여러 개면 연면적이 가장 큰 동을 대표로 쓴다
    (상가가 들어 있을 가능성이 가장 높은 동).
    """
    items = _fetch(TITLE_OP, params, rows=50)
    if not items:
        return None
    return max(items, key=lambda item: _float(item.get("totArea")) or 0.0)


def fetch_floors(params: dict[str, str]) -> list[dict[str, Any]]:
    """층별개요 전체. 같은 지번의 모든 동이 섞여 들어온다."""
    return _fetch(FLOOR_OP, params, rows=200)


def probe_base_url(params: dict[str, str]) -> Optional[str]:
    """
    표제부가 열리는 base_url을 찾아 고정한다 (건축HUB -> 구 서비스 순).
    사전 수집 스크립트가 첫 건물에서 한 번 호출한다.
    """
    for base in (DEFAULT_BASE_URL, FALLBACK_BASE_URL):
        try:
            payload = datagokr.get_json(
                _endpoint(TITLE_OP, base),
                {**params, "_type": "json", "numOfRows": 1, "pageNo": 1},
            )
            datagokr.check_header(payload)
        except Exception as exc:
            logger.info("건축물대장 base_url %s 확인 실패: %s", base, exc)
            continue
        os.environ["BLDRGST_API_BASE_URL"] = base
        return base
    return None


# --- 필드 해석 ----------------------------------------------------------------


def _float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    number = _float(value)
    return int(number) if number is not None else None


def _purpose_text(item: dict[str, Any]) -> str:
    """주용도 + 기타용도를 합친 문자열. 용도 판정은 항상 이 합본으로 한다."""
    parts = [
        str(item.get("mainPurpsCdNm") or ""),
        str(item.get("etcPurps") or ""),
    ]
    return " ".join(part.strip() for part in parts if part.strip())


def is_commercial_purpose(purpose: str) -> bool:
    return any(keyword in purpose for keyword in COMMERCIAL_PURPOSE_KEYWORDS)


def is_non_leasable_purpose(purpose: str) -> bool:
    return any(keyword in purpose for keyword in NON_LEASABLE_PURPOSE_KEYWORDS)


def approval_year(item: dict[str, Any]) -> Optional[int]:
    """
    사용승인일(useAprDay, YYYYMMDD)에서 연도. 비어 있으면 허가일(pmsDay)로 폴백한다.
    리모델링/증축 이력은 대장에 별도로 안 드러나므로 최초 사용승인 기준이다.
    """
    for field in ("useAprDay", "pmsDay", "stcnsDay"):
        raw = str(item.get(field) or "").strip()
        match = re.match(r"^(\d{4})", raw)
        if match:
            year = int(match.group(1))
            if 1900 <= year <= 2100:
                return year
    return None


def parse_title(item: dict[str, Any]) -> dict[str, Any]:
    """표제부 레코드를 우리 스키마로."""
    purpose = _purpose_text(item)
    return {
        "mgm_bldrgst_pk": str(item.get("mgmBldrgstPk") or "").strip(),
        "bld_name": str(item.get("bldNm") or "").strip(),
        "dong_name": str(item.get("dongNm") or "").strip(),
        "plat_address": str(item.get("platPlc") or "").strip(),
        "road_address": str(item.get("newPlatPlc") or "").strip(),
        "approval_year": approval_year(item),
        "total_area": _float(item.get("totArea")),
        "arch_area": _float(item.get("archArea")),
        "ground_floors": _int(item.get("grndFlrCnt")) or 0,
        "underground_floors": _int(item.get("ugrndFlrCnt")) or 0,
        "height": _float(item.get("heit")),
        "structure": str(item.get("strctCdNm") or "").strip(),
        "main_purpose": purpose,
        "elevators": (_int(item.get("rideUseElvtCnt")) or 0) + (_int(item.get("emgenUseElvtCnt")) or 0),
        "is_commercial": is_commercial_purpose(purpose),
    }


def floor_sign(item: dict[str, Any]) -> Optional[int]:
    """
    층별개요 레코드의 층수를 지상 양수 / 지하 음수 정수로.
    flrGbCdNm이 "지하"면 음수, flrNo는 절대값으로 들어온다.
    """
    number = _int(item.get("flrNo"))
    if number is None:
        # flrNoNm("지하1층", "1층", "옥탑1층")에서 파싱 폴백
        name = str(item.get("flrNoNm") or "")
        digits = "".join(ch for ch in name if ch.isdigit())
        if not digits:
            return None
        number = int(digits)
        if "지하" in name:
            return -number
        return number

    gb = str(item.get("flrGbCdNm") or "")
    if "지하" in gb:
        return -abs(number)
    return number


def parse_floors(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    층별개요를 층 단위로 정리한다.

    같은 층에 용도가 여러 줄로 쪼개져 오는 경우(예: 1층 소매점 / 1층 일반음식점)가
    있어 층 번호로 합치고 면적은 더한다. 용도명은 모두 이어 붙여 판정에 쓴다.
    """
    merged: dict[int, dict[str, Any]] = {}

    for item in items:
        floor = floor_sign(item)
        if floor is None:
            continue
        purpose = _purpose_text(item)
        area = _float(item.get("area")) or 0.0

        entry = merged.get(floor)
        if entry is None:
            entry = {
                "floor": floor,
                "floor_label": str(item.get("flrNoNm") or "").strip(),
                "purposes": [],
                "area": 0.0,
                "structure": str(item.get("strctCdNm") or "").strip(),
            }
            merged[floor] = entry

        if purpose and purpose not in entry["purposes"]:
            entry["purposes"].append(purpose)
        entry["area"] += area

    floors = []
    for entry in merged.values():
        purpose_text = " / ".join(entry["purposes"])
        floors.append(
            {
                "floor": entry["floor"],
                "floor_label": entry["floor_label"] or _default_floor_label(entry["floor"]),
                "purpose": purpose_text,
                "area": round(entry["area"], 2),
                "structure": entry["structure"],
                "is_commercial": is_commercial_purpose(purpose_text),
                "is_non_leasable": is_non_leasable_purpose(purpose_text),
            }
        )
    floors.sort(key=lambda entry: entry["floor"])
    return floors


def _default_floor_label(floor: int) -> str:
    if floor < 0:
        return "지하{}층".format(abs(floor))
    return "{}층".format(floor)


def fetch_building(params: dict[str, str]) -> Optional[dict[str, Any]]:
    """
    표제부 + 층별개요를 한 번에. 표제부가 없으면 None (대장 미등재 지번).
    호출부(사전 수집 스크립트)가 예외를 잡아 건물 단위로 건너뛴다.
    """
    title_item = fetch_title(params)
    if title_item is None:
        return None

    title = parse_title(title_item)
    try:
        floors = parse_floors(fetch_floors(params))
    except datagokr.DataGoKrError as exc:
        # 층별개요만 실패하면 표제부 정보로라도 진행한다 (공실 판정은 건너뜀).
        logger.info("층별개요 조회 실패 %s: %s", params, exc)
        floors = []

    return {"title": title, "floors": floors, "register_params": dict(params)}
