import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// 본문(한글)은 globals.css에서 CDN @import한 Pretendard Variable을 쓰고, Inter는
// 라틴 문자/숫자용 폴백으로 next/font/google을 통해 실제로 로드해 최적화(서브셋팅,
// self-host, layout shift 방지)까지 받는다 — "선언만 하고 로드가 안 되는" 상태를 피한다.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "채움 (Chaeum)",
  description: "전북 원도심 공실 상가 AI 진단 및 업종 적합도 스코어링",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
