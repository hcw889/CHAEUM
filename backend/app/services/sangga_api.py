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

# 이 모듈의 모든 호출은 상가정보 API 전용 키를 쓴다 (포털 개발계정은 활용신청
# 건별로 키가 따로 나온다). 전용 키가 없으면 datagokr가 공통 키로 폴백한다.
KEY_ENV = datagokr.SANGGA_KEY_ENV

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

# 사각형 조회가 이만큼 연속 거부되면 격자 크기 문제로 보고 순회를 중단한다.
# (실측: 0.1도 격자는 전부 INVALID_REQUEST_PARAMETER_ERROR, 0.04도는 정상)
MAX_INVALID_TILE_STREAK = 3


def base_url() -> str:
    return (os.environ.get("SANGGA_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def _endpoint(operation: str, base: Optional[str] = None) -> str:
    root = (base or base_url()).rstrip("/")
    return root + "/" + operation


def _request_params(extra: dict[str, Any]) -> dict[str, Any]:
    return {"type": "json", **extra}


def store_list_in_rectangle(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    *,
    rows: int = 1000,
    max_pages: int = 30,
    base: Optional[str] = None,
) -> Iterator[dict[str, Any]]:
    """
    사각형 영역 내 상가 목록. 지역 전체를 훑을 때 쓴다.

    행정구역 단위 조회(storeListInAdmi)가 이 계정에서 폐기(NO_OPENAPI_SERVICE_ERROR)
    되어 있어, 영역 단위 조회로 전북을 격자 순회한다 (sweep_region 참고).
    """
    yield from datagokr.paged(
        _endpoint("storeListInRectangle", base),
        _request_params(
            {"minx": min_lng, "miny": min_lat, "maxx": max_lng, "maxy": max_lat}
        ),
        key_env=KEY_ENV,
        rows=rows,
        max_pages=max_pages,
    )


def rectangle_total_count(
    min_lng: float, min_lat: float, max_lng: float, max_lat: float, base: Optional[str] = None
) -> int:
    """사각형 안의 전체 점포 수만 1건 조회로 확인한다 (빈 격자를 싸게 건너뛰기 위함)."""
    payload = datagokr.get_json(
        _endpoint("storeListInRectangle", base),
        _request_params(
            {
                "minx": min_lng,
                "miny": min_lat,
                "maxx": max_lng,
                "maxy": max_lat,
                "pageNo": 1,
                "numOfRows": 1,
            }
        ),
        key_env=KEY_ENV,
    )
    datagokr.check_header(payload)
    return datagokr.total_count(payload)


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
        key_env=KEY_ENV,
        rows=rows,
        max_pages=max_pages,
    )


def store_list_in_building(bld_mng_no: str, base: Optional[str] = None) -> list[dict[str, Any]]:
    """건물관리번호로 그 건물의 점포 목록. 사후 검증/실시간 조회용."""
    return list(
        datagokr.paged(
            _endpoint("storeListInBuilding", base),
            _request_params({"key": bld_mng_no}),
            key_env=KEY_ENV,
            rows=1000,
            max_pages=5,
        )
    )


def sweep_centers(
    centers: list[dict[str, Any]],
    *,
    radius_m: int = 2000,
    ctprvn_codes: tuple[str, ...] = JEONBUK_CTPRVN_CODES,
    rows: int = 1000,
    max_pages_per_center: int = 5,
    progress: Optional[Any] = None,
) -> Iterator[dict[str, Any]]:
    """
    지점 목록을 중심으로 반경 조회를 돌려 점포를 모은다.

    전역을 사각형 격자로 훑는 방식(sweep_region)은 개발계정 호출 한도(429)를
    금방 넘긴다. 시·군 대표 지점을 중심으로 도심 상권만 표본 수집하는 쪽이
    같은 호출 수로 훨씬 쓸모 있는 후보를 준다.

    Args:
        centers: [{"id", "region_name", "lat", "lng"}, ...]
        radius_m: 중심당 반경(미터)
        max_pages_per_center: 중심당 최대 페이지. 1페이지 1000건.

    중복은 bizesId로 걸러 낸다 — 반경이 겹치는 중심이 있기 때문이다.
    """
    seen_ids: set[str] = set()
    yielded = 0

    for index, center in enumerate(centers, start=1):
        lat, lng = center.get("lat"), center.get("lng")
        label = center.get("region_name") or center.get("id") or "?"
        if lat is None or lng is None:
            continue

        try:
            for raw in store_list_in_radius(
                lng, lat, radius_m, rows=rows, max_pages=max_pages_per_center
            ):
                if ctprvn_codes and str(raw.get("ctprvnCd") or "") not in ctprvn_codes:
                    continue
                store_id = str(raw.get("bizesId") or "")
                if store_id and store_id in seen_ids:
                    continue
                if store_id:
                    seen_ids.add(store_id)
                yielded += 1
                yield raw
        except datagokr.RateLimited:
            raise  # 한도는 호출부가 처리한다 (모은 만큼으로 진행)
        except datagokr.DataGoKrError as exc:
            logger.warning("중심 %s 조회 실패: %s", label, exc)
        except Exception as exc:
            logger.warning("중심 %s 호출 실패: %s", label, exc)

        if progress is not None:
            progress(index, len(centers), label, yielded)


def sweep_region(
    bbox: tuple[float, float, float, float],
    *,
    ctprvn_codes: tuple[str, ...] = JEONBUK_CTPRVN_CODES,
    step_deg: float = 0.04,
    rows: int = 1000,
    max_pages_per_tile: int = 30,
    progress: Optional[Any] = None,
) -> Iterator[dict[str, Any]]:
    """
    사각형 격자로 지역 전체를 훑는다.

    Args:
        bbox: (min_lng, min_lat, max_lng, max_lat)
        ctprvn_codes: 이 시도코드에 속한 점포만 내보낸다. 격자가 도 경계를 넘으면
            인접 도 점포가 섞여 들어오기 때문이다. 전북은 2024-01-18 전북특별자치도
            출범으로 45 -> 52가 되었고 데이터 기준월에 따라 둘 다 나타날 수 있다.
        step_deg: 격자 한 칸의 크기(도). 0.1도는 대략 9km x 11km다.
        progress: progress(tile_index, tile_total, tile_label, yielded) 콜백

    빈 격자는 totalCount만 보고 건너뛴다 (호출 1회). 중복은 bizesId로 걸러 낸다 —
    격자 경계에 걸친 점포가 두 번 나올 수 있다.
    """
    min_lng, min_lat, max_lng, max_lat = bbox
    lngs = _frange(min_lng, max_lng, step_deg)
    lats = _frange(min_lat, max_lat, step_deg)
    tiles = [(x, y) for y in lats for x in lngs]

    seen_ids: set[str] = set()
    yielded = 0
    invalid_streak = 0

    for index, (tile_lng, tile_lat) in enumerate(tiles, start=1):
        tile = (tile_lng, tile_lat, tile_lng + step_deg, tile_lat + step_deg)
        label = "{:.2f},{:.2f}".format(tile_lat, tile_lng)

        try:
            total = rectangle_total_count(*tile)
            invalid_streak = 0
        except datagokr.DataGoKrError as exc:
            logger.warning("격자 %s totalCount 실패: %s", label, exc)
            if _is_quota_error(exc):
                raise
            # 사각형이 API 허용 범위보다 크면 모든 격자가 똑같이 거부된다.
            # 수백 번 더 호출해 한도를 태우지 말고 바로 멈추고 원인을 알린다.
            if "INVALID_REQUEST_PARAMETER" in str(exc).upper():
                invalid_streak += 1
                if invalid_streak >= MAX_INVALID_TILE_STREAK:
                    raise datagokr.DataGoKrError(
                        "사각형 조회가 연속 {}회 거부되었습니다 (INVALID_REQUEST_PARAMETER). "
                        "격자 크기 {}도가 API 허용 범위를 넘는 것으로 보입니다 — "
                        "--step을 {:.2f} 이하로 줄이세요.".format(
                            invalid_streak, step_deg, max(0.01, step_deg / 2)
                        )
                    ) from None
            continue
        except Exception as exc:
            logger.warning("격자 %s 조회 실패: %s", label, exc)
            continue

        if total <= 0:
            if progress is not None:
                progress(index, len(tiles), label, yielded)
            continue

        try:
            for raw in store_list_in_rectangle(
                *tile, rows=rows, max_pages=max_pages_per_tile
            ):
                if ctprvn_codes and str(raw.get("ctprvnCd") or "") not in ctprvn_codes:
                    continue
                store_id = str(raw.get("bizesId") or "")
                if store_id and store_id in seen_ids:
                    continue
                if store_id:
                    seen_ids.add(store_id)
                yielded += 1
                yield raw
        except datagokr.DataGoKrError as exc:
            logger.warning("격자 %s 페이징 중단: %s", label, exc)
            if _is_quota_error(exc):
                raise
        except Exception as exc:
            logger.warning("격자 %s 페이징 실패: %s", label, exc)

        if progress is not None:
            progress(index, len(tiles), label, yielded)


def _frange(start: float, stop: float, step: float) -> list[float]:
    values = []
    current = start
    # 부동소수 누적 오차로 마지막 칸이 빠지지 않게 step의 절반을 여유로 둔다.
    while current < stop - step / 2:
        values.append(round(current, 6))
        current += step
    if not values or values[-1] + step < stop:
        values.append(round(current, 6))
    return values


def _is_quota_error(exc: Exception) -> bool:
    """일일 한도 초과는 재시도해도 소용없으므로 순회를 즉시 멈춘다."""
    message = str(exc).upper()
    return "LIMIT" in message or "초과" in str(exc)


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
        # 실응답 필드명은 lnoMnno/lnoSlno이고 값은 정수로 내려온다 (예: 222 / 3).
        # 포털 문서에 lnbrMnnm/lnbrSlno로 적힌 판본이 있어 둘 다 본다.
        "bun": _text(store, "lnoMnno", "lnbrMnnm"),
        "ji": _text(store, "lnoSlno", "lnbrSlno"),
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
