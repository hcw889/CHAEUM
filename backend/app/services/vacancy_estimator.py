"""
공실 추정 엔진 — 상가정보 API와 건축물대장 API를 건물 단위로 조인한다.

## 왜 추정인가

두 API 모두 "공실" 필드가 없다. 상가정보는 영업 중인 점포만, 건축물대장은
건물 제원만 준다. 그래서 아래 논리로 공실 후보를 만든다:

    건축물대장 층별개요에 근린생활시설/판매시설로 등재된 층
      AND 상가정보에 그 층의 등록 점포가 0건
    -> 공실 후보

이것은 확정된 공실이 아니다. 틀릴 수 있는 경로가 분명히 있다:
  - 상가정보는 분기 스냅샷이라 신규 개업 점포가 아직 안 들어왔을 수 있다
  - 사업자등록 주소의 층 표기(flrNo)가 비어 있거나 실제와 다를 수 있다
  - 대장상 근린생활시설이지만 자가 사용(사무실/창고)인 층일 수 있다

그래서 모든 후보에 confidence와 basis(판정 근거)를 붙이고, 화면에도
"추정"임을 표시한다 (get_data_sources 참고).

## 실데이터 / 추정 구분

실데이터:
  built_year        <- 건축물대장 사용승인일
  area_pyeong       <- 건축물대장 층별 전용면적
  floor / 용도      <- 건축물대장 층별개요
  aging_score       <- 사용승인일 기반 계산
  accessibility     <- 승강기 대수 + 층수 기반 계산
  경쟁포화도        <- 상가정보 반경 내 동일업종 실제 점포 수

추정(실데이터 없음):
  lighting_score    <- 층/구조 기반 휴리스틱
  demographic_fit   <- 인근 업종 구성 기반 프록시
  estimated_rent    <- 면적 x 지역 기준단가 x 층 계수
  foot_traffic      <- 상가 밀도 프록시 (SK 유동인구 API는 별도 flow)
"""

from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Any, Iterable, Optional

PYEONG_PER_SQM = 3.305785

# 경쟁포화도/유동인구 프록시를 계산할 반경.
COMPETITION_RADIUS_M = 300
# 반경 내 전체 점포 수를 유동인구 프록시로 쓸 때의 상한 기준.
# 이 값에서 100점이 되도록 선형 정규화한다 (전북 도심 상권 밀도 기준).
FOOTFALL_PROXY_REFERENCE = 180

# 업종 -> 상가정보 업종명 매칭 키워드. 상가정보의 indsSclsNm/indsMclsNm은
# 표기가 자주 바뀌므로 코드가 아니라 이름 부분 문자열로 맞춘다.
BUSINESS_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "카페": ("커피", "카페", "다방", "비알콜", "제과", "베이커리"),
    "학원": ("학원", "교습", "교육서비스", "보습"),
    "병원": ("병원", "의원", "치과", "한의원", "보건"),
    "편의점": ("편의점", "체인화편의점"),
    "스터디카페": ("독서실", "스터디"),
}

# demographic_fit 프록시: 해당 업종 수요와 같이 움직이는 인근 업종 키워드.
# "주변에 이런 업종이 많으면 그 업종 고객층이 실제로 있다"는 약한 신호다.
DEMAND_COMPANION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "카페": ("음식점", "의류", "화장품", "미용", "서점"),
    "학원": ("학원", "문구", "서점", "독서실", "분식"),
    "병원": ("약국", "병원", "의원", "한의원"),
    "편의점": ("주택", "부동산", "세탁", "미용", "음식점"),
    "스터디카페": ("학원", "독서실", "커피", "문구", "서점"),
}

# 시군별 1평당 월 임대료 기준단가(원). 실데이터가 아니라 시연용 가정값이다.
# 실제 임대 시세 API(국토부 상업용부동산 임대정보 등)를 붙이면 이 표가 사라진다.
RENT_PER_PYEONG_BY_SIGNGU: dict[str, int] = {
    "전주시완산구": 72000,
    "전주시덕진구": 68000,
    "군산시": 55000,
    "익산시": 52000,
    "정읍시": 42000,
    "남원시": 40000,
    "김제시": 38000,
    "완주군": 40000,
    "진안군": 30000,
    "무주군": 30000,
    "장수군": 28000,
    "임실군": 28000,
    "순창군": 28000,
    "고창군": 32000,
    "부안군": 32000,
}
DEFAULT_RENT_PER_PYEONG = 45000

# 층별 임대료 계수. 1층이 가장 비싸고 지하/고층이 싸다는 상가 임대 관행.
FLOOR_RENT_FACTOR = {1: 1.0, 2: 0.55, 3: 0.42, -1: 0.45}
DEFAULT_UPPER_FLOOR_FACTOR = 0.35


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


# --- 공간 인덱스 ---------------------------------------------------------------


class StoreIndex:
    """
    반경 내 점포 수를 빠르게 세기 위한 격자 인덱스.

    전북 전역이면 점포가 10만 건을 넘어서, 후보 건물마다 전체를 훑으면
    수집 스크립트가 끝나지 않는다. 0.01도(약 1.1km) 격자에 담고 인접 칸만 본다.
    """

    CELL_DEG = 0.01

    def __init__(self, stores: Iterable[dict[str, Any]]):
        self._cells: dict[tuple[int, int], list[dict[str, Any]]] = {}
        self._count = 0
        for store in stores:
            lat, lng = store.get("lat"), store.get("lng")
            if lat is None or lng is None:
                continue
            self._cells.setdefault(self._cell(lat, lng), []).append(store)
            self._count += 1

    def __len__(self) -> int:
        return self._count

    @classmethod
    def _cell(cls, lat: float, lng: float) -> tuple[int, int]:
        return (int(math.floor(lat / cls.CELL_DEG)), int(math.floor(lng / cls.CELL_DEG)))

    def nearby(self, lat: float, lng: float, radius_m: int) -> list[dict[str, Any]]:
        """반경 내 점포 목록. 격자 한 칸이 약 1.1km이므로 인접 1칸까지 본다."""
        span = max(1, int(math.ceil((radius_m / 111_000.0) / self.CELL_DEG)))
        base_lat, base_lng = self._cell(lat, lng)

        result = []
        for d_lat in range(-span, span + 1):
            for d_lng in range(-span, span + 1):
                for store in self._cells.get((base_lat + d_lat, base_lng + d_lng), ()):
                    if _haversine_m(lat, lng, store["lat"], store["lng"]) <= radius_m:
                        result.append(store)
        return result


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


# --- 업종 매칭 ----------------------------------------------------------------


def _store_industry_text(store: dict[str, Any]) -> str:
    return " ".join(
        str(store.get(field) or "")
        for field in ("inds_small", "inds_middle", "inds_large")
    )


def matches_business_type(store: dict[str, Any], business_type: str) -> bool:
    """
    점포가 해당 업종인지. 등록된 5개 업종은 키워드 표를 쓰고,
    커스텀 입력(예: "베이커리")은 입력값 자체를 부분 문자열로 찾는다.
    """
    keywords = BUSINESS_TYPE_KEYWORDS.get(business_type)
    text = _store_industry_text(store)
    if keywords:
        return any(keyword in text for keyword in keywords)
    stripped = business_type.strip()
    return bool(stripped) and stripped in text


def count_competitors(
    index: StoreIndex, lat: float, lng: float, business_type: str, radius_m: int = COMPETITION_RADIUS_M
) -> tuple[int, int]:
    """(동일업종 점포 수, 전체 점포 수) — 둘 다 반경 내 실측값."""
    nearby = index.nearby(lat, lng, radius_m)
    same = sum(1 for store in nearby if matches_business_type(store, business_type))
    return same, len(nearby)


# --- 조회 대상 선별 -------------------------------------------------------------


def candidate_priority(building: dict[str, Any]) -> tuple[int, int]:
    """
    건축물대장을 조회할 우선순위. 작은 값이 먼저.

    공실 판정의 신뢰도(assess_floor_vacancy)가 그대로 등급이 되도록,
    신뢰도가 높게 나올 수 있는 건물부터 조회한다:

      0순위  층 표기 없는 점포 0건 + 층이 찍힌 점포 2건 이상 -> 신뢰도 높음 가능
      1순위  층 표기 없는 점포 0건 + 층이 찍힌 점포 1건      -> 보통
      2순위  층 표기 없는 점포가 있는 건물                   -> 낮음

    점포 수가 적은 건물만 앞세우면 1개 점포 건물만 뽑혀서 모든 매물이 '보통'으로
    고정된다 — 실수집에서 125건 전부 보통으로 나와 확인한 문제다. 같은 순위
    안에서는 점포가 적은 건물(빈 층이 있을 여지가 큰 건물)을 먼저 본다.

    사전 수집 스크립트(scripts/fetch_real_vacancies.py)와 런타임 라이브 검색
    (live_search.py)이 같은 기준으로 뽑아야 두 경로의 결과가 어긋나지 않는다.
    """
    by_floor = building.get("stores_by_floor", {})
    unknown = len(by_floor.get(None, ()))
    known = sum(len(stores) for floor, stores in by_floor.items() if floor is not None)

    if unknown:
        tier = 2
    elif known >= 2:
        tier = 0
    elif known == 1:
        tier = 1
    else:
        tier = 2
    return (tier, len(building.get("stores", ())))


# --- 진단 점수 ----------------------------------------------------------------


def aging_score(built_year: Optional[int], *, today: Optional[date] = None) -> float:
    """
    노후도 점수 (높을수록 양호). 건축물대장 사용승인일 기반 — 실데이터.
    연 1.4점씩 감점하며 하한 5점. 승인일이 없으면 중립 50점.
    """
    if not built_year:
        return 50.0
    year = (today or date.today()).year
    age = max(0, year - built_year)
    return round(_clamp(100 - age * 1.4, 5, 100), 1)


def accessibility_score(floor: int, title: dict[str, Any]) -> float:
    """
    접근성 점수. 층수와 승강기 대수 기반 — 건축물대장 실데이터에서 파생.
    1층은 보행 접근이 직접 가능해 최고점, 지하/고층은 승강기 유무가 크게 갈린다.
    """
    elevators = int(title.get("elevators") or 0)

    if floor == 1:
        score = 95.0
    elif floor == 2:
        score = 75.0 if elevators else 62.0
    elif floor >= 3:
        penalty = (floor - 2) * (4 if elevators else 9)
        score = (78.0 if elevators else 58.0) - penalty
    else:  # 지하
        score = (60.0 if elevators else 42.0) + (floor + 1) * 8

    return round(_clamp(score, 5, 100), 1)


def lighting_score(floor: int, title: dict[str, Any], area_sqm: float) -> float:
    """
    채광 점수 — 추정값이다. 두 API에 창호/향/일조 정보가 없다.
    층(지상일수록 유리), 건물 높이 대비 층 위치, 바닥면적(깊은 평면은 불리)으로
    만든 휴리스틱이며 결정적(deterministic)이다.
    """
    if floor < 0:
        score = 25.0 + (floor + 1) * 5  # 지하는 기본적으로 낮다
    elif floor == 1:
        score = 70.0  # 전면 유리가 많지만 주변 건물 그림자를 받는다
    else:
        score = min(88.0, 68.0 + floor * 3.5)

    ground_floors = int(title.get("ground_floors") or 0)
    if ground_floors and floor > 0 and floor == ground_floors:
        score += 6.0  # 최상층은 채광이 유리

    if area_sqm > 200:
        score -= 8.0  # 면적이 크면 평면 안쪽까지 빛이 안 든다

    return round(_clamp(score, 5, 100), 1)


def risk_grade(condition_score: float) -> str:
    if condition_score >= 70:
        return "낮음"
    if condition_score >= 50:
        return "보통"
    return "높음"


# --- 공실 판정 ----------------------------------------------------------------


def _floor_store_count(building: dict[str, Any], floor: int) -> int:
    return len(building.get("stores_by_floor", {}).get(floor, ()))


def _unknown_floor_store_count(building: dict[str, Any]) -> int:
    """층 표기(flrNo)가 비어 있는 점포 수. 많으면 층 단위 판정 신뢰도가 떨어진다."""
    return len(building.get("stores_by_floor", {}).get(None, ()))


def assess_floor_vacancy(building: dict[str, Any], floor_info: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    한 층이 공실 후보인지 판정한다. 후보가 아니면 None.

    Args:
        building: sangga_api.group_by_building()의 항목 (상가정보 쪽)
        floor_info: building_register_api.parse_floors()의 항목 (대장 쪽)
    """
    if not floor_info.get("is_commercial") or floor_info.get("is_non_leasable"):
        return None
    if (floor_info.get("area") or 0) <= 0:
        return None  # 면적 미기재 층은 평수를 못 내므로 매물로 내보내지 않는다

    floor = floor_info["floor"]
    floor_stores = _floor_store_count(building, floor)
    if floor_stores > 0:
        return None  # 영업 점포가 있으므로 공실이 아니다

    total_stores = len(building.get("stores", ()))
    unknown_floor = _unknown_floor_store_count(building)
    known_floor_stores = total_stores - unknown_floor

    # 신뢰도는 "층 단위로 볼 수 있는 건물인가"로 결정한다.
    #
    # 실수집 측정값이 기준이다: 상가정보의 flrNo는 절반(50.3%)이 비어 있고,
    # 건물관리번호로 묶은 건물의 점포 수는 평균 1.8건이다. 그래서 "층이 찍힌 점포
    # 3건 이상"을 높음으로 잡으면 사실상 아무 매물도 높음이 되지 않는다.
    #
    # 층 표기가 없는 점포가 하나라도 있으면 그 점포가 바로 이 층에 있을 수 있으므로
    # 낮음이다. 그게 이 추정의 가장 큰 오판 경로다.
    if unknown_floor > 0:
        confidence = "low"
    elif known_floor_stores >= 2:
        # 서로 다른 층에 점포가 찍혀 있으면 층 구분이 실제로 기록되는 건물이라는 뜻이다.
        confidence = "high"
    elif known_floor_stores == 1:
        confidence = "medium"
    else:
        confidence = "low"

    basis = [
        "건축물대장 {} 용도: {}".format(floor_info["floor_label"], floor_info["purpose"] or "용도 미기재"),
        "상가정보 해당 층 등록 점포 0건 (건물 전체 {}건)".format(total_stores),
    ]
    if unknown_floor:
        basis.append("층 표기가 없는 점포 {}건이 있어 실제로는 영업 중일 수 있음".format(unknown_floor))

    return {
        "estimated": True,
        "confidence": confidence,
        "method": "층별 미등록 추론",
        "basis": basis,
        "register_purpose": floor_info.get("purpose") or "",
        "floor_label": floor_info["floor_label"],
        "floor_area_sqm": floor_info["area"],
        "building_store_count": total_stores,
        "floor_store_count": 0,
        "unknown_floor_store_count": unknown_floor,
    }


# --- 매물 레코드 생성 ----------------------------------------------------------


def _building_id(building_key: str, floor: int) -> str:
    """건물키+층으로 안정적인 짧은 id. 재수집해도 같은 층이면 같은 id가 나온다."""
    digest = hashlib.sha256("{}#{}".format(building_key, floor).encode("utf-8")).hexdigest()
    return "r" + digest[:10]


def _display_name(building: dict[str, Any], floor_label: str) -> str:
    name = (building.get("bld_name") or "").strip()
    if not name:
        name = (building.get("ldong_name") or building.get("adong_name") or "상가").strip() + " 상가"
    return "{} {}".format(name, floor_label)


def _address(building: dict[str, Any], floor_label: str) -> str:
    base = (building.get("road_address") or building.get("jibun_address") or "").strip()
    if not base:
        return floor_label
    return "{} {}".format(base, floor_label)


def _thumbnail_color(building_id: str) -> str:
    """id에서 뽑은 결정적 파스텔 색. 사진이 없는 매물의 플레이스홀더 배경."""
    digest = hashlib.sha256(building_id.encode("utf-8")).digest()
    return "#{:02X}{:02X}{:02X}".format(
        200 + digest[0] % 40, 195 + digest[1] % 45, 190 + digest[2] % 50
    )


def _region_label(building: dict[str, Any]) -> str:
    """region_pref 매칭에 쓰는 지역명. 법정동명을 우선하고 없으면 행정동/시군."""
    for field in ("ldong_name", "adong_name", "signgu_name"):
        value = (building.get(field) or "").strip()
        if value:
            return value
    return ""


def estimated_rent(signgu_name: str, area_pyeong: float, floor: int) -> int:
    """면적 x 시군 기준단가 x 층 계수. 실 시세 데이터가 없는 추정값이다."""
    unit = RENT_PER_PYEONG_BY_SIGNGU.get(signgu_name.replace(" ", ""), DEFAULT_RENT_PER_PYEONG)
    factor = FLOOR_RENT_FACTOR.get(floor, DEFAULT_UPPER_FLOOR_FACTOR)
    value = unit * max(1.0, area_pyeong) * factor
    return int(round(value / 10_000) * 10_000)  # 만원 단위로 정리


def _demographic_fit(index: StoreIndex, lat: float, lng: float, business_type: str) -> float:
    """
    인구통계 적합도 프록시 — 추정값.
    반경 내 '보완 업종' 비중이 높을수록 그 업종 고객층이 있다고 본다.
    """
    keywords = DEMAND_COMPANION_KEYWORDS.get(business_type)
    nearby = index.nearby(lat, lng, COMPETITION_RADIUS_M)
    if not nearby:
        return 45.0
    if not keywords:
        return 50.0

    hits = sum(
        1 for store in nearby if any(keyword in _store_industry_text(store) for keyword in keywords)
    )
    ratio = hits / len(nearby)
    # 보완업종 비중 30%면 만점에 가깝게 본다.
    return round(_clamp(35 + ratio * 200, 20, 95), 1)


def _footfall_proxy(total_nearby: int) -> float:
    """상가 밀도 기반 유동인구 프록시 — 추정값 (SK 유동인구 API는 별도 flow)."""
    return round(_clamp(100 * total_nearby / FOOTFALL_PROXY_REFERENCE, 10, 100), 1)


def build_market_entry(
    index: StoreIndex,
    lat: Optional[float],
    lng: Optional[float],
    business_type: str,
    signgu_name: str,
    area_pyeong: float,
    floor: int,
    saturation_reference: Optional[int] = None,
) -> dict[str, Any]:
    """
    한 매물/업종 조합의 raw 시장 신호. 기존 market_data.json과 같은 4개 키를 낸다
    (scoring.py / matching_agents.py를 수정 없이 재사용하기 위함).

    Args:
        saturation_reference: 경쟁포화도 100점에 해당하는 동일업종 점포 수.
            None이면 업종별 기본값을 쓴다. 수집 스크립트가 데이터 전체의
            90분위수를 넣어 준다.
    """
    rent = estimated_rent(signgu_name, area_pyeong, floor)

    if lat is None or lng is None:
        return {
            "foot_traffic_index": 45,
            "competition_saturation_index": 50,
            "demographic_fit_index": 45,
            "estimated_rent": rent,
            "competitor_count": None,
            "nearby_store_count": None,
        }

    same, total = count_competitors(index, lat, lng, business_type)
    reference = saturation_reference or 8
    saturation = _clamp(100 * same / max(1, reference), 0, 100)

    return {
        "foot_traffic_index": _footfall_proxy(total),
        "competition_saturation_index": round(saturation, 1),
        "demographic_fit_index": _demographic_fit(index, lat, lng, business_type),
        "estimated_rent": rent,
        "competitor_count": same,
        "nearby_store_count": total,
    }


def build_candidate(
    building: dict[str, Any],
    register: dict[str, Any],
    floor_info: dict[str, Any],
    vacancy: dict[str, Any],
    *,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """
    공실 후보 1건을 buildings.json과 동일한 스키마로 만든다.
    기존 라우터/스코어링이 그대로 읽을 수 있어야 한다.
    """
    title = register["title"]
    floor = floor_info["floor"]
    area_sqm = floor_info["area"]
    area_pyeong = round(area_sqm / PYEONG_PER_SQM, 1)

    building_id = _building_id(building["key"], floor)
    built_year = title.get("approval_year")

    diagnosis = {
        "aging_score": aging_score(built_year, today=today),
        "accessibility_score": accessibility_score(floor, title),
        "lighting_score": lighting_score(floor, title, area_sqm),
    }
    condition = sum(diagnosis.values()) / 3

    return {
        "id": building_id,
        "name": _display_name(building, vacancy["floor_label"]),
        "address": _address(building, vacancy["floor_label"]),
        "floor": floor,
        "area_pyeong": area_pyeong,
        "area_sqm": round(area_sqm, 2),
        "built_year": built_year or 0,
        "risk_grade": risk_grade(condition),
        "region": _region_label(building),
        "signgu_name": (building.get("signgu_name") or "").strip(),
        "thumbnail_color": _thumbnail_color(building_id),
        "diagnosis": diagnosis,
        "data_reference_month": (today or date.today()).strftime("%Y-%m"),
        "lat": building.get("lat"),
        "lng": building.get("lng"),
        "vacancy": vacancy,
        "register": {
            "mgm_bldrgst_pk": title.get("mgm_bldrgst_pk", ""),
            "bld_mng_no": building.get("bld_mng_no", ""),
            "structure": title.get("structure", ""),
            "elevators": title.get("elevators", 0),
            "ground_floors": title.get("ground_floors", 0),
            "underground_floors": title.get("underground_floors", 0),
            "total_area": title.get("total_area"),
            "main_purpose": title.get("main_purpose", ""),
            "register_params": register.get("register_params", {}),
        },
        "nearby_store_names": [
            store.get("name", "") for store in building.get("stores", ())[:8] if store.get("name")
        ],
    }


def candidates_for_building(
    building: dict[str, Any],
    register: dict[str, Any],
    *,
    today: Optional[date] = None,
) -> list[dict[str, Any]]:
    """한 건물의 모든 층을 훑어 공실 후보 레코드들을 만든다."""
    results = []
    for floor_info in register.get("floors", ()):
        vacancy = assess_floor_vacancy(building, floor_info)
        if vacancy is None:
            continue
        results.append(build_candidate(building, register, floor_info, vacancy, today=today))
    return results


def saturation_references(
    index: StoreIndex,
    candidates: Iterable[dict[str, Any]],
    business_types: Iterable[str],
) -> dict[str, int]:
    """
    업종별 '경쟁포화도 100점' 기준 점포 수를 데이터에서 뽑는다.
    후보 위치들의 동일업종 점포 수 분포에서 90분위수를 쓴다 — 임의 상수보다
    지역 실정을 반영한다.
    """
    references: dict[str, int] = {}
    located = [c for c in candidates if c.get("lat") is not None and c.get("lng") is not None]

    for business_type in business_types:
        counts = sorted(
            count_competitors(index, c["lat"], c["lng"], business_type)[0] for c in located
        )
        if not counts:
            references[business_type] = 8
            continue
        position = int(0.9 * (len(counts) - 1))
        references[business_type] = max(1, counts[position])
    return references
