import type { ReactNode } from "react";

const TONES = {
  neutral: "border-slate-200 text-slate-600",
  done: "border-brand-200 bg-brand-50 text-accent-text",
  pending: "border-slate-200 bg-slate-50 text-slate-500",
} as const;

interface TagProps {
  children: ReactNode;
  tone?: keyof typeof TONES;
  className?: string;
}

/** 작은 pill 태그 — 강점 키워드, 상태/구분 라벨 등에 공통으로 쓴다. */
export function Tag({ children, tone = "neutral", className = "" }: TagProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${TONES[tone]} ${className}`}>
      {children}
    </span>
  );
}
