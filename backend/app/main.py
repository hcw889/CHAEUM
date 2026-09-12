from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    business_fit,
    buildings,
    dashboard,
    match,
    permits,
    regions,
    report,
    visualize,
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
app.include_router(visualize.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
