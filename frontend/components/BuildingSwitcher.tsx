"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BuildingSummary } from "@/lib/types";

export function BuildingSwitcher({ currentId }: { currentId: string }) {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const router = useRouter();

  useEffect(() => {
    api.listBuildings().then(setBuildings).catch(() => setBuildings([]));
  }, []);

  if (buildings.length === 0) return null;

  return (
    <label className="no-print flex items-center gap-2 text-sm text-muted">
      데모 매물
      <select
        value={currentId}
        onChange={(e) => {
          const section = document.querySelector<HTMLAnchorElement>('.analysis-nav a[aria-current="location"]')?.hash ?? window.location.hash;
          router.push(`/diagnosis/${e.target.value}${section}`);
        }}
        className="rounded-sm border border-border bg-surface px-2.5 py-1.5 text-foreground"
      >
        {buildings.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
    </label>
  );
}
