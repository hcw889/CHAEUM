# 채움(Chaeum) — AI 에이전트 & 데이터 구성

> 작성 기준: 2026-09-13 / 커밋 `c0cfbac`
> 원본 코드: [backend/app/services/](backend/app/services/), [backend/app/routers/match.py](backend/app/routers/match.py)

## 1. 에이전트는 몇 개인가

**LangGraph StateGraph 노드 기준 6개**, 그중 **실제 LLM을 호출하는 건 2개**입니다.

| # | 에이전트 | 파일 | LLM 호출 | 하는 일 |
|---|---|---|---|---|
| 1 | `budget_agent` | `matching_agents.py:42` | ❌ 규칙 | 예산(보증금·월세) vs 추정 임대료 비율 점수 |
| 2 | `market_fit_agent` | `matching_agents.py:64` | ❌ 규칙 | 유동인구·경쟁포화·인구통계 가중합 + 희망지역 가감점 |
| 3 | `building_condition_agent` | `matching_agents.py:88` | ❌ 규칙 | 노후도·접근성·채광 평균 |
| 4 | `aggregate` (orchestrator) | `matching_agents.py:145` | ❌ 규칙 | `final_score = w1·budget + w2·market_fit + w3·condition` |
| 5 | `explanation_agent` | `matching_agents.py:101` | ✅ **Gemini** (`gemini-3.5-flash-lite`, text, max 1024토큰, 15초 타임아웃) | "왜 이 매물이 맞는지" 한국어 한 문장 생성 |
| 6 | `space_vision_agent` | `space_vision_agent.py` | ✅ **Gemini Vision** (`gemini-3.5-flash-lite`, image+text, max 2048토큰, 15초) | 상가 외관 사진 → 쇼윈도/간판/유리비율/테라스/노후흔적/체감 유동인구 JSON 추출 |

즉 **"4-agent 스코어링"(1~4) + 설명 생성(5) + 비전(6)** 구조입니다.
6번의 점수화(노출성·접근성·팝업 적합도)는 LLM이 아니라 `calculate_space_score()`의
규칙 기반 계산이며, YOLO 등 별도 CV 모델은 쓰지 않습니다.

### 스코어링 가중치

우선순위 선택에 따라 1~3번 에이전트의 가중치가 바뀝니다 (`PRIORITY_WEIGHTS`).

| 우선순위 | budget | market_fit | condition |
|---|---|---|---|
| 예산절약 | 0.5 | 0.3 | 0.2 |
| 매출잠재력 | 0.2 | 0.6 | 0.2 |
| 건물안정성 | 0.2 | 0.2 | 0.6 |
| (기본값) | 1/3 | 1/3 | 1/3 |

## 2. 어떻게 엮여 있나 (오케스트레이션)

`match_orchestrator.py`가 LangGraph `StateGraph`로 **매물 1건당 한 번** 실행합니다.

```
START ─┬─> budget ─────────────┐
       ├─> market_fit ─────────┼─> aggregate ─> END
       ├─> building_condition ─┘   (가중합)
       └─> space_vision ──────────────────────> END
                                (LLM 1콜, 점수 계산엔 미관여)

그래프 밖: 40건 스코어링 → 정렬 → 상위 5건만 추천 사유 생성 (스레드풀 병렬)
```

- 앞 4개 노드는 **병렬 fan-out**, `aggregate`에서 **fan-in**
- **추천 사유는 그래프에 없습니다.** 매물마다 생성하면 정렬 뒤 버려질 매물까지
  LLM을 호출하게 되어, 라우터가 순위를 확정한 다음
  `match_orchestrator.generate_explanations()`로 상위 5건에만 호출합니다
- `space_vision`은 `final_score` / `agent_scores`에 전혀 관여하지 않고 응답에 별도 필드로만 붙음
- **모든 노드가 예외를 자체 흡수**해 그래프가 죽지 않음 (데모 중 500 방지)
- 계산식은 `matching_agents.py` / `space_vision_agent.py`에 그대로 두고,
  `match_orchestrator.py`는 **실행 순서만** 담당 (계산 로직 중복 없음)

### 비용 방어

실데이터는 매물이 수백~수천 건이라 전수 스코어링이 불가능합니다 (`routers/match.py`).

| 상수 | 값 | 의미 |
|---|---|---|
| `SCORING_LIMIT` | 40 | 사전 필터 통과분 중 본 스코어링에 넣는 상한 |
| `EXPLANATION_LIMIT` | 5 | 추천 사유(LLM)를 생성하는 상위 매물 수. 나머지는 템플릿 문구 |
| `RESPONSE_LIMIT` | 12 | 화면에 돌려주는 매물 수 (상위 3개는 gold/silver/bronze) |
| `AREA_MIN_RATIO` / `AREA_MAX_RATIO` | 0.5 / 2.0 | 요청 평수 대비 허용 범위 |
| `RENT_MAX_RATIO` | 2.5 | 월세 추정치가 예산의 이 배수를 넘으면 사전 탈락 |

Space Vision은 추가로 `building_id` 기준 **파일 캐시**(`app/data/space_vision_cache.json`)를
써서 `/match` 호출마다 재계산하지 않습니다. **폴백으로 떨어진 결과는 캐시하지 않습니다** —
캐시는 영구 저장이라 일시적 실패를 한 번 넣으면 그 매물이 영영 폴백에 묶입니다.

실측(`gemini-3.5-flash-lite`): LLM 호출 1건 **4~6초**. 상위 5건을 병렬로 생성해
`/match` 전체가 약 6~9초입니다. 40건을 순차 생성하면 200초가 됩니다.

## 3. 어떤 데이터를 쓰나

### 외부 API 5종

| 소스 | 용도 | 환경변수 | 현재 상태 |
|---|---|---|---|
| 소상공인시장진흥공단 **상가(상권)정보** | 영업 점포 목록 (업종·층·좌표·건물관리번호·지번) | `SANGGA_API_SERVICE_KEY` | ✅ 설정됨 |
| 국토교통부 **건축HUB 건축물대장** | 건물 제원 (사용승인일·층별 용도/면적·구조·승강기) | `BLDRGST_API_SERVICE_KEY` | ✅ 설정됨 |
| **SK open API 유동인구** | 반경 1.5km 구역별 시간대별 유동인구 | `SK_OPENAPI_APP_KEY` | ✅ 설정됨 |
| **Kakao** | 지오코딩(일회성 스크립트) + 로드뷰(프론트) | `KAKAO_REST_API_KEY`, `NEXT_PUBLIC_KAKAO_MAP_KEY` | ✅ 설정됨 |
| **Google Gemini** | 에이전트 5·6 (`app/services/llm.py`) | `GEMINI_API_KEY` | ✅ 설정됨 |

### 공실은 "추정"이다 — 핵심 로직

두 공공 API 모두 공실 필드를 제공하지 않아, `vacancy_estimator.py`가
**건물 단위로 조인**해 추론합니다.

```
건축물대장 층별개요에 근린생활시설·판매시설로 등재된 층
  AND 상가정보에 그 층의 등록 점포가 0건
  → 공실 후보 (confidence + basis 부착)
```

조인 키는 상가정보의 `bldMngNo`(건물관리번호),
없으면 `ldongCd` + `plotSctCd` + `lnoMnno`/`lnoSlno`(법정동코드+대지구분+본번/부번)이며,
건축물대장의 `sigunguCd`/`bjdongCd`/`platGbCd`/`bun`/`ji`와 맞물립니다.

**틀릴 수 있는 경로**(그래서 화면에 "추정"으로 표시):
- 상가정보는 분기 스냅샷이라 신규 개업이 아직 반영되지 않았을 수 있음
- 사업자등록 주소의 층 표기(`flrNo`)가 비었거나(실측 50.3%만 채워짐) 실제와 다를 수 있음
- 대장상 근린생활시설이지만 자가 사용(사무실·창고)인 층일 수 있음

### 실데이터 vs 추정값 구분

| 구분 | 필드 |
|---|---|
| 실데이터 (건축물대장) | 준공연도(사용승인일), 층별 전용면적, 층, 대장 용도, 구조, 승강기 |
| 실데이터 (상가정보) | 소재지, 좌표, 인근 영업 점포, **경쟁포화도**(반경 300m 동일업종 실측 점포 수) |
| 실데이터 파생 계산 | 노후도 점수(경과연수), 접근성 점수(층수+승강기) |
| **추정값** | 공실 판정, 채광 점수, 유동인구 지수(상가 밀도 프록시), 인구통계 적합도, **월세**(면적 × 지역 기준단가 × 층 계수) |

`DataProvider.get_data_sources()`가 필드별 출처를 내려주고,
`frontend/components/VacancyEvidence.tsx`가 배지로 구분해 표시합니다.

### Provider 3단 폴백

| 조건 | Provider | 후보 |
|---|---|---|
| 두 서비스키 있음 | `LiveSanggaProvider` | **요청 시점 라이브 검색** (희망지역 → 대표좌표 → 반경 2km) |
| 키 없고 `app/data/real/` 캐시만 있음 | `RealSanggaProvider` | 마지막 수집분 |
| 둘 다 없음 | `MockDataProvider` | 시연용 목업 15건 |

`CHAEUM_LIVE_SEARCH=0` → 라이브 검색 끄고 디스크 캐시 방식,
`CHAEUM_FORCE_MOCK=1` → 캐시가 있어도 목업 사용.

### 캐시 2겹

| 캐시 | 대상 | 수명 | 이유 |
|---|---|---|---|
| TTL 캐시 (메모리) | 검색 결과 전체 | 15분 | 같은 지역 재검색 즉시 응답 |
| 디스크 캐시 (sqlite) | 건축물대장 응답 | 90일 | 사용승인일·층별 용도는 준공 후 거의 안 바뀜 |

공실 판정의 실제 신호인 **상가정보는 매 검색마다 새로 호출**합니다.
실측 소요: 첫 검색 약 20초 → 대장 캐시 warm 약 7초 → TTL 적중이면 즉시.

## 4. 별도 flow (에이전트 아님)

| flow | 파일 | 방식 |
|---|---|---|
| 업종 적합도 진단 (`/business-fit`) | `scoring.py` | 업종별 가중합 스코어카드. 매칭과 **반대 방향**("이 건물에 어떤 업종이 맞는가"), 상권/컨디션 계산식은 매칭과 공유 |
| 주변 유동인구 (`/footfall`) | `sk_footfall.py` | SK open API 실측 또는 구역 단위 mock 폴백 |
| 지자체 공실 대시보드 (`/regions/stats`) | `region_stats.json` | 2026-08 기준 시연용 가상 집계 (19개 지역) |

## 5. 지금 상태에서 짚어둘 점

1. **에이전트 5·6은 Gemini로 동작합니다.**
   `backend/.env`의 `GEMINI_API_KEY`로 연결되며, `app/services/llm.py` 한 곳에서만 호출합니다.
   - 연결 확인: `.venv/Scripts/python scripts/verify_gemini.py`
   - 두 에이전트 모두 실패를 폴백으로 흡수하기 때문에, 화면만 봐서는
     **LLM이 돈 것과 조용히 폴백한 것이 구분되지 않습니다.** 폴백 시
     `app.services.llm` 로거에 warning이 남습니다.
   - 과거 `space_vision_cache.json`이 b1~b15 전부 폴백 상수로 차 있었던 원인은
     **폴백 결과까지 캐시에 쓰고 있었기 때문**입니다. 키가 없던 상태로 `/match`가
     한 번 돌면(테스트 스위트도 목업 15건에 `/match`를 돌립니다) 폴백값이 그대로
     굳었습니다. 이제 폴백은 캐시하지 않으므로 재발하지 않습니다.

2. **에이전트 6(Space Vision)은 실질적으로 항상 폴백입니다.**
   - 실데이터 매물엔 `photo_url`이 아예 없어 Vision-LLM 호출 자체를 시도하지 않습니다.
     실물은 카카오 로드뷰(lat/lng 기준)로 보여줍니다.
   - 목업 15건만 `photo_url`이 있는데, `picsum.photos` **무작위 스톡이미지**라
     상가 사진이 아닙니다(b1은 고양이 코 접사). 실제로 돌리면
     "쇼윈도 0개 / 간판 없음 / 노출 0.0"처럼 정확하지만 쓸모없는 결과가 나옵니다.
   - `space_vision_cache.json`의 b1~b15는 폴백 상수(노출 59.0 / 접근 60.0 / 팝업 59.5)로
     차 있어, 목업 시연에서도 그 값이 그대로 나갑니다.
   - **로드뷰를 Vision 입력으로 쓰는 건 서버에서 불가능합니다.** 카카오 REST API에는
     로드뷰 이미지 엔드포인트가 없고(지오코딩/장소검색/길찾기/정적지도만) JS SDK 전용이라,
     헤드리스 브라우저 캡처 같은 별도 준비 단계가 필요합니다.
   - 이 에이전트를 실제로 살리려면 **상가 외관 사진을 확보하는 것**이 선결 과제입니다.

3. **`occupancy_term`**(팝업 브랜드 입점 희망 기간)은 전달·세션 저장·로깅만 하고
   **스코어링 가중치에는 미반영**입니다 (`routers/match.py`의 TODO).

4. LLM 호출은 `app/services/llm.py` 한 곳으로 모았습니다. 모델은 `GEMINI_MODEL`
   환경변수로 덮어쓸 수 있고, 기본값은 `gemini-3.5-flash-lite`입니다.
   - `gemini-3.8-flash`(최신 stable Flash)는 **무료 등급 한도가 하루 20건**이라
     검색 한 번으로 소진됩니다. `gemini-2.5` 계열은 신규 사용자에게 닫혔습니다(404).
   - Gemini 3 계열은 thinking이 기본 on이고 **`max_output_tokens`에 사고 토큰이 포함**되므로,
     `thinking_level="low"` + 넉넉한 출력 상한을 씁니다. 상한을 조이면 사고 토큰이 먼저
     소진되어 응답 텍스트가 빈 문자열로 오고, 호출은 성공했는데 폴백이 나가는 형태가 됩니다.

5. 프론트의 빠른 데모 프리셋(`frontend/app/match/new/page.tsx`의 `DEMO_PRESETS`)은
   희망 지역이 목업 동 이름(전주역/객사길/노송동) 기준입니다. 실데이터로 전환되면
   그 지역이 선택지에 없어 `상관없음`으로 낮춰지고, 프리셋 간 차이는 예산·우선순위만
   남습니다 (`handlePresetClick`의 폴백).
