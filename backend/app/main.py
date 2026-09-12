from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# backend/.env 를 읽어 환경변수로 올린다 (SK_OPENAPI_APP_KEY, ANTHROPIC_API_KEY 등).
# 이미 셸에 설정된 값은 덮어쓰지 않으며, .env가 없으면 그냥 넘어간다.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
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
