"""
소상공인시장진흥공단_상가(상권)정보 API 클라이언트.

이 API가 주는 것은 "영업 중인 점포 목록"이다. 공실 여부는 들어 있지 않다.
대신 점포마다 건물관리번호(bldMngNo)·법정동코드(ldongCd)·지번(lnbrMnnm/lnbrSlno)·
층(flrNo)이 붙어 있어서, 건축물대장(building_register_api.py)과 같은 건물 단위로
조인할 수 있다. 그 조인 결과로 공실을 추정하는 곳이 vacancy_estimator.py다.

이 모듈에서 얻는 실데이터:
  - 건물별 실제 영업 점포 목록 (상호/업종/층/좌표)
  - 동일 업종 점포 수 -> 경쟁포화도 (추정이 아닌 실측)
  - 건물 식별자 -> 건축물대장 조회 파라미터
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Iterator, Optional

from app.services import datagokr

logger = logging.getLogger(__name__)

# 포털 문서 기준 현행 경로는 sdsc2다. 구 버전(sdsc)만 열려 있는 계정도 있어
# .env에서 덮어쓸 수 있게 둔다.
DEFAULT_BASE_URL = "http://apis.data.go.kr/B553077/api/open/sdsc2"
FALLBACK_BASE_URL = "http://apis.data.go.kr/B553077/api/open/sdsc"

# 전라북도 시도코드. 2024-01-18 전북특별자치도 출범으로 45 -> 52로 바뀌었고,
# 상가정보 데이터 기준월에 따라 둘 중 하나가 쓰인다. 순서대로 시도해 맞는 쪽을 쓴다.
JEONBUK_CTPRVN_CODES = ("52", "45")

# 대지구분코드(plotSctCd) -> 건축물대장 platGbCd.
# 상가정보: 1=대지, 2=산. 건축물대장: 0=대지, 1=산, 2=블록.
PLOT_TO_PLAT_GB = {"1": "0", "2": "1", "0": "0"}


def base_url() -> str:
    return (os.environ.get("SANGGA_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def _endpoint(operation: str, base: Optional[str] = None) -> str:
    root = (base or base_url()).rstrip("/")
    return root + "/" + operation


def _request_params(extra: dict[str, Any]) -> dict[str, Any]:
    return {"type": "json", **extra}


def store_list_in_admi(
    div_id: str,
    key: str,
    *,
    rows: int = 1000,
    max_pages: int = 1000,
    progress: Optional[Any] = None,
    base: Optional[str] = None,
) -> Iterator[dict[str, Any]]:
    """
    행정구역 단위 상가 목록.

    Args:
        div_id: "ctprvnCd"(시도) | "signguCd"(시군구) | "adongCd"(행정동)
        key: div_id에 해당하는 행정구역 코드
    """
    yield from datagokr.paged(
        _endpoint("storeListInAdmi", base),
        _request_params({"divId": div_id, "key": key}),
        rows=rows,
        max_pages=max_pages,
        progress=progress,
    )


def store_list_in_radius(
    lng: float,
    lat: float,
    radius_m: int,
    *,
    inds_lcls_cd: Optional[str] = None,
    rows: int = 1000,
    max_pages: int = 50,
    base: Optional[str] = None,
) -> Iterator[dict[str, Any]]:
    """반경 내 상가 목록. cx=경도, cy=위도, radius=미터."""
    extra: dict[str, Any] = {"radius": radius_m, "cx": lng, "cy": lat}
    if inds_lcls_cd:
        extra["indsLclsCd"] = inds_lcls_cd
    yield from datagokr.paged(
        _endpoint("storeListInRadius", base),
        _request_params(extra),
        rows=rows,
        max_pages=max_pages,
    )


def store_list_in_building(bld_mng_no: str, base: Optional[str] = None) -> list[dict[str, Any]]:
    """건물관리번호로 그 건물의 점포 목록. 사후 검증/실시간 조회용."""
    return list(
        datagokr.paged(
            _endpoint("storeListInBuilding", base),
            _request_params({"key": bld_mng_no}),
            rows=1000,
            max_pages=5,
        )
    )


def resolve_jeonbuk_ctprvn_code() -> Optional[str]:
    """
    전북 시도코드가 52인지 45인지 1페이지만 찔러 확인한다.
    사전 수집 스크립트가 맨 앞에서 한 번 호출한다.
    """
    for code in JEONBUK_CTPRVN_CODES:
        for base in (base_url(), FALLBACK_BASE_URL):
            try:
                payload = datagokr.get_json(
                    _endpoint("storeListInAdmi", base),
                    _request_params(
                        {"divId": "ctprvnCd", "key": code, "pageNo": 1, "numOfRows": 1}
                    ),
                )
                datagokr.check_header(payload)
            except datagokr.DataGoKrError as exc:
                logger.info("상가정보 시도코드 %s (%s) 확인 실패: %s", code, base, exc)
                continue
            except Exception as exc:  # 네트워크/HTTP 오류
                logger.info("상가정보 호출 실패 %s (%s): %s", code, base, exc)
                continue

            if datagokr.extract_items(payload):
                if base != base_url():
                    os.environ["SANGGA_API_BASE_URL"] = base
                    logger.info("상가정보 base_url을 %s로 고정", base)
                return code
    return None


# --- 레코드 정규화 -------------------------------------------------------------


def _text(store: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = store.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _number(store: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = store.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def floor_number(store: dict[str, Any]) -> Optional[int]:
    """
    flrNo를 정수 층수로. 지하는 음수로 바꾼다.
    상가정보의 flrNo는 "1", "2", "B1", "지하1" 등으로 섞여 들어온다.
    """
    raw = _text(store, "flrNo", "floorNo")
    if not raw:
        return None

    negative = raw.upper().startswith("B") or "지하" in raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    value = int(digits)
    return -value if negative else value


def normalize_store(store: dict[str, Any]) -> dict[str, Any]:
    """API 레코드에서 우리가 쓰는 필드만 뽑아 고정 스키마로 정리한다."""
    ldong = _text(store, "ldongCd", "adongCd")
    return {
        "store_id": _text(store, "bizesId"),
        "name": _text(store, "bizesNm"),
        "branch": _text(store, "brchNm"),
        "inds_large": _text(store, "indsLclsNm"),
        "inds_middle": _text(store, "indsMclsNm"),
        "inds_small": _text(store, "indsSclsNm"),
        "inds_large_cd": _text(store, "indsLclsCd"),
        "inds_middle_cd": _text(store, "indsMclsCd"),
        "inds_small_cd": _text(store, "indsSclsCd"),
        "signgu_cd": _text(store, "signguCd"),
        "signgu_name": _text(store, "signguNm"),
        "adong_name": _text(store, "adongNm"),
        "ldong_cd": ldong,
        "ldong_name": _text(store, "ldongNm"),
        "bld_mng_no": _text(store, "bldMngNo"),
        "bld_name": _text(store, "bldNm"),
        "road_address": _text(store, "rdnmAdr", "rdnmAdrs"),
        "jibun_address": _text(store, "lnoAdr", "lnoAdrs"),
        "plot_sct_cd": _text(store, "plotSctCd"),
        "bun": _text(store, "lnbrMnnm"),
        "ji": _text(store, "lnbrSlno"),
        "floor": floor_number(store),
        "ho": _text(store, "hoNo"),
        "lng": _number(store, "lon", "lng", "x"),
        "lat": _number(store, "lat", "y"),
    }


def building_register_params(store: dict[str, Any]) -> Optional[dict[str, str]]:
    """
    정규화된 점포 레코드에서 건축물대장 조회 파라미터를 만든다.

    법정동코드 10자리 = 시군구코드(5) + 법정동코드(5). 건축물대장은 이 둘을
    나눠 받고, 본번/부번은 4자리 zero-pad를 요구한다.
    """
    ldong = (store.get("ldong_cd") or "").strip()
    bun = (store.get("bun") or "").strip()
    if len(ldong) < 10 or not bun.isdigit():
        return None

    ji = (store.get("ji") or "0").strip()
    if not ji.isdigit():
        ji = "0"

    return {
        "sigunguCd": ldong[:5],
        "bjdongCd": ldong[5:10],
        "platGbCd": PLOT_TO_PLAT_GB.get(store.get("plot_sct_cd") or "1", "0"),
        "bun": bun.zfill(4),
        "ji": ji.zfill(4),
    }


def building_key(store: dict[str, Any]) -> Optional[str]:
    """
    건물 단위 그룹핑 키.

    bldMngNo가 있으면 그것이 가장 정확하다. 비어 있는 레코드가 적지 않아
    법정동코드+대지구분+본번+부번으로 폴백한다.
    """
    bld_mng_no = (store.get("bld_mng_no") or "").strip()
    if bld_mng_no:
        return "mng:" + bld_mng_no

    params = building_register_params(store)
    if params is None:
        return None
    return "jibun:{}{}-{}-{}-{}".format(
        params["sigunguCd"], params["bjdongCd"], params["platGbCd"], params["bun"], params["ji"]
    )


def group_by_building(stores: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    정규화된 점포들을 건물 단위로 묶는다.

    Returns:
        building_key -> {
            "key", "bld_mng_no", "bld_name", "register_params",
            "signgu_cd", "signgu_name", "ldong_name", "adong_name",
            "road_address", "jibun_address", "lat", "lng",
            "stores": [...],                  # 그 건물의 전체 점포
            "stores_by_floor": {층: [...]},    # 층 미상은 None 키
        }
    """
    buildings: dict[str, dict[str, Any]] = {}

    for store in stores:
        key = building_key(store)
        if key is None:
            continue

        entry = buildings.get(key)
        if entry is None:
            entry = {
                "key": key,
                "bld_mng_no": store.get("bld_mng_no") or "",
                "bld_name": store.get("bld_name") or "",
                "register_params": building_register_params(store),
                "signgu_cd": store.get("signgu_cd") or "",
                "signgu_name": store.get("signgu_name") or "",
                "ldong_name": store.get("ldong_name") or "",
                "adong_name": store.get("adong_name") or "",
                "road_address": store.get("road_address") or "",
                "jibun_address": store.get("jibun_address") or "",
                "lat": store.get("lat"),
                "lng": store.get("lng"),
                "stores": [],
                "stores_by_floor": {},
            }
            buildings[key] = entry

        # 건물명/좌표는 점포마다 누락이 있어 먼저 채워진 값을 유지하고 빈 칸만 메운다.
        for field in ("bld_name", "road_address", "jibun_address", "ldong_name", "adong_name"):
            if not entry[field] and store.get(field):
                entry[field] = store[field]
        for field in ("lat", "lng"):
            if entry[field] is None and store.get(field) is not None:
                entry[field] = store[field]
        if entry["register_params"] is None:
            entry["register_params"] = building_register_params(store)

        entry["stores"].append(store)
        entry["stores_by_floor"].setdefault(store.get("floor"), []).append(store)

    return buildings
