"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BuildingSummary } from "@/lib/types";

export function BuildingSwitcher({ currentId }: { currentId: string }) {
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    api.listBuildings().then(setBuildings).catch(() => setBuildings([]));
  }, []);

  if (buildings.length === 0) return null;

  const step = pathname?.split("/")[1] ?? "diagnosis";

  return (
    <label className="no-print flex items-center gap-2 text-sm text-muted">
      데모 매물
      <select
        value={currentId}
        onChange={(e) => router.push(`/${step}/${e.target.value}`)}
        className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-foreground"
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
