"use client";

import { useEffect, useRef, useState } from "react";

export const STEPS = [
  { path: "diagnosis", label: "진단 결과" },
  { path: "ranking", label: "업종 순위" },
  { path: "dashboard", label: "리스크 대시보드" },
  { path: "permits", label: "인허가" },
  { path: "strategy", label: "전략" },
  { path: "visualize", label: "유동인구" },
  { path: "report", label: "리포트" },
];

export function StepNav({ buildingId }: { buildingId: string }) {
  const nav = useRef<HTMLElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState("diagnosis");

  useEffect(() => {
    const element = nav.current;
    const page = element?.closest<HTMLElement>(".building-analysis");
    if (!element || !page) return;
    const sections = STEPS.map((step) => document.getElementById(step.path)).filter((section): section is HTMLElement => !!section);
    let frame = 0;
    let anchor = window.location.hash.slice(1);
    const update = () => {
      frame = 0;
      const threshold = element.getBoundingClientRect().height + 28;
      let current = sections[0]?.id ?? "diagnosis";
      for (const section of sections) {
        if (section.getBoundingClientRect().top <= threshold) current = section.id;
      }
      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) current = "report";
      setActive(current);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    const alignAnchor = () => {
      // Correct direct-link positions while earlier sections load, until the reader interacts.
      if (STEPS.some((step) => step.path === anchor)) {
        document.getElementById(anchor)?.scrollIntoView({ behavior: "instant", block: "start" });
      }
      schedule();
    };
    const onHashChange = () => { anchor = window.location.hash.slice(1); alignAnchor(); };
    const cancelAlignment = () => { anchor = ""; };
    const resize = new ResizeObserver(() => {
      page.style.setProperty("--analysis-nav-height", element.getBoundingClientRect().height + "px");
      alignAnchor();
    });
    resize.observe(element);
    sections.forEach((section) => resize.observe(section));
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("hashchange", onHashChange);
    window.addEventListener("wheel", cancelAlignment, { passive: true });
    window.addEventListener("touchstart", cancelAlignment, { passive: true });
    window.addEventListener("pointerdown", cancelAlignment, { passive: true });
    window.addEventListener("keydown", cancelAlignment);
    alignAnchor();
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("hashchange", onHashChange);
      window.removeEventListener("wheel", cancelAlignment);
      window.removeEventListener("touchstart", cancelAlignment);
      window.removeEventListener("pointerdown", cancelAlignment);
      window.removeEventListener("keydown", cancelAlignment);
    };
  }, [buildingId]);

  useEffect(() => {
    const container = scroller.current;
    const link = container?.querySelector<HTMLElement>('a[href="#' + active + '"]');
    if (!container || !link) return;
    const box = container.getBoundingClientRect();
    const target = link.getBoundingClientRect();
    if (target.left < box.left) container.scrollLeft -= box.left - target.left + 8;
    else if (target.right > box.right) container.scrollLeft += target.right - box.right + 8;
  }, [active]);

  return (
    <nav ref={nav} className="analysis-nav no-print" aria-label="건물 분석 섹션">
      <div ref={scroller} className="analysis-nav-scroll">
        <ul className="flex min-w-max gap-1 rounded-full border border-border bg-surface p-1.5 sm:justify-between">
          {STEPS.map((step) => (
            <li key={step.path} className="flex-1">
              <a href={"#" + step.path} aria-current={active === step.path ? "location" : undefined}
                className={`block whitespace-nowrap rounded-full px-3 py-2 text-center text-sm font-medium transition-colors ${active === step.path ? "bg-accent text-accent-foreground" : "text-muted hover:bg-accent-soft hover:text-foreground"}`}>
                {step.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
