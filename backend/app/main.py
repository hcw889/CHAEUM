import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# backend/.env 를 읽어 환경변수로 올린다 (SK_OPENAPI_APP_KEY, ANTHROPIC_API_KEY 등).
# 이미 셸에 설정된 값은 덮어쓰지 않으며, .env가 없으면 그냥 넘어간다.
#
# 파일이 없을 때는 경고를 남긴다 — .env를 backend/app/ 에 두는 바람에 키가 하나도
# 안 읽히고 모든 화면이 조용히 목업으로 돌던 일이 있었다.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
try:
    from dotenv import load_dotenv

    if not load_dotenv(ENV_PATH):
        misplaced = Path(__file__).resolve().parent / ".env"
        if misplaced.is_file():
            logger.warning(
                ".env가 %s 에 있습니다. 로더는 %s 를 읽으므로 파일을 옮기세요.", misplaced, ENV_PATH
            )
        else:
            logger.warning("%s 가 없어 외부 API 키 없이(목업 모드로) 시작합니다.", ENV_PATH)
except ImportError:  # python-dotenv 미설치 환경 — 셸 환경변수만 사용한다.
    pass

from app.routers import (
    business_fit,
    buildings,
    dashboard,
    footfall,
    match,
    permits,
    regions,
    report,
)

app = FastAPI(
    title="채움(Chaeum) API",
    description="전북 원도심 공실 상가 진단 및 업종 적합도 스코어링 MVP API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(buildings.router)
app.include_router(business_fit.router)
app.include_router(dashboard.router)
app.include_router(permits.router)
app.include_router(report.router)
app.include_router(match.router)
app.include_router(regions.router)
app.include_router(footfall.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
