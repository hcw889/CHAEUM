"use client";

import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { Card } from "@/components/Card";
import { Skeleton } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { formatPercent, formatScore } from "@/lib/format";
import { RoleProvider, useResolvedRole, useRole } from "@/lib/roleContext";
import { getRoleCopy } from "@/lib/roleCopy";
import {
  BUSINESS_TYPE_OPTIONS,
  OCCUPANCY_TERM_OPTIONS,
  PRIORITY_OPTIONS,
  REGION_OPTIONS,
  ROLE_LABELS,
  STYLE_OPTIONS,
  type MatchRequest,
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

/**
 * 매칭 flow 입력 wizard.
 *
 * 예비창업자·팝업 브랜드·지자체 담당자가 완전히 동일한 컴포넌트와 동일한
 * /api/match 엔드포인트를 공유한다. role에 따라 갈라지는 것은 화면에 보이는
 * 문구(lib/roleCopy.ts)와, 팝업 브랜드에만 추가로 노출되는 입점 희망 기간
 * 입력뿐이며, 단계 수·요청 형태·스코어링은 role과 무관하게 같다.
 */
export default function MatchWizardPage() {
  // useSearchParams()를 쓰므로 Suspense 경계가 필요하다.
  return (
    <Suspense fallback={<main className="mx-auto w-full max-w-xl flex-1 px-6 py-12" />}>
      <MatchWizard />
    </Suspense>
  );
}

function MatchWizard() {
  const role = useResolvedRole();

  return (
    <RoleProvider role={role}>
      <WizardBody />
    </RoleProvider>
  );
}

function WizardBody() {
  const router = useRouter();
  const role = useRole();
  const copy = getRoleCopy(role);
  const isBrand = role === "brand";

  const [step, setStep] = useState(1);
  const [businessType, setBusinessType] = useState(BUSINESS_TYPE_OPTIONS[0]);
  const [customBusinessType, setCustomBusinessType] = useState("");
  const [occupancyTerm, setOccupancyTerm] = useState(OCCUPANCY_TERM_OPTIONS[0].value);
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
      // 팝업 브랜드에서만 입력받는다. 백엔드로 전달·저장은 하되 현재 스코어링
      // 가중치에는 반영하지 않는다.
      // TODO: 단기임대 가중치 반영은 로드맵 다음 단계
      ...(isBrand ? { occupancy_term: occupancyTerm } : {}),
    };

    if (isBrand) {
      console.info("[match] occupancy_term:", occupancyTerm, "(스코어링 미반영)");
    }

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
    return <LoadingScreen stepIndex={loadingStepIndex} footer={copy.loadingFooter} />;
  }

  return (
    <main className="mx-auto w-full max-w-xl flex-1 px-6 py-12">
      <div className="mb-6">
        <span className="mb-3 inline-block rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
          {ROLE_LABELS[role]}
        </span>
        <h1 className="text-2xl font-bold tracking-tight">{copy.wizardTitle}</h1>
        <p className="mt-2 text-sm text-muted">{copy.wizardSubtitle}</p>
      </div>

      {showPresets && (
        <Card className="mb-6 border-accent/30 bg-accent-soft/40">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-accent">⚡ 예비창업자 빠른 데모</p>
              <p className="mt-1 text-xs text-muted">15개 목업 매물에서 조건별 추천 결과를 바로 확인하세요.</p>
            </div>
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
          <Step title={copy.step1Title}>
            <select
              value={businessType}
              onChange={(e) => setBusinessType(e.target.value)}
              aria-label={copy.step1Title}
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
                placeholder={copy.step1Placeholder}
                className="mt-3 w-full rounded-md border border-border bg-background px-4 py-2.5 outline-none focus:border-accent"
              />
            )}

            {/*
              입점 희망 기간 — 팝업 브랜드에만 노출한다.
              별도 스텝으로 빼지 않고 Step 1 안에 두어, 예비창업자와 동일한
              "6단계" 구조가 role에 따라 갈라지지 않게 한다.
            */}
            {isBrand && (
              <div className="mt-6 border-t border-border pt-5">
                <p className="mb-3 text-sm font-medium">입점 희망 기간</p>
                <RadioGroup options={OCCUPANCY_TERM_OPTIONS} value={occupancyTerm} onChange={setOccupancyTerm} />
                <p className="mt-3 text-xs text-muted">
                  * 현재는 추천 점수에 반영되지 않고, 단기 임대 가능 매물 우선 추천은 다음 단계에서 지원됩니다.
                </p>
              </div>
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
              aria-label="희망하는 지역이 있나요?"
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
            <RadioGroup options={STYLE_OPTIONS} value={stylePref} onChange={setStylePref} />
          </Step>
        )}

        {step === 6 && (
          <Step title="매물을 고를 때 가장 중요한 기준은?">
            <RadioGroup options={PRIORITY_OPTIONS} value={priority} onChange={setPriority} />
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
            {step < TOTAL_STEPS ? "다음" : copy.submitLabel}
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

function LoadingScreen({ stepIndex, footer }: { stepIndex: number; footer: string }) {
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
      <p className="mt-6 text-sm text-muted">{footer}</p>
    </main>
  );
}
