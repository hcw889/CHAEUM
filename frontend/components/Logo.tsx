import Image from "next/image";

// public/logo-mark.png은 원본 심볼에서 투명 여백을 잘라낸 512x496 이미지라 정사각이
// 아니다. size는 "높이" 기준으로 받고 너비는 이 비율로 계산해 왜곡 없이 렌더한다.
const MARK_RATIO = 512 / 496;

export function LogoMark({ size = 22, priority = false }: { size?: number; priority?: boolean }) {
  return (
    <Image
      src="/logo-mark.png"
      alt=""
      width={Math.round(size * MARK_RATIO)}
      height={size}
      priority={priority}
      className="shrink-0"
    />
  );
}

export function Wordmark({ size = 22, className = "" }: { size?: number; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 font-semibold tracking-tight ${className}`}>
      {/* 헤더 로고는 화면 최상단에 바로 노출되므로 preload해 깜빡임을 막는다. */}
      <LogoMark size={size} priority />
      채움
    </span>
  );
}
