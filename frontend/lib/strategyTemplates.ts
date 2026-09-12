import { formatCurrency, formatScore } from "./format";
import type { Building, BusinessFitCandidate } from "./types";

export interface StrategyQuadrant {
  title: string;
  points: string[];
}

/**
 * 전략 그리드는 백엔드 연동 전까지 업종/리스크 등급 기반의 규칙형 템플릿으로 생성한다.
 * 추후 실제 상권 데이터가 붙으면 이 함수를 API 응답으로 교체하면 된다.
 */
export function buildStrategyGrid(building: Building, top: BusinessFitCandidate): StrategyQuadrant[] {
  const breakdown = top.score_breakdown;
  const footTraffic = breakdown["foot_traffic_raw_score"] ?? 0;
  const competition = 100 - (breakdown["competition_saturation_raw_score"] ?? 0);
  const isHighFootTraffic = footTraffic >= 60;
  const isCompetitive = competition >= 55;

  return [
    {
      title: "입지 전략",
      points: [
        isHighFootTraffic
          ? "유동인구가 높은 시간대(출퇴근/주말)에 맞춰 전면 노출을 극대화"
          : "낮은 유동인구를 보완할 자체 목적지형 콘텐츠(SNS 인증 요소 등) 마련",
        `${building.floor}층 입지 특성상 ${building.floor === 1 ? "간판·쇼윈도 노출도" : "온라인 지도·배달앱 노출도"}를 우선 점검`,
        `건물 리스크 등급(${building.risk_grade}) 고려 시 ${building.risk_grade === "위험" ? "안전 점검 후 입점 권장" : "현재 컨디션으로 입점 가능"}`,
      ],
    },
    {
      title: "포지셔닝",
      points: [
        isCompetitive
          ? "경쟁 포화도가 낮은 편으로, 카테고리 대표 브랜드로 선점 가능"
          : "경쟁이 있는 상권이므로 차별화된 컨셉/가격대로 포지셔닝 필요",
        `${top.type} 적합도 ${formatScore(top.fit_score)}점 기준, 상위 3개 업종과의 시너지 고려`,
      ],
    },
    {
      title: "채널 전략",
      points: [
        isHighFootTraffic ? "오프라인 워크인 비중이 높을 것으로 예상, 현장 프로모션 강화" : "배달앱/예약 플랫폼 등 온라인 채널 비중 확대",
        "지역 커뮤니티(SNS, 동네생활 앱) 기반 초기 인지도 확보",
      ],
    },
    {
      title: "가격 전략",
      points: [
        `추정 임대료 월 ${formatCurrency(top.estimated_rent)} 기준 손익분기 역산 필요`,
        isCompetitive ? "경쟁 대비 프리미엄 가격 전략 시도 가능" : "초기 진입가로 고객 락인 후 단계적 가격 조정 권장",
      ],
    },
  ];
}
