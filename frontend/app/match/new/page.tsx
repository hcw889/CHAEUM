"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { api } from "@/lib/api";
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

  useEffect(() => {
    setRole(loadRole());
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

  async function handleSubmit() {
    setPhase("loading");
    setLoadingStepIndex(0);
    setError(null);

    const payload: MatchRequest = {
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

      <div className="mb-6">
        <div className="mb-1.5 flex justify-between text-xs text-muted">
          <span>Step {step} / {TOTAL_STEPS}</span>
          <span>{Math.round((step / TOTAL_STEPS) * 100)}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
          />
        </div>
      </div>

      <Card>
        {step === 1 && (
          <Step title="희망 업종이 무엇인가요?">
            <select
              value={businessType}
              onChange={(e) => setBusinessType(e.target.value)}
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
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
                className="mt-3 w-full rounded-xl border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
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
                  format={(v) => `${(v / 10_000).toLocaleString()}만원`}
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
                  format={(v) => `${(v / 10_000).toLocaleString()}만원`}
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
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
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

        {error && <p className="mt-4 text-sm text-danger">{error}</p>}

        <div className="mt-8 flex gap-3">
          {step > 1 && (
            <button
              onClick={goBack}
              className="rounded-xl border border-border px-5 py-2.5 text-sm font-medium text-muted hover:text-foreground"
            >
              이전
            </button>
          )}
          <button
            onClick={goNext}
            disabled={!canProceed}
            className="flex-1 rounded-xl bg-accent py-2.5 font-medium text-accent-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
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
          className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 transition-colors ${
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
      <div className="mb-6 h-10 w-10 animate-spin rounded-full border-2 border-border border-t-accent" />
      <p className="text-lg font-semibold">{LOADING_STEPS[stepIndex]}</p>
      <div className="mt-6 flex gap-2">
        {LOADING_STEPS.map((_, i) => (
          <span
            key={i}
            className="h-1.5 w-8 rounded-full transition-colors"
            style={{ backgroundColor: i <= stepIndex ? "var(--accent)" : "var(--border)" }}
          />
        ))}
      </div>
      <p className="mt-8 text-sm text-muted">4개의 AI 에이전트가 원도심 매물 데이터를 분석하고 있어요.</p>
    </main>
  );
}
