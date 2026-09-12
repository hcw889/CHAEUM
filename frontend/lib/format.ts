/** 원 단위 통화 포맷. 예: formatCurrency(1234000) -> "1,234,000원" */
export function formatCurrency(amount: number): string {
  return `${Math.round(amount).toLocaleString("ko-KR")}원`;
}

/** 퍼센트 포맷. 예: formatPercent(78.34) -> "78.3%" */
export function formatPercent(value: number, fractionDigits = 1): string {
  return `${value.toFixed(fractionDigits)}%`;
}

/** 점수(0-100) 포맷. 소수점 없이 정수로 표시. 예: formatScore(71.6) -> "72" */
export function formatScore(value: number): string {
  return `${Math.round(value)}`;
}
