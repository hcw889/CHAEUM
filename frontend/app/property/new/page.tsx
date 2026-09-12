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
          <span className="mb-3 inline-block rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
            {ROLE_LABELS[role]}
          </span>
        )}
        <h1 className="text-2xl font-bold tracking-tight">이 건물, 진단해볼까요?</h1>
        <p className="mt-2 text-sm text-muted">{role ? ROLE_INTRO[role] : "진단할 상가의 정보를 입력해주세요."}</p>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-1.5 block text-sm font-medium">주소 *</label>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="예: 전북 전주시 완산구 객사길 45"
              className="w-full rounded-md border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
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
                className="w-full rounded-md border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">평수</label>
              <input
                type="number"
                value={areaPyeong}
                onChange={(e) => setAreaPyeong(e.target.value)}
                placeholder="예: 15"
                className="w-full rounded-md border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
              />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium">사진 업로드 (선택)</label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setPhotoName(e.target.files?.[0]?.name ?? null)}
              className="w-full rounded-md border border-dashed border-border bg-background px-4 py-2.5 text-sm text-muted file:mr-3 file:rounded-sm file:border-0 file:bg-accent-soft file:px-3 file:py-1.5 file:text-accent"
            />
            <p className="mt-1.5 text-xs text-muted">
              현재는 목업 단계로, 사진은 업로드 여부만 기록되며 실제 이미지 진단(CV 모델)은 추후 연동됩니다.
            </p>
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-accent py-3 font-medium text-accent-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "진단 중..." : "이 건물 진단하기"}
          </button>
        </form>
      </Card>

      {demoBuildings.length > 0 && (
        <div className="mt-8">
          <p className="mb-3 text-sm text-muted">또는 데모 매물로 바로 둘러보기</p>
          <div className="flex flex-wrap gap-2">
            {demoBuildings.map((b) => (
              <Link
                key={b.id}
                href={`/diagnosis/${b.id}`}
                className="rounded-full border border-border bg-surface px-3.5 py-1.5 text-sm hover:border-accent hover:text-accent"
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
