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
8. 시각화 (공간 컨셉 이미지 생성 + Before/After 슬라이더) — `/visualize/[id]`
9. 리포트 (Executive Summary + PDF) — `/report/[id]`
10. 지자체 공실 현황 대시보드 — `/official`
11. 주변 유동인구 (매칭 결과 화면 내 색상 지도) — `/match/results`

## 주변 유동인구 대시보드 (SK open API)

매칭 결과(`/match/results`)에서 추천 매물을 고르면, 그 매물 반경 1.5km의 상권 구역별
**시간대별 유동인구**가 색상 지도로 따라 붙습니다. 매칭 스코어링(`/api/match`)과는 완전히
분리된 별도 조회이므로, 유동인구 조회가 실패해도 추천 결과는 그대로 보입니다.

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

## 팝업 브랜드 flow

팝업 브랜드는 예비창업자와 **동일한 화면·동일한 `/api/match` 엔드포인트**를 그대로
재사용한다. "짧은 기간, 확실한 노출"이라는 사용 맥락 차이는 로직이 아니라 문구로만
표현하며, 같은 인프라로 다른 사용자층을 흡수하는 것이 이 설계의 핵심이다.

| 구분 | 예비창업자 | 팝업 브랜드 |
|---|---|---|
| 진입 경로 | `/match/new?role=founder` | `/match/new?role=brand` |
| 화면·컴포넌트 | 동일 (6단계 → 분석 중 → TOP3~5 → drill-down) | 동일 |
| 백엔드 | `POST /api/match` | 동일 |
| 스코어링 | `matching_agents.py` | 동일 (분기 없음) |
| Step 1 문구 | 어떤 업종을 계획 중이신가요? | 어떤 브랜드/컨셉을 운영하시나요? |
| 추가 입력 | — | 입점 희망 기간(단기/장기) |

- role은 온보딩이 `?role=`로 붙여 보내고, 없으면 localStorage로 폴백한다
  (`lib/roleContext.tsx`). 첫 렌더부터 확정되어 문구가 깜빡이지 않는다.
- role별 문구는 전부 `lib/roleCopy.ts` 한 곳에 모여 있다. role이 늘어도
  컴포넌트를 고칠 필요가 없다.
- 입점 희망 기간은 팝업 브랜드에만 노출되며 별도 스텝이 아니라 Step 1 안에 있다
  (6단계 구조를 role에 따라 갈라지지 않게 하기 위함).
  **현재 스코어링 가중치에는 반영하지 않고** 전달·저장·로깅과 공간 시각화
  프롬프트 연출에만 쓴다.
  단기 임대 가능 매물 우선 필터링은 실제 데이터 연동 단계의 로드맵 항목이다.

## 공간 시각화 (HuggingFace 연동)

`/visualize/[id]` 화면에서 공실 사진과 컨셉(업종 또는 팝업 브랜드)을 입력하면
적용 후 이미지를 생성합니다. 팝업 브랜드 담당자가 입지를 고르는 단계에서
"이 공간이 내가 기획한 팝업을 구현하기에 적당한가"를 눈으로 확인하기 위한 기능이며,
매칭 flow(`/api/match`)와는 서로 호출하지 않는 독립 경로입니다.

구현은 `backend/app/services/space_render.py`, 엔드포인트는
`POST /api/buildings/{id}/visualize` 입니다.

### 매물 사진은 어디서 오는가

이 화면의 사용자(팝업 브랜드·예비창업자)는 공간을 **찾는** 쪽이라 공실 사진을 갖고
있지 않습니다. 그래서 사진 업로드를 요구하지 않고 매물 데이터에서 공급합니다
(`backend/app/services/building_photo.py`, `GET /api/buildings/{id}/photo`).

1. `backend/app/data/photos/{매물id}.{jpg,png,webp}`에 실제 촬영본이 있으면 그것을 사용
   (이 디렉터리의 이미지는 git 추적 제외 — 각자 로컬에 두는 데모 자산이다)
2. 없으면 해당 매물의 노후도·채광 점수와 `thumbnail_color`로 그린 참고용 공실
   이미지를 사용

화면은 둘을 구분해 표시하므로("매물 등록 사진 사용 중" / "매물 참고 이미지 사용 중"),
참고용 이미지가 실제 매물 사진으로 오인되지 않습니다. 촬영본이 생기면 `photos/`에
파일만 넣으면 코드 변경 없이 1번으로 전환됩니다. 업로드 버튼은 "다른 사진으로
해보기"라는 선택 수단으로 남아 있습니다.

### 실행 모드

환경에 따라 3단계로 자동 폴백하며, 어떤 실패에서도 화면이 죽지 않습니다.

| 모드 | 조건 | 동작 |
|---|---|---|
| `hf_api` | `HF_TOKEN` 설정됨 | HuggingFace Inference Providers의 image-to-image로 생성 |
| `local` | `CHAEUM_RENDER_MODE=local` | 로컬 `diffusers` 마스크 인페인팅 (GPU 필요) |
| `demo` | 해당 매물에 `{id}.after.*` 촬영본 있음 + 생성 미연결 | 실제 시공 전/후 사진 (AI 생성 아님을 화면에 명시) |
| `mock` | 그 외 / 모든 예외 | Pillow 색보정 기반 미리보기 |

필요한 환경변수는 `backend/.env.example`에 정리해 두었다. 복사해서 값을 채운다
(`.env`는 git에 올라가지 않는다).

```bash
# 실제 생성을 쓰려면 (권장)
export HF_TOKEN=hf_xxx          # Inference Providers 권한이 있는 fine-grained 토큰
export CHAEUM_HF_MODEL=black-forest-labs/FLUX.1-Kontext-dev   # 선택

# GPU가 있어 마스크 인페인팅을 쓰려면
pip install torch diffusers accelerate transformers
export CHAEUM_RENDER_MODE=local
export CHAEUM_LOCAL_MODEL=diffusers/stable-diffusion-xl-1.0-inpainting-0.1   # 선택
```

주의: HuggingFace **호스팅** image-to-image 스펙에는 `mask_image` 파라미터가 없습니다.
즉 `hf_api` 모드는 프롬프트 기반 편집만 가능하고, 마스크로 특정 영역만 다시 그리는
인페인팅은 `local` 모드에서만 동작합니다.

생성된 이미지는 `backend/app/data/generated/`에 캐시되어 같은 조건 재시연 시
즉시 응답합니다 (git 추적 제외).

## 테스트

```bash
# 프론트 E2E — 백엔드가 :8000에서 실행 중이어야 합니다 (next dev는 자동 기동)
cd frontend && npx playwright test

# 백엔드 재사용 원칙 가드 (스코어링에 role 분기가 들어오면 실패한다)
cd backend && python -m pytest tests/ -q
```
