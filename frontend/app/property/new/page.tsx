"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { api } from "@/lib/api";
import { useStoredRole } from "@/lib/role";
import { ROLE_LABELS, type BuildingSummary, type Role } from "@/lib/types";

const ROLE_INTRO: Record<Role, string> = {
  owner: "보유하신 상가의 주소를 입력하면 AI가 건물 리스크와 업종 잠재력을 진단해드려요.",
  founder: "관심있는 상가의 주소를 입력하면 내 아이템과의 적합도를 확인할 수 있어요.",
  brand: "팝업을 열어볼 공간의 주소를 입력하면 유동인구와 화제성 요건을 분석해드려요.",
  official: "관리 중인 공실 상가의 주소를 입력하면 활성화 전략 데이터를 받아볼 수 있어요.",
};

// 라이브 데모에서 진단 전체 흐름을 한 번의 클릭으로 보여줄 수 있는 대표 목업 매물.
const OWNER_DEMO_SCENARIOS = [
  {
    buildingId: "b1",
    label: "노후 상가 리스크 진단",
    name: "팔달로 학원가 노후상가",
    detail: "2층 · 18평 · 주의",
  },
  {
    buildingId: "b2",
    label: "안정 상권 업종 추천",
    name: "객사길 코너 상가",
    detail: "1층 · 14평 · 안전",
  },
  {
    buildingId: "b4",
    label: "고위험 매물 개선안",
    name: "경원동 대로변 상가",
    detail: "1층 · 16평 · 위험",
  },
] as const;

export default function PropertyInputPage() {
  const router = useRouter();
  const role = useStoredRole();
  const [address, setAddress] = useState("");
  const [floor, setFloor] = useState("");
  const [areaPyeong, setAreaPyeong] = useState("");
  const [photoName, setPhotoName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoBuildings, setDemoBuildings] = useState<BuildingSummary[]>([]);

  useEffect(() => {
    api.listBuildings().then(setDemoBuildings).catch(() => setDemoBuildings([]));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!address.trim()) {
      setError("주소를 입력해주세요.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const building = await api.diagnoseBuilding({
        address,
        floor: floor ? Number(floor) : undefined,
        area_pyeong: areaPyeong ? Number(areaPyeong) : undefined,
        has_photo: !!photoName,
      });
      router.push(`/diagnosis/${building.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "진단 요청에 실패했습니다.");
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-xl flex-1 px-6 py-12">
      <Link href="/" className="text-sm text-muted hover:text-foreground">
        ← 역할 다시 선택
      </Link>

      <div className="mt-6 mb-8">
        {role && (
          <span className="mb-3 inline-block rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-text">
            {ROLE_LABELS[role]}
          </span>
        )}
        <h1 className="text-2xl font-bold tracking-tight">이 건물, 진단해볼까요?</h1>
        <p className="mt-2 text-sm text-muted">{role ? ROLE_INTRO[role] : "진단할 상가의 정보를 입력해주세요."}</p>
      </div>

      {role === "owner" && (
        <section className="mb-6" aria-label="건물주 데모 시나리오">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-accent-text">⚡ 건물주 빠른 데모</p>
              <p className="mt-1 text-xs text-muted">목업 매물로 진단부터 업종 추천까지 바로 확인하세요.</p>
            </div>
            <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-text">목업 데이터</span>
          </div>
          <div className="grid gap-2.5 sm:grid-cols-3">
            {OWNER_DEMO_SCENARIOS.map((scenario) => (
              <button
                key={scenario.buildingId}
                type="button"
                onClick={() => router.push(`/diagnosis/${scenario.buildingId}`)}
                className="rounded-md border border-border bg-surface p-3.5 text-left transition-colors hover:border-accent"
              >
                <p className="text-sm font-semibold">{scenario.label}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted">{scenario.name}</p>
                <p className="mt-1.5 text-xs font-medium text-foreground">{scenario.detail}</p>
              </button>
            ))}
          </div>
        </section>
      )}

      <Card>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-1.5 block text-sm font-medium">주소 *</label>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="예: 전북 전주시 완산구 객사길 45"
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-400/30"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium">층수</label>
              <input
                type="number"
                value={floor}
                onChange={(e) => setFloor(e.target.value)}
                placeholder="예: 1"
                className="w-full rounded-xl border border-border bg-background px-4 py-2.5 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-400/30"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">평수</label>
              <input
                type="number"
                value={areaPyeong}
                onChange={(e) => setAreaPyeong(e.target.value)}
                placeholder="예: 15"
                className="w-full rounded-xl border border-border bg-background px-4 py-2.5 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-400/30"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium">사진 업로드 (선택)</label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setPhotoName(e.target.files?.[0]?.name ?? null)}
              className="w-full rounded-md border border-dashed border-border bg-background px-4 py-2.5 text-sm text-muted file:mr-3 file:rounded-sm file:border-0 file:bg-accent-soft file:px-3 file:py-1.5 file:text-accent-text"
            />
            <p className="mt-1.5 text-xs text-muted">
              현재는 목업 단계로, 사진은 업로드 여부만 기록되며 실제 이미지 진단(CV 모델)은 추후 연동됩니다.
            </p>
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-2xl bg-brand-gradient py-3 font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand disabled:opacity-50 disabled:shadow-none"
          >
            {loading ? "진단 중..." : "이 건물 진단하기"}
          </button>
        </form>
      </Card>

      {demoBuildings.length > 0 && (
        <div className="mt-8">
          <p className="mb-3 text-sm text-muted">전체 목업 매물 15개 둘러보기</p>
          <div className="flex flex-wrap gap-2">
            {demoBuildings.map((b) => (
              <Link
                key={b.id}
                href={`/diagnosis/${b.id}`}
                className="rounded-full border border-border bg-surface px-3.5 py-1.5 text-sm hover:border-accent hover:text-accent-text"
              >
                {b.name}
              </Link>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
