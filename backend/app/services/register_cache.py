"""
건축물대장 응답의 영구 디스크 캐시 + 호출 속도 제한.

## 왜 필요한가

라이브 검색 1회는 건물 60개 x 2콜(표제부+층별개요) = 120콜이다. 공공데이터포털
개발계정은 이걸 그대로 받아 주지 않는다 — 동시 8콜로 던지면 429가 쏟아지고,
datagokr의 지수 백오프(2/4/8초)가 겹쳐 검색 한 번이 68초까지 늘어난다(실측).

그런데 대장이 주는 값(사용승인일, 층별 용도/전용면적, 승강기, 구조)은 준공 이후
거의 바뀌지 않는다. 반면 공실 판정의 실제 신호인 "그 층에 영업 점포가 있는가"는
상가정보 쪽에서 오고, 그쪽은 매 검색마다 새로 부른다. 그래서 대장만 영구 캐시해도
공실 판정의 신선도는 떨어지지 않으면서 호출이 사실상 사라진다.

  첫 검색   대장 120콜 (속도 제한 적용, 20초 안팎)
  재검색    대장 0콜   (같은 건물은 디스크에서)

## 저장소

stdlib sqlite3. 파일 하나라 3천 개짜리 디렉터리를 만들지 않고, WAL 모드라
요청 스레드들이 같이 써도 안전하다. 캐시를 지우려면 파일만 지우면 된다.

수집 스크립트(scripts/fetch_real_vacancies.py)도 같은 캐시를 쓰므로, 한 번
수집해 둔 지역은 라이브 검색 첫 회부터 빠르다.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_PATH = CACHE_DIR / "register.sqlite3"

# 대장은 준공 이후 거의 바뀌지 않는다. 그래도 증축/용도변경이 있으므로 만료는 둔다.
TTL_DAYS = 90

# 캐시에는 원본 응답이 아니라 building_register_api.fetch_building()이 **파싱한 결과**
# (층별 is_commercial/is_non_leasable/area 포함)가 들어간다. 그래서 파서·용도 판정
# 규칙을 바꾸면 옛 항목은 옛 판정을 그대로 돌려준다 — 실수집에서 "보일러실" 층이
# 계속 공실 후보로 나온 원인이다. parse_floors/용도 키워드를 바꿀 때 이 값을 올린다.
PARSER_VERSION = 2

# 건물 1개(=표제부+층별개요 2콜)를 시작하기 전 최소 간격(초). 초당 10콜 언저리로,
# 개발계정에서 429가 나기 시작하는 지점 아래다 — 워커 4개 x 이 간격으로 건물 60개
# (120콜)를 429 없이 15~20초에 통과하는 것을 실측했다. 제한 없이 던지면 429
# 백오프(2/4/8초)가 겹쳐 같은 검색이 68초까지 늘어난다.
MIN_INTERVAL_SEC = 0.2


class RateLimiter:
    """acquire() 사이의 최소 간격을 보장한다. 스레드풀 워커들이 공유한다."""

    def __init__(self, min_interval: float):
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + self._min_interval
        if wait > 0:
            time.sleep(wait)


limiter = RateLimiter(MIN_INTERVAL_SEC)

_conn_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _connect() -> sqlite3.Connection:
    global _conn
    with _conn_lock:
        if _conn is None:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False + WAL: 요청 스레드/스레드풀에서 같이 쓴다.
            conn = sqlite3.connect(CACHE_PATH, check_same_thread=False, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS register ("
                "  key TEXT PRIMARY KEY,"
                "  fetched_at TEXT NOT NULL,"
                "  payload TEXT"  # NULL이 아니라 'null' 문자열로 '대장 미등재'도 캐시한다
                ")"
            )
            conn.commit()
            _conn = conn
        return _conn


def cache_key(params: dict[str, str]) -> str:
    """대장 조회 파라미터(시군구/법정동/대지구분/번/지)에 파서 버전을 붙여 키로 쓴다."""
    return "v{}|".format(PARSER_VERSION) + "|".join(
        "{}={}".format(k, params[k]) for k in sorted(params)
    )


def get(params: dict[str, str]) -> tuple[bool, Optional[dict[str, Any]]]:
    """
    Returns:
        (적중 여부, 대장 데이터 또는 None). 적중이면서 값이 None이면 "대장 미등재"가
        캐시된 경우다 — 그 건물을 매번 다시 물어보지 않기 위해 그것도 저장한다.
    """
    try:
        row = _connect().execute(
            "SELECT fetched_at, payload FROM register WHERE key = ?", (cache_key(params),)
        ).fetchone()
    except sqlite3.Error as exc:
        logger.debug("대장 캐시 조회 실패: %s", exc)
        return False, None

    if row is None:
        return False, None

    fetched_at, payload = row
    try:
        if datetime.fromisoformat(fetched_at) < datetime.now() - timedelta(days=TTL_DAYS):
            return False, None
    except ValueError:
        return False, None

    return True, json.loads(payload)


def put(params: dict[str, str], value: Optional[dict[str, Any]]) -> None:
    try:
        conn = _connect()
        with _conn_lock:
            conn.execute(
                "INSERT OR REPLACE INTO register (key, fetched_at, payload) VALUES (?, ?, ?)",
                (cache_key(params), datetime.now().isoformat(timespec="seconds"), json.dumps(value)),
            )
            conn.commit()
    except (sqlite3.Error, TypeError) as exc:
        # 캐시 실패는 기능 실패가 아니다. 다음 검색이 다시 부르면 그만이다.
        logger.debug("대장 캐시 저장 실패: %s", exc)


def get_or_fetch(
    params: dict[str, str],
    fetch: Callable[[dict[str, str]], Optional[dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    """캐시에 있으면 그대로, 없으면 속도 제한을 걸고 fetch한 뒤 저장한다."""
    hit, value = get(params)
    if hit:
        return value

    limiter.acquire()
    value = fetch(params)
    put(params, value)
    return value


def stats() -> dict[str, Any]:
    try:
        (count,) = _connect().execute("SELECT COUNT(*) FROM register").fetchone()
    except sqlite3.Error:
        count = 0
    return {"path": str(CACHE_PATH), "entries": count, "ttl_days": TTL_DAYS}
