"""
공공데이터포털(data.go.kr) 공통 호출 헬퍼.

소상공인시장진흥공단 상가(상권)정보 API와 국토교통부 건축HUB 건축물대장정보
서비스를 함께 쓰기 위한 얇은 레이어다. 두 API는 서비스키 전달 방식과 JSON
응답 봉투(envelope) 구조가 서로 다르고, 같은 API 안에서도 결과가 0건일 때
items가 빈 문자열로 내려오는 등 형태가 흔들린다. 그래서 파싱을 한 곳에
모아 느슨하게 처리한다 (services/sk_footfall.py의 _parse_hourly와 같은 방침).

서비스키는 API마다 따로 발급된다 (포털 개발계정은 활용신청 건별로 키가 나온다).
그래서 호출부가 어떤 API의 키를 쓸지 명시한다:

    SANGGA_API_SERVICE_KEY   소상공인시장진흥공단_상가(상권)정보
    BLDRGST_API_SERVICE_KEY  국토교통부_건축HUB_건축물대장정보 서비스
    DATA_GO_KR_SERVICE_KEY   위 둘이 없을 때 쓰는 공통 폴백 (한 키로 두 API가 다 열린 경우)

포털에서 발급받은 '일반 인증키(Decoding)' 값을 그대로 넣는다 — httpx가 URL
인코딩을 하므로 Encoding 키를 넣으면 이중 인코딩으로
SERVICE_KEY_IS_NOT_REGISTERED_ERROR가 난다.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# API별 서비스키 환경변수. 값이 없으면 SHARED_SERVICE_KEY_ENV로 폴백한다.
SANGGA_KEY_ENV = "SANGGA_API_SERVICE_KEY"
BLDRGST_KEY_ENV = "BLDRGST_API_SERVICE_KEY"
SHARED_SERVICE_KEY_ENV = "DATA_GO_KR_SERVICE_KEY"

# 두 API의 사람이 읽을 이름 — 키가 없을 때 에러 메시지에 쓴다.
API_LABELS = {
    SANGGA_KEY_ENV: "소상공인시장진흥공단_상가(상권)정보",
    BLDRGST_KEY_ENV: "국토교통부_건축HUB_건축물대장정보 서비스",
}

# 하위 호환: 기존 호출부가 참조하던 이름.
SERVICE_KEY_ENV = SHARED_SERVICE_KEY_ENV

DEFAULT_TIMEOUT = 10.0
# 429(초당/분당 호출 제한) 재시도 횟수와 첫 대기 시간. 지수 백오프로 늘어난다.
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF_SEC = 2.0
# 공공데이터포털 개발계정은 트래픽 제한이 빡빡하다. 사전 수집 스크립트가
# 수백~수천 번 호출하므로 호출 간 최소 간격을 둔다.
DEFAULT_SLEEP_SEC = 0.12


class DataGoKrError(RuntimeError):
    """서비스키 오류/쿼터 초과처럼 재시도해도 소용없는 응답."""


class RateLimited(DataGoKrError):
    """HTTP 429. 잠시 쉬면 풀리는 종류라 호출부가 백오프 후 재시도한다."""


def mask_secrets(text: str) -> str:
    """
    로그/예외 문구에서 서비스키를 가린다.

    httpx의 HTTPStatusError 메시지에는 쿼리스트링이 그대로 들어가서, 그냥 로그에
    흘리면 .env의 서비스키가 파일과 콘솔에 남는다. 모든 에러 경로가 이 함수를 거친다.
    """
    result = text
    for name in (SANGGA_KEY_ENV, BLDRGST_KEY_ENV, SHARED_SERVICE_KEY_ENV):
        value = (os.environ.get(name) or "").strip()
        if len(value) >= 8:
            result = result.replace(value, "<SERVICE_KEY>")
    # 환경변수와 철자가 다른 키(수동 전달 등)도 쿼리스트링 패턴으로 한 번 더 가린다.
    return re.sub(r"(?i)(serviceKey=)[^&\s'\"]+", r"\1<SERVICE_KEY>", result)


# 포털이 정상 서비스로 보는 resultCode. 문서상 "00"이지만 일부 서비스는 "0"을 준다.
_OK_CODES = {"00", "0", "000"}


def service_key(key_env: str = SHARED_SERVICE_KEY_ENV) -> Optional[str]:
    """
    해당 API의 서비스키. 전용 키가 없으면 공통 키로 폴백한다.

    Args:
        key_env: SANGGA_KEY_ENV | BLDRGST_KEY_ENV | SHARED_SERVICE_KEY_ENV
    """
    for name in (key_env, SHARED_SERVICE_KEY_ENV):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


def has_service_key(key_env: str = SHARED_SERVICE_KEY_ENV) -> bool:
    return service_key(key_env) is not None


def missing_key_message(key_env: str) -> str:
    label = API_LABELS.get(key_env)
    target = f"{key_env}({label})" if label else key_env
    return (
        f"{target} 서비스키가 없습니다. backend/.env에 {key_env}=발급받은_Decoding_키 를 "
        f"넣으세요 (두 API가 한 키로 열린다면 {SHARED_SERVICE_KEY_ENV} 하나만 넣어도 됩니다)."
    )


def get_json(
    url: str,
    params: dict[str, Any],
    *,
    key_env: str = SHARED_SERVICE_KEY_ENV,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """
    서비스키를 붙여 GET 후 JSON을 반환한다.

    포털은 키가 틀렸거나 쿼터를 넘겼을 때도 HTTP 200 + XML 에러 본문을 주는
    경우가 있어, JSON 파싱 실패를 곧 키/쿼터 문제로 보고 DataGoKrError를 던진다.

    Args:
        key_env: 이 호출에 쓸 서비스키의 환경변수 이름. API별로 키가 다르다.
    """
    import httpx

    key = service_key(key_env)
    if not key:
        raise DataGoKrError(missing_key_message(key_env))

    merged = {**params, "serviceKey": key}

    # 429는 개발계정 초당/분당 호출 제한이다. 잠깐 쉬면 풀리므로 백오프 후 재시도하고,
    # 끝까지 안 풀리면 RateLimited로 올려 호출부가 순회를 멈추게 한다.
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        response = httpx.get(url, params=merged, timeout=timeout)
        if response.status_code != 429:
            break
        if attempt == RATE_LIMIT_RETRIES:
            raise RateLimited(
                "429 Too Many Requests — 개발계정 호출 한도입니다. "
                "잠시 뒤 다시 실행하거나 수집 범위를 좁히세요."
            )
        wait = RATE_LIMIT_BACKOFF_SEC * (2**attempt)
        logger.warning("429 — %.1f초 후 재시도 (%d/%d)", wait, attempt + 1, RATE_LIMIT_RETRIES)
        time.sleep(wait)

    try:
        response.raise_for_status()
    except Exception as exc:
        # httpx의 예외 문구에는 쿼리스트링(=서비스키)이 들어 있다. 반드시 가린다.
        raise DataGoKrError(mask_secrets(str(exc))) from None

    try:
        return response.json()
    except ValueError:
        body = mask_secrets(response.text[:400])
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
    key_env: str = SHARED_SERVICE_KEY_ENV,
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
            key_env=key_env,
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
