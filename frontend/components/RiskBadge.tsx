import type { RiskGrade } from "@/lib/types";

const STYLES: Record<RiskGrade, string> = {
  안전: "bg-safe-soft text-safe",
  주의: "bg-caution-soft text-caution",
  위험: "bg-danger-soft text-danger",
};

export function RiskBadge({ grade }: { grade: RiskGrade }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${STYLES[grade]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {grade}
    </span>
  );
}
