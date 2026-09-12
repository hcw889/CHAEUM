"use client";

import { useState, type ReactNode } from "react";

export function BeforeAfterSlider({
  before,
  after,
  beforeLabel = "현재",
  afterLabel = "적용 후 (mock)",
}: {
  before: ReactNode;
  after: ReactNode;
  beforeLabel?: string;
  afterLabel?: string;
}) {
  const [split, setSplit] = useState(50);

  return (
    <div>
      <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl border border-border select-none">
        <div className="absolute inset-0">{before}</div>
        <div className="absolute inset-0" style={{ clipPath: `inset(0 0 0 ${split}%)` }}>
          {after}
        </div>

        <span className="absolute left-3 top-3 rounded-full bg-black/50 px-2.5 py-1 text-xs text-white">{beforeLabel}</span>
        <span className="absolute right-3 top-3 rounded-full bg-black/50 px-2.5 py-1 text-xs text-white">{afterLabel}</span>

        <div className="absolute inset-y-0 w-0.5 bg-white shadow" style={{ left: `${split}%` }} />
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={split}
        onChange={(e) => setSplit(Number(e.target.value))}
        className="mt-4 w-full accent-[var(--accent)]"
        aria-label="비교 슬라이더"
      />
    </div>
  );
}
