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

# 이 모듈의 모든 호출은 건축물대장 API 전용 키를 쓴다 (상가정보와 키가 다르다).
# 전용 키가 없으면 datagokr가 공통 키로 폴백한다.
KEY_ENV = datagokr.BLDRGST_KEY_ENV

DEFAULT_BASE_URL = "http://apis.data.go.kr/1613000/BldRgstHubService"
# 건축HUB 이전 세대 서비스. 개발계정이 구 서비스만 승인된 경우를 위한 폴백.
FALLBACK_BASE_URL = "http://apis.data.go.kr/1613000/BldRgstService_v2"

TITLE_OP = "getBrTitleInfo"
FLOOR_OP = "getBrFlrOulnInfo"

# 건축물대장 주용도/층용도 문자열 중 "상가로 쓸 수 있는 용도".
# 대장 용도명은 "제2종근린생활시설", "판매시설", "근린생활시설(소매점)", "소매점 점포"
# 등으로 표기가 흔들리므로 부분 문자열로 본다.
#
# 범위를 근린생활시설·판매시설 계열로 좁혀 둔다. 업무시설/운동시설/교육연구시설/
# 숙박시설까지 넣으면 "골프연습장 236평", "사무실 전체 층"처럼 카페·편의점 창업자가
# 임차할 상가가 아닌 층이 공실 후보로 올라온다 (실수집에서 확인). 소규모 학원·
# 스터디카페·의원은 대장에도 제2종근린생활시설로 등재되므로 여기서 걸러지지 않는다.
COMMERCIAL_PURPOSE_KEYWORDS = (
    "근린생활시설",
    "판매시설",
    "판매및영업시설",
    "소매점",
    "일반음식점",
    "휴게음식점",
    "상점",
    "점포",
)

# 공실 후보에서 제외할 용도. 주거/주차/기계실은 비어 있어도 "상가 공실"이 아니다.
#
# 주용도(mainPurpsCdNm)가 "기타제1종근린생활시설"이어도 기타용도(etcPurps)가
# "PIT층", "보일러실", "주택", "관리실"인 층이 실수집에서 공실 후보로 올라왔다.
# 세부용도 쪽 단어까지 여기서 걸러야 한다.
NON_LEASABLE_PURPOSE_KEYWORDS = (
    "주차장",
    "기계실",
    "전기실",
    "계단실",
    "승강기",
    "물탱크",
    "공용",
    "주택",  # 다가구/다세대/단독/연립 + etcPurps에 그냥 "주택"으로 적힌 층
    "아파트",
    "기숙사",
    "창고",
    "발전시설",
    "정화조",
    "피난",
    "PIT",
    "피트",
    "보일러",
    "관리실",
    "경비실",
    "화장실",
    "장례식장",
    "의료시설",  # 병원 본동. 근생 "의원"은 이 단어가 없어 그대로 후보가 된다
    "공공시설",
    "종교시설",
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
        key_env=KEY_ENV,
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


def probe_base_url(params: dict[str, str]) -> tuple[Optional[str], list[str]]:
    """
    표제부가 열리는 base_url을 찾아 고정한다 (건축HUB -> 구 서비스 순).
    사전 수집 스크립트가 첫 건물에서 한 번 호출한다.

    Returns:
        (찾은 base_url 또는 None, 실패 사유 목록)

    실패 사유를 함께 돌려주는 이유: 여기서 키가 틀리면 이후 모든 건물 조회가
    똑같이 실패하는데, 사유를 안 보여 주면 "오류 N건"만 남아 원인을 알 수 없다.
    """
    reasons: list[str] = []
    for base in (DEFAULT_BASE_URL, FALLBACK_BASE_URL):
        try:
            payload = datagokr.get_json(
                _endpoint(TITLE_OP, base),
                {**params, "_type": "json", "numOfRows": 1, "pageNo": 1},
                key_env=KEY_ENV,
            )
            datagokr.check_header(payload)
        except Exception as exc:
            message = datagokr.mask_secrets(str(exc))
            logger.info("건축물대장 base_url %s 확인 실패: %s", base, message)
            reasons.append("{} -> {}".format(base.rsplit("/", 1)[-1], message))
            continue
        os.environ["BLDRGST_API_BASE_URL"] = base
        return base, reasons
    return None, reasons


# 응답에 이 문구가 있으면 키 문제라서, 계속 호출해 봐야 전부 같은 결과다.
AUTH_ERROR_MARKERS = (
    "SERVICE_KEY_IS_NOT_REGISTERED",
    "SERVICE ACCESS DENIED",
    "UNREGISTERED",
    "403",
    "등록되지 않은",
)


def is_auth_error(message: str) -> bool:
    upper = message.upper()
    return any(marker.upper() in upper for marker in AUTH_ERROR_MARKERS)


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
    """
    주용도 + 기타용도를 합친 문자열. 용도 판정은 항상 이 합본으로 한다.

    두 값이 같거나 한쪽이 다른 쪽을 포함하면("휴게음식점" / "휴게음식점") 긴 쪽만 쓴다 —
    화면에 "휴게음식점 휴게음식점"으로 나가던 중복을 막는다.
    """
    main = str(item.get("mainPurpsCdNm") or "").strip()
    etc = str(item.get("etcPurps") or "").strip()
    if not main or main in etc:
        return etc
    if not etc or etc in main:
        return main
    return main + " " + etc


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


# flrGbCdNm 실측값: "지하" | "지상" | "옥탑". 옥탑은 층번호가 1부터 다시 시작해서
# 지상 1층과 flrNo가 겹치므로 반드시 따로 묶어야 한다.
GROUND = "지상"
BASEMENT = "지하"
ROOFTOP = "옥탑"


def floor_group(item: dict[str, Any]) -> str:
    """층 구분. flrGbCdNm이 비어 있으면 flrNoNm 문자열로 추정한다."""
    text = "{} {}".format(item.get("flrGbCdNm") or "", item.get("flrNoNm") or "")
    if ROOFTOP in text:
        return ROOFTOP
    if BASEMENT in text:
        return BASEMENT
    return GROUND


def floor_sign(item: dict[str, Any]) -> Optional[int]:
    """
    층별개요 레코드의 층수를 지상 양수 / 지하 음수 정수로. flrNo는 절대값으로 온다.

    옥탑은 지상 층번호와 겹치므로 ROOFTOP_OFFSET을 더해 구분한다. 옥탑은 상가
    공실 대상이 아니지만(계단실·물탱크가 대부분), 지상 1층에 면적이 합산되는
    오염을 막기 위해 별도 층으로 들고 있어야 한다.
    """
    number = _int(item.get("flrNo"))
    if number is None:
        # flrNoNm("지하1층", "1층", "옥탑1층")에서 파싱 폴백
        digits = "".join(ch for ch in str(item.get("flrNoNm") or "") if ch.isdigit())
        if not digits:
            return None
        number = int(digits)

    group = floor_group(item)
    if group == BASEMENT:
        return -abs(number)
    if group == ROOFTOP:
        return ROOFTOP_OFFSET + abs(number)
    return number


# 옥탑층을 지상층과 구분하기 위한 오프셋. 현실의 건물 층수를 한참 넘는 값이면 된다.
ROOFTOP_OFFSET = 900


def is_rooftop(floor: int) -> bool:
    return floor >= ROOFTOP_OFFSET


def parse_floors(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    층별개요를 층 단위로 정리한다.

    같은 층에 용도가 여러 줄로 쪼개져 오는 경우(예: 1층 소매점 / 1층 일반음식점)가
    있어 층 번호로 합친다. 지하/지상/옥탑은 flrNo가 겹치므로 floor_sign()이 구분한
    값으로 묶는다.

    임대 가능 여부는 **줄 단위**로 본다. 합본 문자열로 판정하면
      - "소매점 / 관리실"인 1층이 관리실 때문에 통째로 제외되거나
      - "제1종근린생활시설 PIT층"이 근린생활시설 때문에 통째로 후보가 되는
    양쪽 오판이 난다 (둘 다 실수집에서 확인). 그래서 상가로 쓸 수 있는 줄이
    하나라도 있으면 그 층은 임대 가능이고, area는 그 줄들의 면적만 더한다
    (소매점 60㎡ + 주차장 200㎡인 층을 260㎡ 매물로 내보내지 않기 위함).
    """
    merged: dict[int, dict[str, Any]] = {}

    for item in items:
        floor = floor_sign(item)
        if floor is None:
            continue
        purpose = _purpose_text(item)
        area = _float(item.get("area")) or 0.0
        leasable = is_commercial_purpose(purpose) and not is_non_leasable_purpose(purpose)

        entry = merged.get(floor)
        if entry is None:
            entry = {
                "floor": floor,
                "floor_label": str(item.get("flrNoNm") or "").strip(),
                "purposes": [],
                "area": 0.0,
                "leasable_area": 0.0,
                "has_leasable": False,
                "structure": str(item.get("strctCdNm") or "").strip(),
            }
            merged[floor] = entry

        if purpose and purpose not in entry["purposes"]:
            entry["purposes"].append(purpose)
        entry["area"] += area
        if leasable:
            entry["has_leasable"] = True
            entry["leasable_area"] += area

    floors = []
    for entry in merged.values():
        purpose_text = " / ".join(entry["purposes"])
        floor = entry["floor"]
        # 옥탑은 용도명이 근린생활시설로 적혀 있어도 임대 가능한 상가 층이
        # 아니다 (실측 사례: mainPurpsCdNm=기타제2종근린생활시설 / etcPurps=계단실).
        leasable = entry["has_leasable"] and not is_rooftop(floor)
        floors.append(
            {
                "floor": floor,
                "floor_label": _normalize_floor_label(entry["floor_label"], floor),
                "purpose": purpose_text,
                "area": round(entry["leasable_area"] if leasable else entry["area"], 2),
                "structure": entry["structure"],
                "is_commercial": leasable or is_commercial_purpose(purpose_text),
                "is_non_leasable": not leasable,
            }
        )
    floors.sort(key=lambda entry: entry["floor"])
    return floors


def _normalize_floor_label(raw: str, floor: int) -> str:
    """
    화면에 그대로 나가는 층 이름이라 표기를 고른다.

    대장의 flrNoNm은 "1층", "지하1층"처럼 온전한 값도 있지만 "지1"처럼 줄여 쓴
    값도 섞여 있다 (실수집에서 확인). 정상 표기가 아니면 층 번호로 다시 만든다.
    """
    label = (raw or "").strip()
    if label.endswith("층"):
        return label
    return _default_floor_label(floor)


def _default_floor_label(floor: int) -> str:
    if is_rooftop(floor):
        return "옥탑{}층".format(floor - ROOFTOP_OFFSET)
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
