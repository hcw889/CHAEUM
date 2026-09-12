"""
실제 공실 매물 데이터 수집 — 소상공인 상가정보 API + 국토부 건축HUB 건축물대장 API.

두 API를 건물 단위로 조인해 "대장에는 상업용도인데 영업 점포가 0건인 층"을 찾아
매물 후보로 만든다. 판정 논리와 점수 계산은 app/services/vacancy_estimator.py에 있고,
이 스크립트는 호출/페이징/캐시 저장만 담당한다.

실행:
    cd backend
    python scripts/fetch_real_vacancies.py                    # 전북 전역
    python scripts/fetch_real_vacancies.py --max-buildings 300  # 쿼터 절약
    python scripts/fetch_real_vacancies.py --signgu 52111       # 특정 시군구만

사전 준비 — backend/.env에 공공데이터포털 일반 인증키(Decoding)를 넣는다:
    DATA_GO_KR_SERVICE_KEY=...

두 API 모두 같은 키를 쓰지만, 포털에서 각각 활용신청이 승인돼 있어야 한다:
    소상공인시장진흥공단_상가(상권)정보
    국토교통부_건축HUB_건축물대장정보 서비스

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
from app.services import building_register_api, datagokr, sangga_api, vacancy_estimator  # noqa: E402

OUT_DIR = BASE_DIR / "app" / "data" / "real"

BUSINESS_TYPES = ["카페", "학원", "병원", "편의점", "스터디카페"]

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


def collect_stores(ctprvn_cd: str, signgu_filter: Optional[str], max_pages: int) -> list[dict[str, Any]]:
    """전북 전역(또는 지정 시군구)의 점포를 모두 가져와 정규화한다."""
    if signgu_filter:
        div_id, key = "signguCd", signgu_filter
        log("상가정보 수집 — 시군구 {}".format(signgu_filter))
    else:
        div_id, key = "ctprvnCd", ctprvn_cd
        log("상가정보 수집 — 전북 시도코드 {}".format(ctprvn_cd))

    stores: list[dict[str, Any]] = []

    def progress(page: int, seen: int, total: int) -> None:
        if page % 10 == 0 or page == 1:
            log("  {}페이지 / 누적 {:,}건 (totalCount {:,})".format(page, seen, total))

    try:
        for raw in sangga_api.store_list_in_admi(
            div_id, key, rows=1000, max_pages=max_pages, progress=progress
        ):
            stores.append(sangga_api.normalize_store(raw))
    except datagokr.DataGoKrError as exc:
        if not stores:
            raise
        # 쿼터 초과로 중간에 끊겨도 모은 만큼으로 진행한다.
        log("  [경고] 수집이 중단되었습니다 ({}). 모은 {:,}건으로 계속합니다.".format(exc, len(stores)))

    log("상가정보 {:,}건 수집 완료".format(len(stores)))
    return stores


# --- 2단계: 건축물대장 조회 대상 선별 -------------------------------------------


def _candidate_priority(building: dict[str, Any]) -> tuple[int, int]:
    """
    건축물대장을 조회할 우선순위. 작은 값이 먼저.

    층이 찍힌 점포가 하나라도 있는 건물을 앞세운다 — 층 단위 공실 판정의
    신뢰도가 거기서 나온다. 그다음 점포 수가 적은 건물(빈 층이 있을 여지가 큰 건물).
    """
    floors = building.get("stores_by_floor", {})
    known_floors = sum(1 for floor in floors if floor is not None)
    return (0 if known_floors else 1, len(building.get("stores", ())))


def select_buildings(
    buildings: dict[str, dict[str, Any]], max_buildings: int
) -> list[dict[str, Any]]:
    """
    조회 대상 건물을 시군별로 비례 배분해 고른다.

    건축물대장은 건물당 2회(표제부+층별개요) 호출한다. 전북 전체 건물을 다 보면
    개발계정 일일 한도를 넘기므로 상한을 두고, 전주만 쏠리지 않게 시군별로 나눈다.
    """
    usable = [
        b
        for b in buildings.values()
        if b.get("register_params") and b.get("lat") is not None and b.get("lng") is not None
    ]
    log("건물 {:,}개 중 지번/좌표가 온전한 {:,}개가 조회 가능".format(len(buildings), len(usable)))

    by_signgu: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for building in usable:
        by_signgu[building.get("signgu_name") or building.get("signgu_cd") or "미상"].append(building)

    if len(usable) <= max_buildings:
        selected = usable
    else:
        selected = []
        total = len(usable)
        for signgu, group in sorted(by_signgu.items()):
            group.sort(key=_candidate_priority)
            quota = max(10, round(max_buildings * len(group) / total))
            selected.extend(group[:quota])
        selected = selected[:max_buildings]

    log("건축물대장 조회 대상 {:,}개 건물 (약 {:,}회 호출)".format(len(selected), len(selected) * 2))
    return selected


# --- 3단계: 건축물대장 조회 + 공실 판정 ------------------------------------------


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
        probed = building_register_api.probe_base_url(selected[0]["register_params"])
        log("건축물대장 base_url: {}".format(probed or "확인 실패 — 기본값으로 진행"))

    for position, building in enumerate(selected, start=1):
        if position % 25 == 0:
            log(
                "  건축물대장 {}/{} — 대장 확인 {} / 공실후보 {}".format(
                    position, len(selected), stats["register_found"], stats["vacant_candidates"]
                )
            )

        stats["queried"] += 1
        try:
            register = building_register_api.fetch_building(building["register_params"])
        except datagokr.DataGoKrError as exc:
            stats["errors"] += 1
            message = str(exc)
            if "LIMIT" in message.upper() or "초과" in message:
                log("  [중단] 일일 호출 한도에 걸렸습니다: {}".format(message))
                break
            continue
        except Exception as exc:  # 네트워크/타임아웃 — 건물 단위로 건너뛴다
            stats["errors"] += 1
            if stats["errors"] <= 5:
                log("  [건너뜀] {} — {}".format(building.get("jibun_address") or building["key"], exc))
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
            lat, lng = 35.8242, 127.1480  # 전주시청 — 좌표를 못 구한 시군의 대표점

        regions.append(
            {
                "id": SIGNGU_TO_REGION_ID.get(signgu.replace(" ", ""), _slug(signgu)),
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
        region_id = SIGNGU_TO_REGION_ID.get(
            (candidate.get("signgu_name") or "").replace(" ", ""), _slug(candidate.get("signgu_name") or "미상")
        )
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
    parser.add_argument("--signgu", default=None, help="특정 시군구코드만 수집 (예: 52111)")
    parser.add_argument(
        "--max-store-pages", type=int, default=400, help="상가정보 최대 페이지 수 (1000건/페이지)"
    )
    parser.add_argument("--sleep", type=float, default=0.12, help="건축물대장 호출 간 대기 초")
    parser.add_argument("--out", default=str(OUT_DIR), help="출력 디렉터리")
    return parser.parse_args()


def main() -> int:
    _utf8_stdout()
    args = parse_args()

    if not datagokr.has_service_key():
        log("{}가 없습니다. backend/.env에 공공데이터포털 일반 인증키(Decoding)를 넣으세요.".format(
            datagokr.SERVICE_KEY_ENV
        ))
        return 1

    today = date.today()
    started = datetime.now()

    ctprvn_cd = args.signgu or sangga_api.resolve_jeonbuk_ctprvn_code()
    if ctprvn_cd is None:
        log(
            "상가정보 API에서 전북 데이터를 찾지 못했습니다.\n"
            "  - 포털에서 '소상공인시장진흥공단_상가(상권)정보' 활용신청이 승인됐는지\n"
            "  - 인증키가 Decoding 값인지 확인하세요."
        )
        return 1

    stores = collect_stores(
        ctprvn_cd if not args.signgu else ctprvn_cd, args.signgu, args.max_store_pages
    )
    if not stores:
        log("수집된 점포가 없습니다.")
        return 1

    buildings = sangga_api.group_by_building(stores)
    index = vacancy_estimator.StoreIndex(stores)
    log("좌표가 있는 점포 {:,}건으로 공간 인덱스 구성".format(len(index)))

    selected = select_buildings(buildings, args.max_buildings)
    candidates, stats = fetch_registers(selected, today, args.sleep)

    if not candidates:
        log(
            "공실 후보를 찾지 못했습니다.\n"
            "  대장 확인 {} / 대장 미등재 {} / 오류 {}\n"
            "  --max-buildings를 늘리거나 --signgu로 도심 시군구를 지정해 보세요.".format(
                stats["register_found"], stats["register_missing"], stats["errors"]
            )
        )
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
            "ctprvn_cd": ctprvn_cd,
            "signgu_filter": args.signgu,
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
