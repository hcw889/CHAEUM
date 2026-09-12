"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { Skeleton } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { formatPercent, formatScore } from "@/lib/format";
import { loadRole } from "@/lib/role";
import {
  BUSINESS_TYPE_OPTIONS,
  PRIORITY_OPTIONS,
  REGION_OPTIONS,
  ROLE_LABELS,
  STYLE_OPTIONS,
  type MatchRequest,
  type Role,
} from "@/lib/types";

const TOTAL_STEPS = 6;
const CUSTOM_BUSINESS_TYPE = "기타 직접입력";

const LOADING_STEPS = [
  "예산 매칭 에이전트 분석 중…",
  "상권 적합도 에이전트 분석 중…",
  "건물 컨디션 에이전트 분석 중…",
  "추천 이유 정리 중…",
];
const LOADING_STEP_MS = 600;

// 라이브 발표용 데모 프리셋. 사전 검증한 서로 다른 조건 조합으로, 각각 다른 1위 매물을
// 즉시 보여준다 (예산절약→b5 전주역, 매출잠재력→b2 객사길, 건물안정성→b7 노송동).
const DEMO_PRESETS: { key: string; label: string; description: string; payload: MatchRequest }[] = [
  {
    key: "budget",
    label: "예산 최우선 창업자",
    description: "빠듯한 예산으로 시작하는 예비 창업자 시나리오",
    payload: {
      business_type: "카페",
      area_pyeong: 15,
      budget: { deposit: 10_000_000, monthly_rent: 1_000_000 },
      region_pref: "전주역",
      commercial_style_pref: "조용한골목상권",
      priority: "예산절약",
    },
  },
  {
    key: "revenue",
    label: "매출 잠재력 우선 브랜드",
    description: "화제성과 매출 잠재력이 중요한 팝업 브랜드 시나리오",
    payload: {
      business_type: "카페",
      area_pyeong: 15,
      budget: { deposit: 13_000_000, monthly_rent: 1_300_000 },
      region_pref: "객사길",
      commercial_style_pref: "유동인구중심",
      priority: "매출잠재력",
    },
  },
  {
    key: "stability",
    label: "건물 안정성 우선 지자체",
    description: "안정적인 건물 컨디션을 우선하는 지자체 담당자 시나리오",
    payload: {
      business_type: "카페",
      area_pyeong: 15,
      budget: { deposit: 17_000_000, monthly_rent: 1_700_000 },
      region_pref: "노송동",
      commercial_style_pref: "유동인구중심",
      priority: "건물안정성",
    },
  },
];

export default function MatchWizardPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role | null>(null);

  const [step, setStep] = useState(1);
  const [businessType, setBusinessType] = useState(BUSINESS_TYPE_OPTIONS[0]);
  const [customBusinessType, setCustomBusinessType] = useState("");
  const [areaPyeong, setAreaPyeong] = useState(15);
  const [deposit, setDeposit] = useState(10_000_000);
  const [monthlyRent, setMonthlyRent] = useState(1_000_000);
  const [regionPref, setRegionPref] = useState(REGION_OPTIONS[0]);
  const [stylePref, setStylePref] = useState(STYLE_OPTIONS[0].value);
  const [priority, setPriority] = useState(PRIORITY_OPTIONS[1].value);

  const [phase, setPhase] = useState<"wizard" | "loading">("wizard");
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [showPresets, setShowPresets] = useState(true);

  useEffect(() => {
    // Delay the browser-only storage read until after hydration. This also keeps
    // the server and first client render identical.
    const timer = window.setTimeout(() => setRole(loadRole()), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const isCustomType = businessType === CUSTOM_BUSINESS_TYPE;
  const canProceed = step !== 1 || !isCustomType || customBusinessType.trim().length > 0;

  function goNext() {
    if (step < TOTAL_STEPS) setStep(step + 1);
    else handleSubmit();
  }

  function goBack() {
    if (step > 1) setStep(step - 1);
  }

  function handlePresetClick(preset: (typeof DEMO_PRESETS)[number]) {
    // 이후 "이전"으로 돌아가거나 재제출할 때도 값이 맞도록 폼 상태도 함께 채워둔다.
    setBusinessType(preset.payload.business_type);
    setAreaPyeong(preset.payload.area_pyeong ?? areaPyeong);
    setDeposit(preset.payload.budget.deposit);
    setMonthlyRent(preset.payload.budget.monthly_rent);
    setRegionPref(preset.payload.region_pref);
    setStylePref(preset.payload.commercial_style_pref ?? stylePref);
    setPriority(preset.payload.priority);
    setStep(TOTAL_STEPS);
    handleSubmit(preset.payload);
  }

  async function handleSubmit(overridePayload?: MatchRequest) {
    setPhase("loading");
    setLoadingStepIndex(0);
    setError(null);

    const payload: MatchRequest = overridePayload ?? {
      business_type: isCustomType ? customBusinessType.trim() : businessType,
      area_pyeong: areaPyeong,
      budget: { deposit, monthly_rent: monthlyRent },
      region_pref: regionPref,
      commercial_style_pref: stylePref,
      priority,
    };

    const timer = setInterval(() => {
      setLoadingStepIndex((i) => Math.min(i + 1, LOADING_STEPS.length - 1));
    }, LOADING_STEP_MS);

    try {
      const [result] = await Promise.all([
        api.matchBuildings(payload),
        new Promise((resolve) => setTimeout(resolve, LOADING_STEP_MS * LOADING_STEPS.length)),
      ]);
      sessionStorage.setItem("chaeum_match_request", JSON.stringify(payload));
      sessionStorage.setItem("chaeum_match_result", JSON.stringify(result));
      router.push("/match/results");
    } catch (err) {
      setPhase("wizard");
      setError(err instanceof Error ? err.message : "매칭 요청에 실패했습니다.");
    } finally {
      clearInterval(timer);
    }
  }

  if (phase === "loading") {
    return <LoadingScreen stepIndex={loadingStepIndex} />;
  }

  return (
    <main className="mx-auto w-full max-w-xl flex-1 px-6 py-12">
      <div className="mb-6">
        {role && (
          <span className="mb-3 inline-block rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
            {ROLE_LABELS[role]}
          </span>
        )}
        <h1 className="text-2xl font-bold tracking-tight">내 상황을 알려주세요</h1>
        <p className="mt-2 text-sm text-muted">6가지 조건을 바탕으로 딱 맞는 매물을 찾아드려요.</p>
      </div>

      {showPresets && (
        <Card className="mb-6 border-accent/30 bg-accent-soft/40">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-semibold text-accent">⚡ 빠른 데모 시나리오</p>
            <button onClick={() => setShowPresets(false)} className="text-xs text-muted hover:text-foreground">
              직접 입력하기 ↓
            </button>
          </div>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {DEMO_PRESETS.map((preset) => (
              <button
                key={preset.key}
                onClick={() => handlePresetClick(preset)}
                className="rounded-md border border-border bg-surface p-3.5 text-left transition-colors hover:border-accent"
              >
                <p className="text-sm font-semibold">{preset.label}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted">{preset.description}</p>
              </button>
            ))}
          </div>
        </Card>
      )}

      <div className="mb-6">
        <div className="mb-1.5 flex justify-between text-xs text-muted">
          <span>Step {step} / {TOTAL_STEPS}</span>
          <span>{formatPercent((step / TOTAL_STEPS) * 100, 0)}</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
          />
        </div>
      </div>

      <Card>
        <div key={step} className="step-transition">
        {step === 1 && (
          <Step title="희망 업종이 무엇인가요?">
            <select
              value={businessType}
              onChange={(e) => setBusinessType(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
            >
              {BUSINESS_TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
              <option value={CUSTOM_BUSINESS_TYPE}>{CUSTOM_BUSINESS_TYPE}</option>
            </select>
            {isCustomType && (
              <input
                value={customBusinessType}
                onChange={(e) => setCustomBusinessType(e.target.value)}
                placeholder="예: 베이커리, 반려동물용품점"
                className="mt-3 w-full rounded-md border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
              />
            )}
          </Step>
        )}

        {step === 2 && (
          <Step title="희망 평수는 어느 정도인가요?">
            <SliderRow
              value={areaPyeong}
              min={5}
              max={40}
              step={1}
              onChange={setAreaPyeong}
              format={(v) => `${v}평`}
            />
          </Step>
        )}

        {step === 3 && (
          <Step title="가용 예산을 알려주세요">
            <div className="space-y-6">
              <div>
                <p className="mb-2 text-sm font-medium text-muted">보증금</p>
                <SliderRow
                  value={deposit}
                  min={3_000_000}
                  max={30_000_000}
                  step={500_000}
                  onChange={setDeposit}
                  format={(v) => `${formatScore(v / 10_000)}만원`}
                />
              </div>
              <div>
                <p className="mb-2 text-sm font-medium text-muted">월세</p>
                <SliderRow
                  value={monthlyRent}
                  min={300_000}
                  max={3_000_000}
                  step={100_000}
                  onChange={setMonthlyRent}
                  format={(v) => `${formatScore(v / 10_000)}만원`}
                />
              </div>
            </div>
          </Step>
        )}

        {step === 4 && (
          <Step title="희망하는 지역이 있나요?">
            <select
              value={regionPref}
              onChange={(e) => setRegionPref(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
            >
              {REGION_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </Step>
        )}

        {step === 5 && (
          <Step title="어떤 상권 분위기를 선호하세요?">
            <RadioGroup
              options={STYLE_OPTIONS}
              value={stylePref}
              onChange={setStylePref}
            />
          </Step>
        )}

        {step === 6 && (
          <Step title="매물을 고를 때 가장 중요한 기준은?">
            <RadioGroup
              options={PRIORITY_OPTIONS}
              value={priority}
              onChange={setPriority}
            />
          </Step>
        )}
        </div>

        {error && <p className="mt-4 text-sm text-danger">{error}</p>}

        <div className="mt-8 flex gap-3">
          {step > 1 && (
            <button
              onClick={goBack}
              className="rounded-md border border-border px-5 py-2.5 text-sm font-medium text-muted hover:text-foreground"
            >
              이전
            </button>
          )}
          <button
            onClick={goNext}
            disabled={!canProceed}
            className="flex-1 rounded-md bg-accent py-2.5 font-medium text-accent-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {step < TOTAL_STEPS ? "다음" : "매물 추천받기"}
          </button>
        </div>
      </Card>
    </main>
  );
}

function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-5 text-lg font-semibold">{title}</h2>
      {children}
    </div>
  );
}

function SliderRow({
  value,
  min,
  max,
  step,
  onChange,
  format,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format: (v: number) => string;
}) {
  return (
    <div>
      <p className="mb-2 text-2xl font-bold tracking-tight">{format(value)}</p>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--accent)]"
      />
      <div className="mt-1 flex justify-between text-xs text-muted">
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
    </div>
  );
}

function RadioGroup({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string; description?: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-2.5">
      {options.map((opt) => (
        <label
          key={opt.value}
          className={`flex cursor-pointer items-start gap-3 rounded-md border px-4 py-3 transition-colors ${
            value === opt.value ? "border-accent bg-accent-soft" : "border-border hover:border-accent/50"
          }`}
        >
          <input
            type="radio"
            checked={value === opt.value}
            onChange={() => onChange(opt.value)}
            className="mt-1 h-4 w-4 accent-[var(--accent)]"
          />
          <span>
            <span className="block font-medium">{opt.label}</span>
            {opt.description && <span className="block text-sm text-muted">{opt.description}</span>}
          </span>
        </label>
      ))}
    </div>
  );
}

function LoadingScreen({ stepIndex }: { stepIndex: number }) {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center px-6 py-12 text-center">
      <Card className="w-full text-left">
        <Skeleton className="mb-5 h-5 w-48" />
        <Skeleton className="mb-3 h-3 w-full" />
        <Skeleton className="mb-6 h-3 w-4/5" />
        <div className="flex gap-2">
          {LOADING_STEPS.map((_, i) => (
            <span
              key={i}
              className="h-1.5 flex-1 rounded-full transition-colors"
              style={{ backgroundColor: i <= stepIndex ? "var(--accent)" : "var(--border)" }}
            />
          ))}
        </div>
        <p className="mt-6 text-center text-sm text-muted">{LOADING_STEPS[stepIndex]}</p>
      </Card>
    </main>
  );
}
