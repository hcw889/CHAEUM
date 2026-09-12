import type { ReactNode } from "react";

interface InsightBoxProps {
  headline: string;
  children: ReactNode;
  className?: string;
}

/** EAAI RISK INSIGHT와 동일 톤의 하단 콜아웃 박스. */
export function InsightBox({ headline, children, className = "" }: InsightBoxProps) {
  return (
    <div className={`flex gap-3 rounded-md border border-amber-100 bg-amber-50 p-4 ${className}`}>
      <span aria-hidden className="mt-0.5 shrink-0 text-lg leading-none">
        💡
      </span>
      <div>
        <p className="mb-1 text-sm font-bold text-amber-900">{headline}</p>
        <p className="text-sm leading-relaxed text-amber-800">{children}</p>
      </div>
    </div>
  );
}
