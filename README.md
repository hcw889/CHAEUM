# 채움 (Chaeum)

전북 원도심 공실 상가의 건물 진단·업종 적합도, 조건 기반 매물 매칭과 주변 유동인구 시각화를 시연하는 해커톤 MVP입니다.

## 구조

```
backend/   FastAPI (Python) — 진단/스코어링·매칭·유동인구·지역 집계 API, mock JSON 데이터
frontend/  Next.js + TypeScript + Tailwind CSS
```

건물·시장 지표·인허가·지역 집계 데이터는 현재 `backend/app/data/*.json` mock으로 제공하며,
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

`backend/app/data/buildings.json`에 전주 가상 매물 **15개**가 준비되어 있습니다.
그중 `b1`~`b5`는 학원 / 카페 / 병원 / 편의점 / 스터디카페가 각각 1위 추천 업종이 되도록 구성되어 있습니다.
건물주 경로인 `/property/new` 하단의 "데모 매물로 바로 둘러보기"에서 확인할 수 있습니다.
매칭 입력 화면 상단에는 빠른 데모 시나리오 3개가 준비되어 있습니다.

## 화면 구성

총 **12개 화면**이며, 건물별 분석 화면 7개는 `StepNav`로 이동합니다.

| 화면 | 경로 | 기본 진입 역할 |
| --- | --- | --- |
| 온보딩 (역할 선택) | `/` | 공통 |
| 매물 입력 | `/property/new` | 건물주 |
| 매칭 조건 입력 | `/match/new?role=founder` 또는 `/match/new?role=brand` | 예비 창업자·팝업 브랜드 |
| 매칭 결과 (TOP 3 위치 지도·상세 팝업) | `/match/results` | 예비 창업자·팝업 브랜드 |
| 진단 결과 | `/diagnosis/[id]` | 공통 |
| 업종 적합도 순위 | `/ranking/[id]` | 공통 |
| 리스크 대시보드 | `/dashboard/[id]` | 공통 |
| 인허가 체크리스트 | `/permits/[id]` | 공통 |
| 전략 그리드 | `/strategy/[id]` | 공통 |
| 유동인구 시각화 (지도·시간대별 비교) | `/visualize/[id]` | 공통 |
| 리포트 (요약·브라우저 인쇄로 PDF 저장) | `/report/[id]` | 공통 |
| 지자체 공실 현황 대시보드 | `/official` | 지자체 담당자 |

## 주변 유동인구 대시보드 (SK open API)

유동인구 시각화(`/visualize/[id]`)에서 선택한 매물 반경 1.5km의 상권 구역별
**시간대별 유동인구**를 색상 지도로 확인합니다. 매칭 결과(`/match/results`)에서
지도 마커 또는 추천 카드를 눌러 상세 팝업의 “주변 유동인구 보기”를 선택하거나, 건물별 분석 메뉴의 “유동인구”로 이동합니다.
주소로 직접 진입할 수 있으며, 화면 상단의 매물 선택기로 조회 대상을 바꿀 수 있습니다.

유동인구는 이 화면에서 별도로 조회합니다. 조회가 실패하면 오류 안내와 재시도 버튼을 표시합니다.

- 구역 원의 **색** = 선택한 시간대의 유동인구(조회 구역 중 최댓값 대비 상대값), **크기** = 구역 반경
- 시간 슬라이더(하루 전체 / 00시~23시)와 평일·주말 전환, 24시간 막대, 구역별 비교 목록
- 요약 지표: 하루 유동인구, 피크 시간대, 도보권(500m) 합계, 최대 구역

### 데이터와 API

`GET /api/buildings/{id}/footfall?day_type=weekday|weekend`
→ `app/services/sk_footfall.py` → **SK open API 유동인구**(openapi.sk.com) 또는 mock

| 모드 | 조건 | 값 |
| --- | --- | --- |
| `sk_api` | `SK_OPENAPI_APP_KEY` 설정 + 호출 성공 | SK open API 실측 |
| `mock` | 키 없음 / 호출·파싱 실패 | 구역 특성 기반 시연용 가상 수치 (결정적) |

폴백은 **구역 단위**로 동작합니다. 일부 구역만 실패하면 그 구역만 가상 수치가 되고,
화면 하단 출처 문구가 어느 쪽인지 표시합니다.

### 키 연결 방법

1. `backend/.env`에 `SK_OPENAPI_APP_KEY=발급받은_키` 를 넣습니다.
2. 계약한 상품의 엔드포인트를 `SK_FOOTFALL_AREA_PATH`(지역코드 기반) 또는
   `SK_FOOTFALL_COORD_PATH`(좌표 기반)에 맞춥니다. `{area_code}` `{date}` `{lat}` `{lng}` `{radius}`가 치환됩니다.
3. 지역코드 기반 상품이라면 `backend/app/data/footfall_areas.json`의 각 구역에
   `sk_area_code`(행정동/집계구 코드)를 채웁니다. 비어 있으면 좌표 호출 → mock 순으로 내려갑니다.

> 구역 좌표·반경은 지도 표시용 대표값이고, 연동 전 수치는 모두 시연용 가상 데이터입니다.
> 실제 응답 예시를 확보하면 `sk_footfall._parse_hourly()`만 엄격한 파서로 바꾸면 됩니다.

## 지자체 공실 현황 대시보드

역할 선택 화면에서 **지자체 담당자**를 선택하면 입력 단계 없이 `/official`로 이동합니다.

- 총 19개 지역 항목: 전북 14개 시·군 / 전주 5개 시범 상권 전환
- 공실 수·공실률에 따른 색상과 크기의 지도 원, 확대·축소·전체 보기
- 전체 공실 수, 전체 공실률, 공실률 최상위 지역, 평균 공실 기간
- 지도·지역별 비교 막대 선택과 상세 패널 연동, 6개월 공실률 추이
- 전주 시범 상권에서 기존 `b1`부터 `b5`까지의 매물 진단으로 이동
- 데이터 로딩·오류·재시도·빈 목록 상태, 모바일 배치, 키보드 지역 선택

### 데이터와 API

`GET /api/regions/stats` → `DataProvider.get_region_stats()` → `backend/app/data/region_stats.json`

집계는 **2026년 8월 기준으로 만든 시연용 가상 수치**입니다. 데모 매물 15개만으로 공실률을 산출할 수 없어 별도의 조사 모집단을 가정했습니다.
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
.\.venv\Scripts\python.exe -m pytest tests -q
cd ../frontend
npx eslint app/official/page.tsx components/official/VacancyMap.tsx lib/regionTypes.ts lib/roleRoutes.ts lib/api.ts
npx next typegen
npx tsc --noEmit
npm run build
```

## 매칭과 팝업 브랜드 구현

팝업 브랜드는 예비 창업자와 **동일한 화면·동일한 `POST /api/match` 엔드포인트**를
재사용합니다. 역할 차이는 문구와 선택 입력으로 반영하며 계산 로직은 공유합니다.

희망 지역은 전주시 데모 지역 15개(동·거리·역 일대)와 “상관없음” 중 선택합니다.
매물 15개를 순위화하고, 화면 대부분을 차지하는 지도에 상위 3개의 위치를 gold·silver·bronze 마커로 표시합니다.
지도 하단에는 순위·주소·매칭 점수 요약 카드가 있으며, 나머지 매물은 “다른 추천 매물” 목록을 펼쳐 확인합니다.

마커 또는 카드를 누르면 큰 상세 팝업이 열립니다. 왼쪽은 선택한 매물 하나만 표시한 확대 지도,
오른쪽은 예산·상권 적합도·건물 컨디션의 **3개 원형 점수와 가중치**, 추천 이유, AI Space Vision 정보입니다.
모바일에서는 지도 아래에 추천 근거를 배치합니다. Escape·닫기 버튼·팝업 바깥 클릭으로 닫을 수 있고,
건물 상세 진단·주변 유동인구 화면으로 이동할 수 있습니다.

매칭 응답의 `location`(`lat`, `lng`, `is_approximate`)은 기존 `footfall_areas.json`의 **시연용 대표 좌표**입니다.
실제 주소를 지오코딩한 위치가 아니며, 화면에 이 구분을 표시합니다. 좌표가 없는 이전 세션은
`GET /api/buildings/locations`로 위치만 추가 조회합니다. 유동인구 API나 매칭 재실행은 필요하지 않습니다.
위치가 없는 매물은 임의의 좌표를 만들지 않고 카드로 상세를 제공하며, 배경 지도 요청이 실패해도 선택 기능은 유지합니다.

| 구분 | 예비 창업자 | 팝업 브랜드 |
|---|---|---|
| 진입 경로 | `/match/new?role=founder` | `/match/new?role=brand` |
| 화면·컴포넌트 | 공통 6단계 마법사와 결과·상세 화면 | 동일 |
| 백엔드 | `POST /api/match` | 동일 |
| 스코어링 | `matching_agents.py` | 동일 (분기 없음) |
| Step 1 문구 | 어떤 업종을 계획 중이신가요? | 어떤 브랜드/컨셉을 운영하시나요? |
| 추가 입력 | — | 입점 희망 기간(단기/장기) |

- 역할 해석은 `lib/roleContext.tsx`에서 처리합니다.
- 매칭 화면의 역할별 문구는 `lib/roleCopy.ts`에 모여 있습니다.
- 입점 희망 기간은 팝업 브랜드에만 노출하며 Step 1 안에 있습니다. 일반 제출 시 전달·세션 저장·로깅하지만 **현재 스코어링 가중치에는 반영하지 않습니다**.
- 빠른 데모 프리셋에는 입점 희망 기간이 포함되지 않습니다. 기간 전달을 시연할 때는 6단계 입력을 직접 제출합니다.
- 단기 임대 가능 매물 우선 필터링은 실제 데이터 연동 단계의 로드맵 항목입니다.

## 테스트

아래 명령은 프로젝트 루트 `ONIT`에서 시작하며, 먼저 위 설치·실행 안내를 따릅니다.
`pytest`·`httpx`는 `requirements.txt`에 포함되어 별도 설치가 필요하지 않습니다.

```powershell
# 백엔드 — 매칭 재사용 원칙과 지역 집계를 함께 검사합니다.
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q

# 프런트엔드 — 백엔드가 :8000에서 실행 중이어야 합니다.
cd ../frontend
npx playwright install chromium  # 최초 1회
npx playwright test              # next dev는 자동 기동하거나 기존 :3000 서버를 재사용합니다.
```

타입 검사·빌드와 Playwright 준비는 [프런트엔드 README](frontend/README.md)를 참조합니다.
