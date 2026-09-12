export function LogoMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden>
      <defs>
        <linearGradient id="chaeumFill" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="var(--accent)" />
          <stop offset="100%" stopColor="var(--gold)" />
        </linearGradient>
        <clipPath id="chaeumClip">
          <rect x="4" y="4" width="20" height="20" rx="7" />
        </clipPath>
      </defs>
      <rect x="4" y="4" width="20" height="20" rx="7" stroke="var(--foreground)" strokeOpacity="0.3" strokeWidth="1.5" />
      <g clipPath="url(#chaeumClip)">
        <rect x="4" y="12.5" width="20" height="11.5" fill="url(#chaeumFill)" />
      </g>
    </svg>
  );
}

export function Wordmark({ size = 22, className = "" }: { size?: number; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 font-semibold tracking-tight ${className}`}>
      <LogoMark size={size} />
      채움
    </span>
  );
}
