"""
buildings.json의 address를 카카오 로컬 API로 좌표(lat/lng)로 변환해 채운다.

런타임에 매 요청마다 지오코딩하면 느리고 쿼터를 낭비하므로, 이 스크립트를 한 번
실행해 좌표를 데이터에 박아 넣고 결과를 커밋한다. 좌표는 로드뷰 파노라마를 찾는
데 쓰인다 (frontend/components/RoadviewPanel.tsx).

실행:
    cd backend && python scripts/geocode_buildings.py

이미 lat/lng가 있는 매물은 건너뛴다. 검색이 실패한 주소는 [실패]로 출력되므로,
카카오맵에서 직접 찍은 좌표를 buildings.json에 수동으로 넣으면 된다.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import httpx

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "app" / "data" / "buildings.json"

ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def _load_key() -> str:
    """환경변수 우선, 없으면 backend/.env에서 직접 읽는다 (dotenv 미설치 대응)."""
    key = (os.environ.get("KAKAO_REST_API_KEY") or "").strip()
    if key:
        return key

    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "KAKAO_REST_API_KEY":
                return value.strip().strip("\"'")

    sys.exit("KAKAO_REST_API_KEY가 없습니다. backend/.env에 설정하세요.")


def geocode(client: httpx.Client, address: str) -> tuple[float, float] | None:
    """
    (lat, lng) 또는 None.

    도로명/지번 주소 검색을 먼저 시도하고, 결과가 없으면 키워드 검색으로 재시도한다.
    '객사길 45' 처럼 건물명이 없는 주소는 주소 검색이 맞고, '전주 한옥마을 OO상가'
    처럼 상호가 섞인 값은 키워드 검색이 맞기 때문이다.
    """
    for url in (ADDRESS_URL, KEYWORD_URL):
        response = client.get(url, params={"query": address})
        if response.status_code == 401:
            sys.exit("401: REST API 키가 잘못되었습니다.")
        if response.status_code == 403:
            sys.exit(
                "403: 앱에서 카카오맵 서비스가 비활성 상태입니다.\n"
                "  Kakao Developers > 내 애플리케이션 > 제품 설정 > 카카오맵 > 활성화 ON"
            )
        response.raise_for_status()

        documents = response.json().get("documents") or []
        if documents:
            first = documents[0]
            return float(first["y"]), float(first["x"])  # y=위도, x=경도

    return None


def main() -> int:
    # Windows 콘솔 기본 코드페이지(cp949)에서는 em-dash 등이 인코딩되지 않아
    # print가 UnicodeEncodeError로 죽는다. 출력 스트림을 UTF-8로 바꾼다.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass

    key = _load_key()
    buildings: dict[str, dict] = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    failed: list[str] = []
    filled = 0

    with httpx.Client(
        headers={"Authorization": f"KakaoAK {key}"}, timeout=10.0
    ) as client:
        for building_id, building in buildings.items():
            if building.get("lat") is not None and building.get("lng") is not None:
                print(f"[건너뜀] {building_id} — 좌표 있음")
                continue

            address = building.get("address", "")
            coord = geocode(client, address)
            if coord is None:
                print(f"[실패]   {building_id} {address}")
                failed.append(f"{building_id} ({address})")
                continue

            building["lat"], building["lng"] = coord
            filled += 1
            print(f"[성공]   {building_id} {address} → {coord[0]:.6f}, {coord[1]:.6f}")
            time.sleep(0.1)  # 쿼터 여유를 둔다

    if filled:
        DATA_PATH.write_text(
            json.dumps(buildings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n{DATA_PATH.name}에 {filled}건 저장")

    if failed:
        print(f"\n좌표를 못 찾은 {len(failed)}건 — 수동 입력이 필요합니다:")
        for item in failed:
            print(f"  - {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
