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

```powershell
cd backend
py -3.11 -m venv .venv   # Python 3.14는 아직 일부 의존성 wheel이 없어 3.11 권장
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

> `Activate.ps1` 실행이 보안 정책으로 막히면(`... cannot be loaded because running scripts is disabled ...`), 먼저 아래 명령으로 현재 세션에서만 정책을 완화하세요.
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

API 문서: http://localhost:8000/docs

### 프론트엔드

```powershell
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
10. 지자체 공실 현황 대시보드 — `/official`

## 지자체 공실 현황 대시보드

역할 선택 화면에서 **지자체 담당자**를 선택하면 입력 단계 없이 `/official`로 이동합니다.
역할별 기획 흐름은 [FLOW.md](../FLOW.md), 전체 기획은 [AGENT.md](../AGENT.md)를 함께 확인합니다.

- 전북 14개 시·군 / 전주 5개 시범 상권 전환
- 공실 수·공실률에 따른 색상과 크기의 지도 원, 확대·축소·전체 보기
- 전체 공실 수, 전체 공실률, 공실률 최상위 지역, 평균 공실 기간
- 지도·지역별 비교 막대 선택과 상세 패널 연동, 6개월 공실률 추이
- 전주 시범 상권에서 기존 `b1`부터 `b5`까지의 매물 진단으로 이동
- 데이터 로딩·오류·재시도·빈 목록 상태, 모바일 배치, 키보드 지역 선택

### 데이터와 API

`GET /api/regions/stats` → `DataProvider.get_region_stats()` → `backend/app/data/region_stats.json`

집계는 **2026년 8월 기준으로 만든 시연용 가상 수치**입니다. 기존 매물 5개만으로 공실률을 산출할 수 없어 별도의 조사 모집단을 가정했습니다.
추천 업종도 시나리오 값이며 실제 상권 분석 결과가 아닙니다.
시·군과 상권은 `scope`로 구분하며 전주 시범 상권을 시·군 합계에 중복 합산하지 않습니다.

| 필드 | 의미 |
| --- | --- |
| `is_mock`, `data_reference_month`, `months` | 목업 여부, 집계 기준월, 추이의 6개 월 |
| `id`, `scope`, `parent_id` | 지역 식별자, 시·군 또는 시범 상권, 소속 시 |
| `lat`, `lng` | 지도 표시용 대략적인 대표 지점 |
| `total_units`, `monthly_vacant_units` | 6개월 고정 상가 수, 각 월의 공실 수 |
| `vacant_units`, `vacancy_rate`, `vacancy_trend_6m` | API에서 공실 수로부터 계산한 기준월 공실 수·공실률·추이 |
| `avg_vacancy_period_months` | 기준월 현재 공실의 평균 공실 기간 |
| `top_recommended_business`, `building_id` | 추천 업종 시나리오, 기존 데모 매물 연결(있는 경우) |

전체 공실률은 **공실 수 합계 ÷ 상가 수 합계 × 100**, 평균 공실 기간은 **지역별 기간 × 현재 공실 수의 합계 ÷ 공실 수 합계**로 계산합니다.
전월 대비는 같은 모집단의 공실률 차이이며 단위는 **%p**입니다.

지도는 [Leaflet 1.9.4](https://leafletjs.com/examples/quick-start/)와 [OpenStreetMap](https://www.openstreetmap.org/copyright)을 사용합니다.
별도 API 키는 필요하지 않으며 배경 지도에는 인터넷 연결이 필요합니다.
원의 위치는 지역 대표 지점이고 색·크기는 선택한 지표를 나타냅니다. **행정경계 면 채색이나 개별 공실 위치 지도는 아닙니다.**
배경 지도 요청이 실패하면 안내를 표시하고 지역별 비교 목록과 집계 조회를 계속 제공합니다.

실데이터 전환 시 같은 API 스키마로 `DataProvider`를 구현하고, 시·군과 상권의 조사 범위·기준월·좌표 및 추천 근거를 검증해야 합니다.

### 지자체 기능 검증

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd ../frontend
npx eslint app/official/page.tsx components/official/VacancyMap.tsx lib/regionTypes.ts lib/roleRoutes.ts lib/api.ts
npx tsc --noEmit
npm run build
```
