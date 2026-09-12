"use client";

interface RoleCardProps {
  emoji: string;
  title: string;
  description: string;
  onClick: () => void;
}

export function RoleCard({ emoji, title, description, onClick }: RoleCardProps) {
  return (
    <button
      onClick={onClick}
      className="group flex flex-col items-start gap-3 rounded-2xl border border-border bg-surface p-6 text-left transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
    >
      <span className="text-3xl">{emoji}</span>
      <div>
        <h3 className="font-semibold text-foreground">{title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-muted">{description}</p>
      </div>
      <span className="mt-auto pt-2 text-sm font-medium text-accent opacity-0 transition-opacity group-hover:opacity-100">
        시작하기 →
      </span>
    </button>
  );
}
