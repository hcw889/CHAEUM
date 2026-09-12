"""
실제 공실 매물 데이터 수집 — 소상공인 상가정보 API + 국토부 건축HUB 건축물대장 API.

두 API를 건물 단위로 조인해 "대장에는 상업용도인데 영업 점포가 0건인 층"을 찾아
매물 후보로 만든다. 판정 논리와 점수 계산은 app/services/vacancy_estimator.py에 있고,
이 스크립트는 호출/페이징/캐시 저장만 담당한다.

수집 방식 (실제 API 동작에 맞춰 정한 것이다):
  - 행정구역 단위 조회(storeListInAdmi)는 폐기되어(NO_OPENAPI_SERVICE_ERROR) 쓸 수 없다.
  - 전역을 사각형 격자로 훑으면 개발계정 호출 한도(429)를 금방 넘는다.
    0.1도 격자는 API가 아예 거부한다(INVALID_REQUEST_PARAMETER_ERROR).
  - 그래서 기본은 시·군 대표 지점(region_stats.json 좌표) 반경 조회다.
    전북 14개 시·군 + 전주 5개 시범 상권 도심을 표본으로 훑는다.
  - 반경/격자 모두 도 경계를 넘어온 인접 도 점포는 ctprvnCd로 걸러 낸다.

실행:
    cd backend
    python scripts/fetch_real_vacancies.py                      # 전북 시·군 전역(기본)
    python scripts/fetch_real_vacancies.py --max-buildings 200  # 호출 절약
    python scripts/fetch_real_vacancies.py --signgu 전주시 --max-buildings 300  # 데모 지역 집중
    python scripts/fetch_real_vacancies.py --mode grid --bbox 127.08,35.79,127.20,35.86

사전 준비 — 두 API는 포털 활용신청이 각각이라 서비스키도 각각이다.
backend/.env에 각 API의 '일반 인증키(Decoding)'를 넣는다:

    SANGGA_API_SERVICE_KEY=...   소상공인시장진흥공단_상가(상권)정보
    BLDRGST_API_SERVICE_KEY=...  국토교통부_건축HUB_건축물대장정보 서비스

한 키로 두 API가 다 열리는 계정이면 DATA_GO_KR_SERVICE_KEY 하나만 넣어도 된다
(전용 키가 없을 때의 폴백).

출력 (app/data/real/):
    buildings.json     매물 후보 (기존 buildings.json과 동일 스키마 + vacancy/register)
    market_data.json   매물 x 업종 raw 시장 신호
    region_stats.json  시군별 표본 공실 집계
    meta.json          수집 시각/건수/출처

결과 JSON이 존재하면 app이 MockDataProvider 대신 RealSanggaProvider를 쓴다
(app/services/data_provider.get_data_provider).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Optional

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# app.* 임포트 전에 .env를 올린다 (app/main.py를 거치지 않으므로 직접 로드).
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

from app.models import regions as region_models  # noqa: E402  (경로 설정 후 임포트)
from app.services import (  # noqa: E402
    building_register_api,
    datagokr,
    register_cache,
    sangga_api,
    vacancy_estimator,
)

OUT_DIR = BASE_DIR / "app" / "data" / "real"

BUSINESS_TYPES = ["카페", "학원", "병원", "편의점", "스터디카페"]

# 전북특별자치도 대략 경계 (min_lng, min_lat, max_lng, max_lat).
# 서쪽 군산/부안 해안 ~ 동쪽 무주/장수 산간, 남쪽 남원 ~ 북쪽 익산.
# 격자가 도 경계를 넘으면 인접 도 점포가 섞이므로 sweep_region이 ctprvnCd로 걸러 낸다.
JEONBUK_BBOX = (126.40, 35.00, 127.95, 36.15)

# region_stats의 지역 id는 프론트/목업과 맞춘다 (시군명 -> id).
SIGNGU_TO_REGION_ID = {
    "전주시완산구": "jeonju",
    "전주시덕진구": "jeonju",
    "전주시": "jeonju",
    "군산시": "gunsan",
    "익산시": "iksan",
    "정읍시": "jeongeup",
    "남원시": "namwon",
    "김제시": "gimje",
    "완주군": "wanju",
    "진안군": "jinan",
    "무주군": "muju",
    "장수군": "jangsu",
    "임실군": "imsil",
    "순창군": "sunchang",
    "고창군": "gochang",
    "부안군": "buan",
}


def _utf8_stdout() -> None:
    """Windows 콘솔(cp949)에서 한글/기호 출력이 죽지 않게 한다."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass


def log(message: str) -> None:
    print(message, flush=True)


# --- 1단계: 상가정보 수집 -------------------------------------------------------


def load_centers() -> list[dict[str, Any]]:
    """
    반경 수집의 중심 지점. region_stats.json의 시·군/상권 대표 좌표를 그대로 쓴다.

    전북 14개 시·군 + 전주 5개 시범 상권이 이미 들어 있어서, 별도 좌표 표를
    새로 만들지 않아도 시·군별 coverage가 확보된다.
    """
    path = BASE_DIR / "app" / "data" / "region_stats.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {"id": item["id"], "region_name": item["region_name"], "lat": item["lat"], "lng": item["lng"]}
        for item in data["regions"]
        if item.get("lat") is not None and item.get("lng") is not None
    ]


def collect_stores_by_centers(
    centers: list[dict[str, Any]], radius_m: int, max_pages: int
) -> list[dict[str, Any]]:
    """
    시·군 대표 지점 반경으로 점포를 모은다 (기본 방식).

    행정구역 단위 조회(storeListInAdmi)는 이 계정에서 폐기되어 쓸 수 없고, 전역을
    사각형 격자로 훑으면 개발계정 호출 한도(429)를 금방 넘긴다. 그래서 시·군
    도심 반경만 표본 수집한다 — 같은 호출 수로 훨씬 쓸모 있는 후보가 나온다.
    """
    log(
        "상가정보 수집 — 중심 {}곳 / 반경 {:,}m / 중심당 최대 {}페이지".format(
            len(centers), radius_m, max_pages
        )
    )

    stores: list[dict[str, Any]] = []

    def progress(index: int, total: int, label: str, yielded: int) -> None:
        log("  [{}/{}] {} — 누적 {:,}건".format(index, total, label, yielded))

    try:
        for raw in sangga_api.sweep_centers(
            centers, radius_m=radius_m, max_pages_per_center=max_pages, progress=progress
        ):
            stores.append(sangga_api.normalize_store(raw))
    except datagokr.DataGoKrError as exc:
        if not stores:
            raise
        log("  [경고] 수집이 중단되었습니다 ({}). 모은 {:,}건으로 계속합니다.".format(exc, len(stores)))

    log("상가정보 {:,}건 수집 완료".format(len(stores)))
    return stores


def collect_stores_by_grid(
    bbox: tuple[float, float, float, float], step_deg: float
) -> list[dict[str, Any]]:
    """
    사각형 격자로 지역 전체를 훑는다 (--mode grid).

    호출 수가 많아 개발계정 한도로는 전북 전역을 끝까지 돌기 어렵다. 한도가 넉넉한
    운영계정이나 좁은 --bbox에서 쓴다. 0.1도 격자는 API가 거부하므로 0.04도가 기본이다.
    """
    log(
        "상가정보 수집(격자) — bbox {} / 격자 {}도 (약 {:.0f}km)".format(
            bbox, step_deg, step_deg * 111
        )
    )

    stores: list[dict[str, Any]] = []

    def progress(index: int, total: int, label: str, yielded: int) -> None:
        if index % 10 == 0 or index == total:
            log("  격자 {}/{} ({}) — 누적 {:,}건".format(index, total, label, yielded))

    try:
        for raw in sangga_api.sweep_region(bbox, step_deg=step_deg, progress=progress):
            stores.append(sangga_api.normalize_store(raw))
    except datagokr.DataGoKrError as exc:
        if not stores:
            raise
        # 쿼터 초과로 중간에 끊겨도 모은 만큼으로 진행한다.
        log("  [경고] 수집이 중단되었습니다 ({}). 모은 {:,}건으로 계속합니다.".format(exc, len(stores)))

    log("상가정보 {:,}건 수집 완료".format(len(stores)))
    return stores


# --- 2단계: 건축물대장 조회 대상 선별 -------------------------------------------


# 대장 조회 우선순위는 런타임 라이브 검색(app/services/live_search.py)과 공유한다.
_candidate_priority = vacancy_estimator.candidate_priority


def select_buildings(
    buildings: dict[str, dict[str, Any]],
    max_buildings: int,
    signgu_filter: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """
    조회 대상 건물을 시군별로 비례 배분해 고른다.

    건축물대장은 건물당 2회(표제부+층별개요) 호출한다. 전북 전체 건물을 다 보면
    개발계정 일일 한도를 넘기므로 상한을 두고, 전주만 쏠리지 않게 시군별로 나눈다.

    배분은 "비례 몫(내림) + 나머지는 후보가 많은 시군부터 1건씩"이다. 예전처럼
    시군마다 최소 10건을 주고 마지막에 [:max_buildings]로 자르면, 가나다순 뒤쪽
    시군(장수·전주·정읍·진안)이 통째로 빠진다 — 실수집(상한 100)에서 전주 0건으로
    확인한 문제다.

    Args:
        signgu_filter: 시군명 부분 문자열 목록. 주면 이 시군의 건물만 대상으로 한다
            (예: ["전주시"] -> 완산구/덕진구 모두). 데모 지역만 집중 수집할 때 쓴다.
    """
    usable = [
        b
        for b in buildings.values()
        if b.get("register_params") and b.get("lat") is not None and b.get("lng") is not None
    ]
    log("건물 {:,}개 중 지번/좌표가 온전한 {:,}개가 조회 가능".format(len(buildings), len(usable)))

    if signgu_filter:
        wanted = [token.replace(" ", "") for token in signgu_filter if token.strip()]
        usable = [
            b
            for b in usable
            if any(token in (b.get("signgu_name") or "").replace(" ", "") for token in wanted)
        ]
        log("--signgu {} 로 좁힌 조회 가능 건물 {:,}개".format(", ".join(wanted), len(usable)))

    by_signgu: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for building in usable:
        by_signgu[building.get("signgu_name") or building.get("signgu_cd") or "미상"].append(building)
    for group in by_signgu.values():
        group.sort(key=_candidate_priority)

    if len(usable) <= max_buildings:
        selected = usable
    else:
        total = len(usable)
        take = {
            signgu: min(len(group), max_buildings * len(group) // total)
            for signgu, group in by_signgu.items()
        }
        remaining = max_buildings - sum(take.values())
        # 내림으로 남은 자리는 후보가 많은 시군부터 한 건씩 (시군 수보다 적으므로 한 바퀴면 끝).
        for signgu in sorted(by_signgu, key=lambda s: len(by_signgu[s]), reverse=True):
            if remaining <= 0:
                break
            if take[signgu] < len(by_signgu[signgu]):
                take[signgu] += 1
                remaining -= 1
        selected = [b for signgu, group in by_signgu.items() for b in group[: take[signgu]]]

    log("건축물대장 조회 대상 {:,}개 건물 (약 {:,}회 호출)".format(len(selected), len(selected) * 2))
    for signgu in sorted(by_signgu):
        count = sum(1 for b in selected if (b.get("signgu_name") or b.get("signgu_cd") or "미상") == signgu)
        log("  {} {:,}개 (후보 {:,}개)".format(signgu, count, len(by_signgu[signgu])))
    return selected


# --- 3단계: 건축물대장 조회 + 공실 판정 ------------------------------------------


# 실패가 수백 건이어도 로그가 도배되지 않게 앞의 몇 건만 보여 준다.
# 0건이면 원인을 전혀 알 수 없으므로 반드시 몇 건은 보여 줘야 한다.
ERROR_SAMPLE_LIMIT = 5


def _log_sample_error(error_count: int, building: dict[str, Any], message: str) -> None:
    if error_count <= ERROR_SAMPLE_LIMIT:
        log("  [건너뜀] {} — {}".format(building.get("jibun_address") or building["key"], message))
    elif error_count == ERROR_SAMPLE_LIMIT + 1:
        log("  [건너뜀] … 이후 오류는 요약만 표시합니다")


def fetch_registers(
    selected: list[dict[str, Any]], today: date, sleep_sec: float
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    선별된 건물마다 표제부/층별개요를 가져와 공실 후보 레코드를 만든다.

    Returns:
        (후보 레코드 목록, 통계 dict)
    """
    stats = {
        "queried": 0,
        "register_found": 0,
        "register_missing": 0,
        "errors": 0,
        "commercial_floors": 0,
        "vacant_candidates": 0,
    }
    candidates: list[dict[str, Any]] = []
    # 시군별 모집단(조사한 상업용도 층 수) — region_stats의 total_units가 된다.
    commercial_by_signgu: dict[str, int] = defaultdict(int)
    vacant_by_signgu: dict[str, int] = defaultdict(int)

    if selected:
        probed, reasons = building_register_api.probe_base_url(selected[0]["register_params"])
        if probed:
            log("건축물대장 base_url: {}".format(probed))
        else:
            # 여기서 실패하면 이후 모든 건물이 같은 이유로 실패한다. 사유를 바로 보여 준다.
            log("건축물대장 접속 확인 실패 — 사유:")
            for reason in reasons:
                log("  " + reason)
            if any(building_register_api.is_auth_error(reason) for reason in reasons):
                log("")
                log("  건축물대장 서비스키가 거부되었습니다. backend/.env의")
                log("  {}를 확인하세요 (포털의 '일반 인증키(Decoding)' 전체 문자열).".format(
                    datagokr.BLDRGST_KEY_ENV
                ))
                log("  키가 한 글자라도 잘리면 이 오류가 납니다.")
                return [], stats

    for position, building in enumerate(selected, start=1):
        if position % 25 == 0:
            log(
                "  건축물대장 {}/{} — 대장 확인 {} / 공실후보 {}".format(
                    position, len(selected), stats["register_found"], stats["vacant_candidates"]
                )
            )

        stats["queried"] += 1
        try:
            # 런타임 라이브 검색과 같은 디스크 캐시를 쓴다. 여기서 한 번 수집해 두면
            # 그 지역의 첫 라이브 검색부터 대장 호출 없이 즉시 뜬다.
            register = register_cache.get_or_fetch(
                building["register_params"], building_register_api.fetch_building
            )
        except datagokr.DataGoKrError as exc:
            stats["errors"] += 1
            message = datagokr.mask_secrets(str(exc))
            if isinstance(exc, datagokr.RateLimited) or "LIMIT" in message.upper() or "초과" in message:
                log("  [중단] 호출 한도에 걸렸습니다: {}".format(message))
                break
            # 키가 거부되면 남은 건물도 전부 같은 이유로 실패한다. 호출을 더
            # 태우지 말고 바로 멈추고 원인을 알린다 (이전에는 조용히 세기만 해서
            # "오류 100"만 남고 이유를 알 수 없었다).
            if building_register_api.is_auth_error(message):
                log("  [중단] 건축물대장 서비스키가 거부되었습니다: {}".format(message))
                log("         backend/.env의 {}를 확인하세요 (Decoding 키 전체 문자열).".format(
                    datagokr.BLDRGST_KEY_ENV
                ))
                break
            _log_sample_error(stats["errors"], building, message)
            continue
        except Exception as exc:  # 네트워크/타임아웃 — 건물 단위로 건너뛴다
            stats["errors"] += 1
            _log_sample_error(stats["errors"], building, datagokr.mask_secrets(str(exc)))
            continue

        if register is None:
            stats["register_missing"] += 1
            continue
        stats["register_found"] += 1

        signgu = building.get("signgu_name") or "미상"
        leasable_floors = [
            floor
            for floor in register["floors"]
            if floor["is_commercial"] and not floor["is_non_leasable"] and (floor["area"] or 0) > 0
        ]
        commercial_by_signgu[signgu] += len(leasable_floors)
        stats["commercial_floors"] += len(leasable_floors)

        found = vacancy_estimator.candidates_for_building(building, register, today=today)
        candidates.extend(found)
        vacant_by_signgu[signgu] += len(found)
        stats["vacant_candidates"] += len(found)

        if sleep_sec:
            time.sleep(sleep_sec)

    stats["commercial_by_signgu"] = dict(commercial_by_signgu)  # type: ignore[assignment]
    stats["vacant_by_signgu"] = dict(vacant_by_signgu)  # type: ignore[assignment]
    return candidates, stats


# --- 4단계: 시장 신호 / 지역 집계 ----------------------------------------------


def build_market_data(
    index: vacancy_estimator.StoreIndex, candidates: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """매물 x 업종 raw 시장 신호. market_data.json과 같은 구조."""
    references = vacancy_estimator.saturation_references(index, candidates, BUSINESS_TYPES)
    log("경쟁포화도 기준(90분위 동일업종 점포 수): {}".format(references))

    market: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        market[candidate["id"]] = {
            business_type: vacancy_estimator.build_market_entry(
                index,
                candidate.get("lat"),
                candidate.get("lng"),
                business_type,
                candidate.get("signgu_name", ""),
                candidate.get("area_pyeong", 0) or 0,
                candidate.get("floor", 1),
                saturation_reference=references.get(business_type),
            )
            for business_type in BUSINESS_TYPES
        }
    return market


def build_region_stats(
    candidates: list[dict[str, Any]], stats: dict[str, Any], today: date
) -> dict[str, Any]:
    """
    시군별 표본 공실 집계.

    실데이터에는 과거 이력이 없으므로 월별 추이를 만들지 않는다. months는
    수집 기준월 1개이고, total_units는 '조사한 상업용도 층 수'(표본 모집단)다.
    목업의 전북 전체 상가 수와는 의미가 다르므로 description에 명시한다.
    """
    month = today.strftime("%Y-%m")
    commercial = stats.get("commercial_by_signgu") or {}
    vacant = stats.get("vacant_by_signgu") or {}

    coords: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for candidate in candidates:
        signgu = candidate.get("signgu_name") or "미상"
        if candidate.get("lat") is not None:
            coords[signgu].append((candidate["lat"], candidate["lng"]))

    # 공실 후보가 0건인 시군은 목업 region_stats의 시군 대표 좌표를 쓴다. 예전에는
    # 전부 전주시청 좌표로 찍어서 지자체 대시보드 지도에 고창·무주·순창·완주·임실
    # 마커가 전주 위에 겹쳐 보였다.
    center_by_region_id = {center["id"]: center for center in load_centers()}

    regions = []
    for signgu, total_units in sorted(commercial.items()):
        if total_units <= 0:
            continue
        vacant_units = min(vacant.get(signgu, 0), total_units)
        points = coords.get(signgu) or []
        if points:
            lat = sum(p[0] for p in points) / len(points)
            lng = sum(p[1] for p in points) / len(points)
        else:
            center = center_by_region_id.get(_region_id(signgu))
            if center:
                lat, lng = center["lat"], center["lng"]
            else:
                lat, lng = 35.8242, 127.1480  # 전주시청 — 대표 좌표도 없는 시군의 최후 폴백

        regions.append(
            {
                "id": _region_id(signgu),
                "scope": "district",
                "region_name": signgu,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "total_units": total_units,
                # 실데이터에는 평균 공실 기간 정보가 없다. 0은 "미집계"를 뜻한다.
                "avg_vacancy_period_months": 0.0,
                # finalize_top_business()가 시장 신호를 보고 채운다.
                "top_recommended_business": BUSINESS_TYPES[0],
                "monthly_vacant_units": [vacant_units],
            }
        )

    # 같은 region id(전주 완산/덕진)는 합산한다 — 모델이 id 중복을 기대하지 않는다.
    regions = _merge_by_region_id(regions)

    return {
        "is_mock": False,
        "data_reference_month": month,
        "months": [month],
        "description": (
            "소상공인시장진흥공단 상가(상권)정보 API와 국토교통부 건축HUB 건축물대장정보 API를 "
            "건물 단위로 조인해 산출한 공실 추정치입니다. 두 API 모두 공실 여부를 직접 제공하지 "
            "않으므로, 건축물대장에 근린생활시설·판매시설로 등재된 층 중 상가정보에 등록 점포가 "
            "0건인 층을 공실 후보로 판정했습니다. 전체 상가가 아니라 조회한 표본 기준이며, "
            "상가정보가 분기 스냅샷이라 신규 개업이 아직 반영되지 않은 층이 공실로 잡힐 수 있습니다. "
            "과거 이력이 없어 월별 추이는 제공하지 않습니다."
        ),
        "regions": regions,
    }


def _region_id(signgu_name: str) -> str:
    """
    시군명 -> region_stats id. 프론트/목업과 id를 맞추기 위한 변환이다.

    상가정보 API의 signguNm은 "전주시 완산구"처럼 구까지 붙어 오거나 띄어쓰기가
    제각각이라, 공백 제거 후 전체 일치 -> 선행 "OO시/OO군" 토큰 일치 순으로 찾는다.
    어디에도 없으면 이름 기반 슬러그를 쓴다 (지역이 빠지는 것보다 낫다).
    """
    compact = signgu_name.replace(" ", "")
    if compact in SIGNGU_TO_REGION_ID:
        return SIGNGU_TO_REGION_ID[compact]

    for suffix in ("시", "군"):
        index = compact.find(suffix)
        if index > 0:
            head = compact[: index + 1]
            if head in SIGNGU_TO_REGION_ID:
                return SIGNGU_TO_REGION_ID[head]

    return _slug(signgu_name)


def _slug(name: str) -> str:
    digest = sum(ord(ch) for ch in name)
    return "region{}".format(digest % 100000)


def _merge_by_region_id(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for region in regions:
        existing = merged.get(region["id"])
        if existing is None:
            merged[region["id"]] = dict(region)
            continue
        existing["total_units"] += region["total_units"]
        existing["monthly_vacant_units"] = [
            existing["monthly_vacant_units"][0] + region["monthly_vacant_units"][0]
        ]
        # 전주시 완산구/덕진구를 합치면 이름은 상위 시로 표기한다.
        if existing["region_name"] != region["region_name"]:
            existing["region_name"] = existing["region_name"].split("시")[0] + "시"
    return list(merged.values())


def finalize_top_business(
    region_stats: dict[str, Any], candidates: list[dict[str, Any]], market: dict[str, dict[str, Any]]
) -> None:
    """
    지역별 추천 업종을 시장 신호에서 채운다. 경쟁포화도가 낮고 인구통계 적합도가
    높은 업종을 고른다 (scoring.py의 market_fit과 같은 방향).
    """
    by_region: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        region_id = _region_id(candidate.get("signgu_name") or "미상")
        by_region[region_id].append(candidate["id"])

    for region in region_stats["regions"]:
        ids = by_region.get(region["id"]) or []
        best, best_score = BUSINESS_TYPES[0], -1.0
        for business_type in BUSINESS_TYPES:
            entries = [market[i][business_type] for i in ids if i in market]
            if not entries:
                continue
            score = sum(
                (100 - e["competition_saturation_index"]) * 0.6 + e["demographic_fit_index"] * 0.4
                for e in entries
            ) / len(entries)
            if score > best_score:
                best, best_score = business_type, score
        region["top_recommended_business"] = best


def validate_region_stats(region_stats: dict[str, Any]) -> None:
    """
    /api/regions/stats 라우터가 던지는 검증을 미리 통과시킨다.
    수집 후가 아니라 여기서 깨지는 게 디버깅이 쉽다.
    """
    months = region_stats["months"]
    for region in region_stats["regions"]:
        history = region["monthly_vacant_units"]
        if region["total_units"] <= 0 or len(history) != len(months):
            raise SystemExit("region_stats 검증 실패: {}".format(region["region_name"]))
        if any(count < 0 or count > region["total_units"] for count in history):
            raise SystemExit("공실 수가 모집단을 넘습니다: {}".format(region["region_name"]))
    # pydantic 모델로도 한 번 태워 본다.
    region_models.RegionStatsResponse(
        **{
            **region_stats,
            "regions": [
                {
                    **region,
                    "vacant_units": region["monthly_vacant_units"][-1],
                    "vacancy_rate": round(
                        region["monthly_vacant_units"][-1] / region["total_units"] * 100, 1
                    ),
                    "vacancy_trend_6m": [
                        round(count / region["total_units"] * 100, 1)
                        for count in region["monthly_vacant_units"]
                    ],
                }
                for region in region_stats["regions"]
            ],
        }
    )


# --- 엔트리포인트 --------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="실제 공실 매물 데이터 수집")
    parser.add_argument(
        "--max-buildings",
        type=int,
        default=800,
        help="건축물대장을 조회할 건물 수 상한 (건물당 2회 호출). 기본 800",
    )
    parser.add_argument(
        "--mode",
        choices=("centers", "grid"),
        default="centers",
        help="centers=시·군 대표 지점 반경 수집(기본, 호출 적음) / grid=bbox 격자 순회(호출 많음)",
    )
    parser.add_argument(
        "--radius", type=int, default=2000, help="centers 모드의 중심당 반경(m). 기본 2000"
    )
    parser.add_argument(
        "--center-pages",
        type=int,
        default=5,
        help="centers 모드의 중심당 최대 페이지(1000건/페이지). 기본 5",
    )
    parser.add_argument(
        "--bbox",
        default=None,
        help="grid 모드의 수집 영역 'min_lng,min_lat,max_lng,max_lat'. 기본은 전북 전역",
    )
    parser.add_argument(
        "--step",
        type=float,
        default=0.04,
        help="grid 모드 격자 한 칸 크기(도). 0.1도는 API가 거부한다(실측). 기본 0.04",
    )
    parser.add_argument(
        "--signgu",
        default=None,
        help="건축물대장 조회를 이 시군으로 한정 (쉼표 구분, 부분 일치). 예: '전주시' 또는 '전주시,익산시'",
    )
    parser.add_argument("--sleep", type=float, default=0.12, help="건축물대장 호출 간 대기 초")
    parser.add_argument("--out", default=str(OUT_DIR), help="출력 디렉터리")
    return parser.parse_args()


def parse_bbox(raw: Optional[str]) -> tuple[float, float, float, float]:
    if not raw:
        return JEONBUK_BBOX
    parts = [float(piece) for piece in raw.split(",")]
    if len(parts) != 4:
        raise SystemExit("--bbox는 'min_lng,min_lat,max_lng,max_lat' 형식이어야 합니다.")
    return (parts[0], parts[1], parts[2], parts[3])


def main() -> int:
    _utf8_stdout()
    args = parse_args()

    # 두 API는 포털 활용신청이 각각이라 서비스키도 각각이다. 둘 중 하나라도
    # 없으면 수집이 반쪽이 되므로 시작 전에 같이 확인한다.
    missing = [
        key_env
        for key_env in (datagokr.SANGGA_KEY_ENV, datagokr.BLDRGST_KEY_ENV)
        if not datagokr.has_service_key(key_env)
    ]
    if missing:
        log("서비스키가 없어 수집을 시작할 수 없습니다.")
        for key_env in missing:
            log("  - " + datagokr.missing_key_message(key_env))
        log("")
        log("backend/.env 예시:")
        log("    SANGGA_API_SERVICE_KEY=상가정보_Decoding_키")
        log("    BLDRGST_API_SERVICE_KEY=건축물대장_Decoding_키")
        return 1

    log(
        "서비스키 확인 — 상가정보 {} / 건축물대장 {}".format(
            "전용 키" if os.environ.get(datagokr.SANGGA_KEY_ENV) else "공통 키",
            "전용 키" if os.environ.get(datagokr.BLDRGST_KEY_ENV) else "공통 키",
        )
    )

    today = date.today()
    started = datetime.now()

    bbox = parse_bbox(args.bbox)
    if args.mode == "grid":
        stores = collect_stores_by_grid(bbox, args.step)
    else:
        stores = collect_stores_by_centers(load_centers(), args.radius, args.center_pages)
    if not stores:
        log("수집된 점포가 없습니다.")
        return 1

    buildings = sangga_api.group_by_building(stores)
    index = vacancy_estimator.StoreIndex(stores)
    log("좌표가 있는 점포 {:,}건으로 공간 인덱스 구성".format(len(index)))

    signgu_filter = [token for token in (args.signgu or "").split(",") if token.strip()] or None
    selected = select_buildings(buildings, args.max_buildings, signgu_filter)
    candidates, stats = fetch_registers(selected, today, args.sleep)

    if not candidates:
        log(
            "공실 후보를 찾지 못했습니다.\n"
            "  대장 확인 {} / 대장 미등재 {} / 오류 {}".format(
                stats["register_found"], stats["register_missing"], stats["errors"]
            )
        )
        # 원인에 맞는 안내만 한다. 대장 조회가 통째로 실패했는데 "--max-buildings를
        # 늘려 보라"고 하면 같은 실패를 더 많이 반복하게 된다.
        if stats["register_found"] == 0:
            log("")
            log("  건축물대장 조회가 한 건도 성공하지 못했습니다 — 수집 범위 문제가 아닙니다.")
            log("  위의 [건너뜀]/[중단] 사유를 보고 서비스키부터 확인하세요:")
            log("    backend/.env의 {} (포털 '일반 인증키(Decoding)' 전체 문자열)".format(
                datagokr.BLDRGST_KEY_ENV
            ))
        else:
            log("  --max-buildings를 늘리거나 --bbox로 도심 영역을 좁혀 보세요.")
        return 1

    log("공실 후보 {:,}건 (조사 상업용도 층 {:,}개)".format(len(candidates), stats["commercial_floors"]))

    market = build_market_data(index, candidates)
    region_stats = build_region_stats(candidates, stats, today)
    finalize_top_business(region_stats, candidates, market)
    validate_region_stats(region_stats)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    buildings_out = {candidate["id"]: candidate for candidate in candidates}
    _write(out_dir / "buildings.json", buildings_out)
    _write(out_dir / "market_data.json", market)
    _write(out_dir / "region_stats.json", region_stats)
    _write(
        out_dir / "meta.json",
        {
            "collected_at": started.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "data_reference_month": today.strftime("%Y-%m"),
            "collection_mode": args.mode,
            "center_radius_m": args.radius if args.mode == "centers" else None,
            "bbox": list(bbox) if args.mode == "grid" else None,
            "grid_step_deg": args.step if args.mode == "grid" else None,
            "signgu_filter": signgu_filter,
            "ctprvn_codes": list(sangga_api.JEONBUK_CTPRVN_CODES),
            "store_count": len(stores),
            "building_count": len(buildings),
            "buildings_queried": stats["queried"],
            "register_found": stats["register_found"],
            "register_missing": stats["register_missing"],
            "register_errors": stats["errors"],
            "commercial_floors_surveyed": stats["commercial_floors"],
            "vacancy_candidates": len(candidates),
            "vacancy_method": "층별 미등록 추론",
            "business_types": BUSINESS_TYPES,
            "sources": {
                "stores": "소상공인시장진흥공단_상가(상권)정보 API",
                "register": "국토교통부_건축HUB_건축물대장정보 서비스",
            },
            "service_key_mode": {
                "sangga": datagokr.SANGGA_KEY_ENV
                if os.environ.get(datagokr.SANGGA_KEY_ENV)
                else datagokr.SHARED_SERVICE_KEY_ENV,
                "register": datagokr.BLDRGST_KEY_ENV
                if os.environ.get(datagokr.BLDRGST_KEY_ENV)
                else datagokr.SHARED_SERVICE_KEY_ENV,
            },
            "sangga_base_url": sangga_api.base_url(),
            "bldrgst_base_url": building_register_api.base_url(),
        },
    )

    log("\n저장 완료 — {}".format(out_dir))
    log("  buildings.json    {:,}건".format(len(buildings_out)))
    log("  market_data.json  {:,}건".format(len(market)))
    log("  region_stats.json {:,}개 지역".format(len(region_stats["regions"])))
    log("\n서버를 재시작하면 RealSanggaProvider로 전환됩니다.")
    return 0


def _write(path: pathlib.Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
