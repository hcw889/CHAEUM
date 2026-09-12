# 채움(Chaeum) 프런트엔드

역할 선택, 매물 입력·매칭, 건물 분석과 지자체 대시보드를 제공하는 Next.js·TypeScript·Tailwind CSS 앱입니다. 설치·백엔드 설정과 전체 화면 목록은 [프로젝트 README](../README.md)를 참조합니다.

## 개발 서버 실행

이 디렉터리(`ONIT/frontend`)에서 실행합니다. 먼저 별도 터미널에서 **백엔드가 `http://localhost:8000`으로 실행 중이어야 합니다.** 백엔드 실행 방법은 [프로젝트 README](../README.md#백엔드)를 따릅니다.

```powershell
npm install
npm run dev
```

브라우저에서 `http://localhost:3000`에 접속합니다. API 기본 주소는 `lib/api.ts`에서 설정하며, 변경이 필요한 경우 프런트엔드 시작 전에 `NEXT_PUBLIC_API_BASE` 환경변수를 지정합니다.

## 타입 검사와 빌드

```powershell
npx next typegen
npx tsc --noEmit
npm run build
```

`next typegen`은 `LayoutProps` 등 Next.js의 경로 타입을 생성합니다. 새로 설치한 환경에서도 개발 서버를 먼저 실행하지 않고 타입 검사를 할 수 있도록 포함했습니다. 생성 파일을 수동 편집하지 않습니다.

## Playwright 검사

의존성 설치와 백엔드 기동을 마친 후 같은 디렉터리에서 실행합니다.

```powershell
npx playwright install chromium  # 최초 1회 브라우저 설치
npx playwright test
```

`playwright.config.ts`는 `next dev`를 자동 기동하며 `:3000`에 기존 서버가 있으면 재사용합니다. **백엔드 `:8000`은 자동 기동하지 않으므로 별도 터미널에서 계속 실행해야 합니다.** 매칭 결과에서 선택한 매물로 이동하는 경로, 유동인구 지도·요일·시간대 전환, 조회 실패 후 재시도와 기존 역할별 흐름을 검사합니다.

매칭 지도·상세 팝업과 유동인구 화면 검사는 고정된 API 응답을 사용하므로 외부 API 키 없이 실행할 수 있습니다. 지도 순위 마커·선택 매물의 확대 지도·키보드 포커스·모바일 배치·이전 세션의 좌표 조회도 검사합니다. 실제 SK 데이터 연동과 추천 품질은 별도 검증 대상입니다. 백엔드 pytest 실행은 [프로젝트 README의 테스트 안내](../README.md#테스트)를 참조합니다.
