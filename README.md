# 채움 (Chaeum)

전북 원도심 공실 상가 AI 진단 및 업종 적합도 스코어링 서비스 — 해커톤 MVP

## 구조

```
backend/   FastAPI (Python) — 진단/스코어링 API, mock JSON 데이터
frontend/  Next.js + TypeScript + Tailwind CSS
```

데이터는 현재 전부 `backend/app/data/*.json` mock으로 대체되어 있으며,
`DataProvider` 인터페이스(`backend/app/services/data_provider.py`)로 감싸져 있어
추후 실제 데이터 연동 시 `MockDataProvider`를 대체하는 새 구현체만 추가하면 됩니다.

## 실행 방법

### 백엔드

```bash
cd backend
python3.11 -m venv .venv   # Python 3.14는 아직 일부 의존성 wheel이 없어 3.11 권장
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API 문서: http://localhost:8000/docs

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

http://localhost:3000 접속 (백엔드가 8000번 포트에서 실행 중이어야 합니다)

## 데모 시나리오

`backend/app/data/buildings.json`에 전주 원도심 가상 매물 5개가 준비되어 있으며,
각 매물마다 1위 추천 업종이 다르게 나오도록 구성되어 있습니다 (학원 / 카페 / 병원 / 편의점 / 스터디카페).
`/property/new` 화면 하단의 "데모 매물로 바로 둘러보기"에서 바로 확인할 수 있습니다.

## 화면 구성

1. 온보딩 (역할 선택) — `/`
2. 매물 입력 — `/property/new`
3. 진단 결과 — `/diagnosis/[id]`
4. 업종 적합도 순위 — `/ranking/[id]`
5. 리스크 대시보드 — `/dashboard/[id]`
6. 인허가 체크리스트 — `/permits/[id]`
7. 전략 그리드 — `/strategy/[id]`
8. 시각화 (Before/After 슬라이더) — `/visualize/[id]`
9. 리포트 (Executive Summary + PDF) — `/report/[id]`
