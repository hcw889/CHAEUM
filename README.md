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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

설치와 실행 모두 프로젝트의 `.venv` Python을 직접 사용하므로 가상환경 활성화는 필요하지 않습니다. 전역 `uvicorn`으로 실행하면 `.venv`에 설치된 `langgraph` 등을 찾지 못할 수 있습니다. 이미 가상환경이 있으면 생성 단계는 생략합니다.

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

총 **6개 화면**입니다. 건물별 분석은 `/diagnosis/[id]` 한 페이지에서 일곱 섹션을 연속으로 보여줍니다. 상단 메뉴는 스크롤 중에도 고정되고, 선택한 섹션으로 이동하며 현재 위치를 표시합니다.

| 화면 | 경로 | 기본 진입 역할 |
| --- | --- | --- |
| 온보딩 (역할 선택) | `/` | 공통 |
| 매물 입력 | `/property/new` | 건물주 |
| 매칭 조건 입력 | `/match/new?role=founder` 또는 `/match/new?role=brand` | 예비 창업자·팝업 브랜드 |
| 매칭 결과 (TOP 3 위치 지도·상세 팝업) | `/match/results` | 예비 창업자·팝업 브랜드 |
| 건물 종합 분석 (진단·업종 순위·리스크·인허가·전략·유동인구·리포트) | `/diagnosis/[id]` | 공통 |
| 지자체 공실 현황 대시보드 | `/official` | 지자체 담당자 |

분석 섹션의 직접 주소는 `/diagnosis/[id]#ranking`처럼 사용합니다. 해시는 `diagnosis`, `ranking`, `dashboard`, `permits`, `strategy`, `visualize`, `report`입니다. 기존 `/ranking/[id]` 등 여섯 상세 주소도 대응하는 섹션으로 이동합니다. 건물 정보와 업종 순위는 섹션끼리 공유하며, 메뉴 이동은 재조회나 페이지 전환을 일으키지 않습니다. 유동인구 지도는 해당 섹션 근처에 도달하면 불러오고 이후 상태를 유지합니다. PDF 다운로드는 리포트 섹션만 인쇄합니다.

## 주변 유동인구 대시보드 (SK open API)

유동인구 섹션(`/diagnosis/[id]#visualize`)에서 선택한 매물 반경 1.5km의 상권 구역별
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

## 실제 공실 데이터 연동 (공공데이터포털)

두 개의 공공 API를 **건물 단위로 조인해** 공실 매물을 만들고, 매칭 추천(`/api/match`)의
후보로 쓴다. 캐시가 있으면 `RealSanggaProvider`, 없으면 기존 `MockDataProvider`가 쓰인다.

| API | 얻는 것 |
| --- | --- |
| 소상공인시장진흥공단_상가(상권)정보 | 영업 중인 점포 목록 (업종·층·좌표·건물관리번호·지번) |
| 국토교통부_건축HUB_건축물대장정보 서비스 | 건물 제원 (사용승인일·층별 용도/면적·구조·승강기) |

### 공실은 추정값이다

**두 API 모두 "공실" 필드를 제공하지 않는다.** 그래서 다음 논리로 추론한다:

```
건축물대장 층별개요에 근린생활시설·판매시설로 등재된 층
  AND 상가정보에 그 층의 등록 점포가 0건
-> 공실 후보
```

조인 키는 상가정보 응답의 `bldMngNo`(건물관리번호), 없으면 `ldongCd`+`plotSctCd`+
`lnbrMnnm`/`lnbrSlno`(법정동코드+대지구분+본번/부번)이며, 이 값들이 건축물대장의
`sigunguCd`/`bjdongCd`/`platGbCd`/`bun`/`ji`와 그대로 맞물린다.

틀릴 수 있는 경로가 분명히 있으므로 매물마다 `confidence`와 판정 근거(`basis`)를
붙이고 결과 화면에도 "추정"으로 표시한다:

- 상가정보는 분기 스냅샷이라 신규 개업이 아직 반영되지 않았을 수 있다
- 사업자등록 주소의 층 표기(`flrNo`)가 비었거나 실제와 다를 수 있다
- 대장상 근린생활시설이지만 자가 사용(사무실·창고)인 층일 수 있다

### 실데이터와 추정값 구분

`DataProvider.get_data_sources()`가 필드별 출처를 내려주고, 결과 화면의
`components/VacancyEvidence.tsx`가 배지로 구분해 보여 준다.

| 구분 | 필드 |
| --- | --- |
| 실데이터 (건축물대장) | 준공연도(사용승인일), 층별 전용면적, 층, 대장 용도, 구조, 승강기 |
| 실데이터 (상가정보) | 소재지, 좌표, 인근 영업 점포, **경쟁포화도**(반경 300m 동일업종 실측 점포 수) |
| 실데이터 파생 계산 | 노후도 점수(경과연수), 접근성 점수(층수+승강기) |
| 추정값 | 공실 판정, 채광 점수, 유동인구 지수(상가 밀도 프록시), 인구통계 적합도, 월세 |

임대 시세와 일조 데이터는 두 API에 없어 `vacancy_estimator.py`의 가정값
(`RENT_PER_PYEONG_BY_SIGNGU`, `FLOOR_RENT_FACTOR`)을 쓴다. 실제 임대 시세 API를
붙이면 그 표만 교체하면 된다.

### 수집 방법

1. [공공데이터포털](https://www.data.go.kr)에서 두 API의 활용신청을 각각 승인받는다.
   - 소상공인시장진흥공단_상가(상권)정보
   - 국토교통부_건축HUB_건축물대장정보 서비스
2. `backend/.env`에 **API별 일반 인증키(Decoding)** 를 넣는다. 포털 개발계정은
   활용신청 건별로 키가 따로 발급되므로 두 줄이 필요하다. Encoding 키를 넣으면
   httpx가 한 번 더 인코딩해 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`가 난다.

   ```
   SANGGA_API_SERVICE_KEY=상가정보_Decoding_키
   BLDRGST_API_SERVICE_KEY=건축물대장_Decoding_키
   ```

   한 키로 두 API가 모두 열리는 계정이면 공통 폴백 한 줄로 대체할 수 있다:

   ```
   DATA_GO_KR_SERVICE_KEY=공통_Decoding_키
   ```

   | 환경변수 | 대상 API |
   | --- | --- |
   | `SANGGA_API_SERVICE_KEY` | 소상공인시장진흥공단_상가(상권)정보 |
   | `BLDRGST_API_SERVICE_KEY` | 국토교통부_건축HUB_건축물대장정보 서비스 |
   | `DATA_GO_KR_SERVICE_KEY` | 위 둘이 없을 때의 공통 폴백 |

3. 수집 스크립트를 실행한다. venv를 반드시 쓴다(시스템 Python에는 의존성이 없다).
   런타임이 아니라 사전 수집인 이유는 건축물대장이 건물당 2회 호출이라 매칭
   요청마다 돌리면 응답이 수십 초가 되고, 개발계정 호출 한도를 데모 중에
   소진하기 때문이다.

   ```bash
   cd backend
   .\.venv\Scripts\python.exe scripts/fetch_real_vacancies.py                     # 전북 시·군 전역(기본)
   .\.venv\Scripts\python.exe scripts/fetch_real_vacancies.py --max-buildings 200 # 호출 절약
   .\.venv\Scripts\python.exe scripts/fetch_real_vacancies.py --mode grid --bbox 127.08,35.79,127.20,35.86
   ```

4. 서버를 재시작하면 `RealSanggaProvider`로 전환된다. 결과 화면 상단에
   "실데이터 기반 공실 추정" 배너가 뜬다.

출력은 `backend/app/data/real/`에 쌓인다 — `buildings.json`(매물 후보),
`market_data.json`(매물 x 업종 시장 신호), `region_stats.json`(시군별 표본 공실
집계), `meta.json`(수집 시각·건수·출처).

`CHAEUM_FORCE_MOCK=1`을 주면 캐시가 있어도 목업을 쓴다 (비교용).

### 실제 API에서 확인한 제약

문서와 다른 부분이 있어 실호출로 확인한 내용이다 (`tests/test_real_vacancy.py`가 고정한다).

| 항목 | 실제 동작 |
| --- | --- |
| `storeListInAdmi` (행정구역 단위) | **폐기됨** — `NO_OPENAPI_SERVICE_ERROR`. 영역/반경 조회만 쓸 수 있다 |
| 사각형 조회 크기 | 0.1도 격자는 `INVALID_REQUEST_PARAMETER_ERROR`로 거부. 0.04도는 정상 |
| 호출 한도 | 격자 전역 순회는 HTTP 429에 걸린다. 분 단위 제한이라 잠시 뒤 풀린다 |
| 지번 필드명 | `lnoMnno` / `lnoSlno` (문서의 `lnbrMnnm`/`lnbrSlno`가 아님), 값은 정수 |
| `flrNo` (층) | **50.3%만 채워져 있다**. 빈 값이면 층 판정 불가 → 공실 신뢰도 '낮음' |
| `bldMngNo` (건물관리번호) | 99.8% 채워짐. 가장 믿을 만한 건물 조인 키 |
| `bldMngNo` 접두 | 구 코드 `45…`, `ldongCd`는 신 코드 `52…`. 건축물대장은 `52…`를 받는다 |
| 건축물대장 `flrGbCdNm` | `지하` / `지상` / **`옥탑`**. 옥탑은 `flrNo`가 1부터 다시 시작해 지상층과 겹친다 |
| 건축물대장 `bldNm` | 값이 없을 때 빈 문자열이 아니라 `" "`(공백)으로 온다 |
| 서비스키 | 계정당 한 키로 두 API가 모두 열렸다. API별 키를 따로 넣어도 된다 |

그래서 기본 수집 방식은 **시·군 대표 지점 반경 조회**다. 전북 14개 시·군 +
전주 5개 시범 상권 좌표(`region_stats.json`)를 중심으로 반경 2km씩 훑는다.
`--mode grid`는 호출 한도가 넉넉한 계정이나 좁은 `--bbox`에서만 쓴다.

### 알려진 한계

- **표본 기준이다.** 전북 전체 건물의 건축물대장을 다 조회하면 호출 한도를 넘기므로
  시군별로 비례 배분한 상한(`--max-buildings`) 안에서만 조사한다. `region_stats.json`의
  `total_units`는 "전체 상가 수"가 아니라 "조사한 상업용도 층 수"다.
- **도심 반경 표본이다.** 기본 수집은 시·군 대표 지점 반경 2km라서, 그 바깥의
  읍·면 상가는 후보에 들어오지 않는다.
- **월별 추이가 없다.** 과거 이력을 주는 API가 아니라서 `months`가 기준월 1개뿐이고,
  `/official`의 추이 차트는 단일 스냅샷으로 표시된다.
- **평균 공실 기간은 미집계(0)다.** 두 API에 공실 시작 시점 정보가 없다.
- 매칭은 사전 필터로 후보를 좁힌 뒤 상위 40건만 4-agent 스코어링하고 12건을
  돌려준다 (`routers/match.py`의 `SCORING_LIMIT`/`RESPONSE_LIMIT`).

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
