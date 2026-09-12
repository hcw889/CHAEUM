"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const STEPS = [
  { path: "diagnosis", label: "진단 결과" },
  { path: "ranking", label: "업종 순위" },
  { path: "dashboard", label: "리스크 대시보드" },
  { path: "permits", label: "인허가" },
  { path: "strategy", label: "전략" },
  { path: "visualize", label: "시각화" },
  { path: "report", label: "리포트" },
];

export function StepNav({ buildingId }: { buildingId: string }) {
  const pathname = usePathname();

  return (
    <nav className="no-print -mx-4 mb-8 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <ul className="flex min-w-max gap-1.5 rounded-full border border-border bg-surface p-1.5 sm:min-w-0 sm:justify-between">
        {STEPS.map((step) => {
          const href = `/${step.path}/${buildingId}`;
          const active = pathname?.startsWith(`/${step.path}/`);
          return (
            <li key={step.path} className="flex-1">
              <Link
                href={href}
                className={`block whitespace-nowrap rounded-full px-3 py-1.5 text-center text-sm transition-colors ${
                  active ? "bg-accent text-accent-foreground" : "text-muted hover:text-foreground"
                }`}
              >
                {step.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
