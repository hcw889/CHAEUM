"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { STEPS } from "./StepNav";

/** 리스크 대시보드 전용 좌측 세로 스텝퍼 — StepNav와 같은 단계 목록을 세로로 보여준다. */
export function VerticalStepper({ buildingId }: { buildingId: string }) {
  const pathname = usePathname();
  const activeIndex = STEPS.findIndex((step) => pathname?.startsWith(`/${step.path}/`));

  return (
    <ol className="no-print flex shrink-0 flex-row gap-2 overflow-x-auto sm:w-40 sm:flex-col sm:gap-0 sm:overflow-visible">
      {STEPS.map((step, i) => {
        const done = activeIndex >= 0 && i < activeIndex;
        const active = i === activeIndex;
        return (
          <li key={step.path} className="flex shrink-0 items-center gap-2 sm:items-stretch">
            <div className="hidden flex-col items-center sm:flex">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ${
                  active
                    ? "bg-accent text-accent-foreground"
                    : done
                      ? "bg-brand-100 text-accent-text"
                      : "bg-border text-muted"
                }`}
              >
                {done ? "✓" : i + 1}
              </span>
              {i < STEPS.length - 1 && <span className={`my-0.5 h-6 w-px ${done ? "bg-brand-300" : "bg-border"}`} />}
            </div>
            <Link
              href={`/${step.path}/${buildingId}`}
              className={`rounded-full border px-3 py-1.5 text-xs whitespace-nowrap transition-colors sm:mb-1 sm:rounded-md sm:border-0 sm:px-2 sm:py-1 ${
                active
                  ? "border-accent bg-accent-soft font-semibold text-accent-text sm:bg-transparent"
                  : "border-border text-muted hover:text-foreground"
              }`}
            >
              {step.label}
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
