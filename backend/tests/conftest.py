"""
테스트 공통 설정.

기본 provider는 LiveSanggaProvider(요청마다 상가정보/건축물대장 API 호출)다.
테스트가 그대로 돌면 실제 네트워크를 타고, 공공데이터포털 일일 호출 한도를
테스트 실행만으로 소진한다. 그래서 스위트 전체에서 라이브 검색을 꺼 둔다.

라이브 검색 자체를 검증하는 테스트는 live_search.search()를 직접 부르며
monkeypatch로 API 호출을 대신한다 (test_live_search.py 참고).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("CHAEUM_LIVE_SEARCH", "0")
os.environ["CHAEUM_LIVE_SEARCH"] = "0"


@pytest.fixture(autouse=True)
def _reset_provider_singleton():
    """
    provider는 모듈 전역 싱글턴이라 테스트 사이에 상태가 샌다
    (LiveSanggaProvider는 검색 결과를 인메모리에 누적한다).
    """
    from app.services import data_provider

    data_provider._provider = None
    yield
    data_provider._provider = None
