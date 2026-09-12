"""
DataProvider 추상 인터페이스.

지금 단계에서는 MockDataProvider가 로컬 JSON 파일을 읽어 데이터를 제공한다.
이후 팀원이 실제 데이터(공공데이터포털, 내부 크롤링 DB 등)를 연동할 때는
DataProvider를 상속하는 새 클래스(RealDataProvider 등)를 만들어 아래 메서드들만
동일한 반환 스키마로 구현하면 된다. 라우터/스코어링 로직은 수정할 필요가 없다.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class DataProvider(ABC):
    @abstractmethod
    def get_region_stats(self) -> dict[str, Any]:
        """지역별 공실 집계. 개별 매물 데이터와 별도의 조사 모집단."""
        ...

    @abstractmethod
    def list_business_types(self) -> list[str]:
        ...

    @abstractmethod
    def list_buildings(self) -> list[dict[str, Any]]:
        """데모 시나리오 목록 (요약 정보만)."""
        ...

    @abstractmethod
    def get_building(self, building_id: str) -> Optional[dict[str, Any]]:
        """building.json 스키마를 따르는 단일 건물 진단 정보."""
        ...

    @abstractmethod
    def create_building_from_input(
        self,
        address: str,
        floor: Optional[int] = None,
        area_pyeong: Optional[float] = None,
        has_photo: bool = False,
    ) -> dict[str, Any]:
        """
        매물 입력 화면에서 사용자가 입력한 주소/평수/층수를 받아
        건물 진단 결과를 반환한다. 실제 연동 전까지는 입력값을 바탕으로
        미리 준비된 데모 시나리오 중 하나에 매핑한다.
        """
        ...

    @abstractmethod
    def get_market_data(self, building_id: str) -> dict[str, dict[str, Any]]:
        """
        business_type -> {foot_traffic_index, competition_saturation_index,
        demographic_fit_index, estimated_rent} 형태의 raw 시장 신호.
        """
        ...

    @abstractmethod
    def get_permits(self, business_type: str) -> list[str]:
        ...


class MockDataProvider(DataProvider):
    def __init__(self, data_dir: Path = DATA_DIR):
        self._data_dir = data_dir
        self._buildings: dict[str, Any] = json.loads((data_dir / "buildings.json").read_text(encoding="utf-8"))
        self._market_data: dict[str, Any] = json.loads((data_dir / "market_data.json").read_text(encoding="utf-8"))
        self._permits: dict[str, Any] = json.loads((data_dir / "permits.json").read_text(encoding="utf-8"))

    def list_business_types(self) -> list[str]:
        return list(self._permits.keys())

    def get_region_stats(self) -> dict[str, Any]:
        return json.loads((self._data_dir / "region_stats.json").read_text(encoding="utf-8"))

    def list_buildings(self) -> list[dict[str, Any]]:
        return [
            {
                "id": b["id"],
                "name": b["name"],
                "address": b["address"],
                "risk_grade": b["risk_grade"],
                "thumbnail_color": b.get("thumbnail_color", "#EEEEEE"),
            }
            for b in self._buildings.values()
        ]

    def get_building(self, building_id: str) -> Optional[dict[str, Any]]:
        return self._buildings.get(building_id)

    def create_building_from_input(
        self,
        address: str,
        floor: Optional[int] = None,
        area_pyeong: Optional[float] = None,
        has_photo: bool = False,
    ) -> dict[str, Any]:
        ids = list(self._buildings.keys())
        # 데모: 입력된 주소를 해시하여 시나리오 중 하나에 결정적으로 매핑한다.
        # 실연동 시에는 이 부분이 실제 진단 파이프라인(CV 모델 등) 호출로 대체된다.
        digest = hashlib.sha256(address.strip().encode("utf-8")).hexdigest()
        index = int(digest, 16) % len(ids)
        matched = self._buildings[ids[index]]

        building = dict(matched)
        building["address"] = address or matched["address"]
        if floor is not None:
            building["floor"] = floor
        if area_pyeong is not None:
            building["area_pyeong"] = area_pyeong
        building["matched_scenario_id"] = matched["id"]
        return building

    def get_market_data(self, building_id: str) -> dict[str, dict[str, Any]]:
        return self._market_data.get(building_id, {})

    def get_permits(self, business_type: str) -> list[str]:
        return self._permits.get(business_type, [])


_provider: DataProvider = MockDataProvider()


def get_data_provider() -> DataProvider:
    """FastAPI Depends()에서 사용할 provider 팩토리. 실데이터 전환 시 이 함수만 교체."""
    return _provider
