"use client";

interface RoleCardProps {
  emoji: string;
  title: string;
  hook: string;
  description: string;
  onClick: () => void;
}

export function RoleCard({ emoji, title, hook, description, onClick }: RoleCardProps) {
  return (
    <button
      onClick={onClick}
      className="group flex flex-col items-start gap-3 rounded-lg border border-border bg-surface p-6 text-left shadow-card transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-card-hover"
    >
      <span className="text-3xl">{emoji}</span>
      <div>
        <p className="text-xs italic text-muted">{hook}</p>
        <h3 className="mt-0.5 font-semibold text-foreground">{title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-muted">{description}</p>
      </div>
      <span className="mt-auto pt-2 text-sm font-medium text-accent-text opacity-0 transition-opacity group-hover:opacity-100">
        시작하기 →
      </span>
    </button>
  );
}
