"""
공공데이터포털(data.go.kr) 공통 호출 헬퍼.

소상공인시장진흥공단 상가(상권)정보 API와 국토교통부 건축HUB 건축물대장정보
서비스를 함께 쓰기 위한 얇은 레이어다. 두 API는 서비스키 전달 방식과 JSON
응답 봉투(envelope) 구조가 서로 다르고, 같은 API 안에서도 결과가 0건일 때
items가 빈 문자열로 내려오는 등 형태가 흔들린다. 그래서 파싱을 한 곳에
모아 느슨하게 처리한다 (services/sk_footfall.py의 _parse_hourly와 같은 방침).

서비스키는 .env의 DATA_GO_KR_SERVICE_KEY를 쓴다. 포털에서 발급받은
'일반 인증키(Decoding)' 값을 그대로 넣는다 — httpx가 URL 인코딩을 하므로
Encoding 키를 넣으면 이중 인코딩으로 SERVICE_KEY_IS_NOT_REGISTERED_ERROR가 난다.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

SERVICE_KEY_ENV = "DATA_GO_KR_SERVICE_KEY"

DEFAULT_TIMEOUT = 10.0
# 공공데이터포털 개발계정은 트래픽 제한이 빡빡하다. 사전 수집 스크립트가
# 수백~수천 번 호출하므로 호출 간 최소 간격을 둔다.
DEFAULT_SLEEP_SEC = 0.12


class DataGoKrError(RuntimeError):
    """서비스키 오류/쿼터 초과처럼 재시도해도 소용없는 응답."""


# 포털이 정상 서비스로 보는 resultCode. 문서상 "00"이지만 일부 서비스는 "0"을 준다.
_OK_CODES = {"00", "0", "000"}


def service_key() -> Optional[str]:
    key = (os.environ.get(SERVICE_KEY_ENV) or "").strip()
    return key or None


def has_service_key() -> bool:
    return service_key() is not None


def get_json(url: str, params: dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT) -> Any:
    """
    서비스키를 붙여 GET 후 JSON을 반환한다.

    포털은 키가 틀렸거나 쿼터를 넘겼을 때도 HTTP 200 + XML 에러 본문을 주는
    경우가 있어, JSON 파싱 실패를 곧 키/쿼터 문제로 보고 DataGoKrError를 던진다.
    """
    import httpx

    key = service_key()
    if not key:
        raise DataGoKrError(f"{SERVICE_KEY_ENV}가 설정되지 않았습니다. backend/.env에 추가하세요.")

    merged = {**params, "serviceKey": key}
    response = httpx.get(url, params=merged, timeout=timeout)
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        body = response.text[:400]
        raise DataGoKrError(
            f"JSON이 아닌 응답입니다 (키/쿼터 문제일 가능성이 높습니다): {body}"
        ) from None


def check_header(payload: Any) -> None:
    """
    응답 헤더의 resultCode를 확인한다. 정상이 아니면 DataGoKrError를 던진다.
    두 API의 헤더 위치가 달라(response.header / header) 양쪽을 본다.
    """
    header = None
    if isinstance(payload, dict):
        header = payload.get("header")
        if header is None:
            response = payload.get("response")
            if isinstance(response, dict):
                header = response.get("header")
    if not isinstance(header, dict):
        return  # 헤더가 없는 형태면 판정하지 않고 items 추출에 맡긴다.

    code = str(header.get("resultCode", "")).strip()
    if code and code not in _OK_CODES:
        message = header.get("resultMsg") or header.get("resultMessage") or ""
        raise DataGoKrError(f"resultCode={code} {message}")


def extract_items(payload: Any) -> list[dict[str, Any]]:
    """
    응답에서 레코드 리스트를 꺼낸다.

    실제로 관측되는 형태가 모두 다르기 때문에 모양을 가리지 않고 받는다:
      상가정보   {"body": {"items": [ {...} ]}}
      건축물대장 {"response": {"body": {"items": {"item": [ {...} ]}}}}
      1건일 때   {"response": {"body": {"items": {"item": {...}}}}}
      0건일 때   {"response": {"body": {"items": ""}}}
    """
    body = payload
    if isinstance(body, dict) and "response" in body:
        body = body["response"]
    if isinstance(body, dict) and "body" in body:
        body = body["body"]
    if not isinstance(body, dict):
        return []

    items = body.get("items")
    if isinstance(items, dict):
        items = items.get("item")
    if items is None or items == "":
        return []
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return [entry for entry in items if isinstance(entry, dict)]
    return []


def total_count(payload: Any) -> int:
    body = payload
    if isinstance(body, dict) and "response" in body:
        body = body["response"]
    if isinstance(body, dict) and "body" in body:
        body = body["body"]
    if not isinstance(body, dict):
        return 0
    try:
        return int(body.get("totalCount") or 0)
    except (TypeError, ValueError):
        return 0


def paged(
    url: str,
    params: dict[str, Any],
    *,
    rows: int = 1000,
    max_pages: int = 1000,
    sleep_sec: float = DEFAULT_SLEEP_SEC,
    timeout: float = DEFAULT_TIMEOUT,
    progress: Optional[Any] = None,
) -> Iterable[dict[str, Any]]:
    """
    pageNo를 1부터 올리며 레코드를 모두 흘려보낸다.

    totalCount를 신뢰하지 않고 "빈 페이지가 나오면 끝"으로 판단한다. 상가정보
    API는 totalCount가 실제 반환량과 어긋나는 경우가 있기 때문이다.
    """
    import time

    seen = 0
    for page in range(1, max_pages + 1):
        payload = get_json(
            url,
            {**params, "pageNo": page, "numOfRows": rows},
            timeout=timeout,
        )
        check_header(payload)
        items = extract_items(payload)
        if not items:
            return
        for item in items:
            yield item
        seen += len(items)
        if progress is not None:
            progress(page, seen, total_count(payload))
        if len(items) < rows:
            return  # 마지막 페이지
        if sleep_sec:
            time.sleep(sleep_sec)
