import type { Role } from "./types";

/**
 * 매칭 flow(/match/new → /match/results)의 role별 문구.
 *
 * 화면과 스코어링 로직은 role과 무관하게 100% 동일하고, 사용자에게 보이는 말만
 * 갈라진다. 예비창업자는 "장기 정착", 팝업 브랜드는 "단기 노출 테스트"라는
 * 사용 맥락 차이를 문구로만 표현한다.
 *
 * 문구를 컴포넌트가 아니라 여기에 모아두는 이유: role이 늘어도 컴포넌트를
 * 건드리지 않고 이 매핑에 항목만 추가하면 되도록 하기 위함이다.
 */
export interface RoleCopy {
  /** wizard 상단 제목 */
  wizardTitle: string;
  /** wizard 상단 보조 설명 */
  wizardSubtitle: string;
  /** Step 1 질문 */
  step1Title: string;
  /** Step 1 "기타 직접입력" 시 placeholder */
  step1Placeholder: string;
  /** 분석 중 화면 하단 문구 */
  loadingFooter: string;
  /** 결과 화면 제목 */
  resultsTitle: string;
  /** 제출 버튼 */
  submitLabel: string;
}

const FOUNDER: RoleCopy = {
  wizardTitle: "내 상황을 알려주세요",
  wizardSubtitle: "6가지 조건을 바탕으로 딱 맞는 매물을 찾아드려요.",
  step1Title: "어떤 업종을 계획 중이신가요?",
  step1Placeholder: "예: 베이커리, 반려동물용품점",
  loadingFooter: "4개의 AI 에이전트가 원도심 매물 데이터를 분석하고 있어요.",
  resultsTitle: "매물 추천 결과",
  submitLabel: "매물 추천받기",
};

const BRAND: RoleCopy = {
  wizardTitle: "팝업 조건을 알려주세요",
  wizardSubtitle: "6가지 조건을 바탕으로 노출·체류 조건이 맞는 공간을 찾아드려요.",
  step1Title: "어떤 브랜드/컨셉을 운영하시나요?",
  step1Placeholder: "예: 플라워 팝업, 로컬 디저트 브랜드",
  loadingFooter: "4개의 AI 에이전트가 팝업에 맞는 원도심 공간을 분석하고 있어요.",
  resultsTitle: "팝업 공간 추천 결과",
  submitLabel: "공간 추천받기",
};

export const ROLE_COPY: Record<Role, RoleCopy> = {
  founder: FOUNDER,
  brand: BRAND,
  // owner는 매칭 flow 대신 진단 flow(/property/new)로 가지만, 매핑을 빠짐없이
  // 채워 두면 어느 role로 진입해도 문구가 비지 않는다.
  owner: FOUNDER,
  official: FOUNDER,
};

export function getRoleCopy(role: Role | null): RoleCopy {
  return role ? ROLE_COPY[role] : FOUNDER;
}
