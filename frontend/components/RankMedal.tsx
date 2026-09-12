import type { RankLabel } from "@/lib/types";

const MEDAL: Record<NonNullable<RankLabel>, { label: string; color: string; bg: string }> = {
  gold: { label: "1위", color: "var(--gold)", bg: "var(--accent-soft)" },
  silver: { label: "2위", color: "var(--silver)", bg: "var(--border)" },
  bronze: { label: "3위", color: "var(--bronze)", bg: "var(--accent-soft)" },
};

export function RankMedal({ rank }: { rank: RankLabel }) {
  if (!rank) return null;
  const medal = MEDAL[rank];
  return (
    <span
      className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
      style={{ color: medal.color, backgroundColor: medal.bg, border: `1.5px solid ${medal.color}` }}
    >
      {medal.label}
    </span>
  );
}
