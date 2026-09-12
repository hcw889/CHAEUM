"use client";

import { useRouter } from "next/navigation";
import { RoleCard } from "@/components/RoleCard";
import { saveRole } from "@/lib/role";
import { getRoleRoute } from "@/lib/roleRoutes";
import type { Role } from "@/lib/types";

const ROLES: { role: Role; emoji: string; title: string; hook: string; description: string }[] = [
  {
    role: "owner",
    emoji: "🏢",
    title: "건물주",
    hook: "내 건물에 맞는 업종을 찾고 싶다면",
    description: "보유하신 공실 상가의 리스크와 잠재력을 진단받아보세요.",
  },
  {
    role: "founder",
    emoji: "🌱",
    title: "예비 창업자",
    hook: "내 아이템에 맞는 상가를 찾고 싶다면",
    description: "내 아이템에 가장 적합한 상가를 데이터로 확인해보세요.",
  },
  {
    role: "brand",
    emoji: "🎪",
    title: "팝업 브랜드",
    hook: "짧게, 굵게 임팩트를 남기고 싶다면",
    description: "짧은 기간 임팩트를 낼 수 있는 원도심 공간을 찾아보세요.",
  },
  {
    role: "official",
    emoji: "🏛️",
    title: "지자체 담당자",
    hook: "원도심에 필요한 전략이 궁금하다면",
    description: "원도심 공실 현황과 활성화 전략을 한눈에 파악해보세요.",
  },
];

export default function OnboardingPage() {
  const router = useRouter();

  function handleSelect(role: Role) {
    saveRole(role);
    router.push(getRoleRoute(role));
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-6 py-16">
      <div className="mb-12 text-center">
        <p className="mb-3 text-sm font-medium tracking-wide text-accent">CHAEUM</p>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">채움</h1>
        <p className="mt-4 text-balance text-muted">
          전북 원도심의 비어있는 상가에, 데이터로 다음 이야기를 채웁니다.
          <br />
          어떤 입장에서 방문하셨나요?
        </p>
      </div>

      <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2">
        {ROLES.map((r) => (
          <RoleCard
            key={r.role}
            emoji={r.emoji}
            title={r.title}
            hook={r.hook}
            description={r.description}
            onClick={() => handleSelect(r.role)}
          />
        ))}
      </div>
    </main>
  );
}
