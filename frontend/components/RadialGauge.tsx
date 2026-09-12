import { formatScore } from "@/lib/format";

interface RadialGaugeProps {
  value: number;
  label: string;
  /** "circle": 360도 원형 게이지(카드용, 작게). "semi": 180도 반원 게이지(강조용, 크게). */
  variant?: "circle" | "semi";
  size?: number;
}

/**
 * EAAI 카드/모달 패턴의 원형·반원 게이지. 트랙은 slate-200, 진행 부분은 brand-400 고정
 * (랭크·등급별 색 분기 없음 — 순위색은 배지에서만 쓴다).
 */
export function RadialGauge({ value, label, variant = "circle", size }: RadialGaugeProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const isSemi = variant === "semi";
  const dim = size ?? (isSemi ? 176 : 104);
  const stroke = isSemi ? 14 : 10;
  const radius = dim / 2 - stroke / 2;
  const cx = dim / 2;
  const cy = isSemi ? dim / 2 : dim / 2;
  const circumference = isSemi ? Math.PI * radius : 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);
  const viewBoxHeight = isSemi ? dim / 2 + stroke / 2 : dim;

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: dim, height: viewBoxHeight }}>
        <svg width={dim} height={viewBoxHeight} viewBox={`0 0 ${dim} ${viewBoxHeight}`}>
          {isSemi ? (
            <>
              <path
                d={`M ${stroke / 2} ${cy} A ${radius} ${radius} 0 0 1 ${dim - stroke / 2} ${cy}`}
                fill="none"
                stroke="#e2e8f0"
                strokeWidth={stroke}
                strokeLinecap="round"
              />
              <path
                d={`M ${stroke / 2} ${cy} A ${radius} ${radius} 0 0 1 ${dim - stroke / 2} ${cy}`}
                fill="none"
                stroke="var(--color-brand-400)"
                strokeWidth={stroke}
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
              />
            </>
          ) : (
            <>
              <circle cx={cx} cy={cy} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={stroke} />
              <circle
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke="var(--color-brand-400)"
                strokeWidth={stroke}
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                transform={`rotate(-90 ${cx} ${cy})`}
              />
            </>
          )}
        </svg>
        <div
          className={`absolute inset-x-0 flex flex-col items-center ${isSemi ? "bottom-0" : "top-1/2 -translate-y-1/2"}`}
        >
          <span className={isSemi ? "text-4xl font-black tracking-tight" : "text-xl font-black tracking-tight"}>
            {formatScore(clamped)}
          </span>
          <span className="text-[11px] font-medium text-muted">{label}</span>
        </div>
      </div>
    </div>
  );
}
