"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { BeforeAfterSlider } from "@/components/BeforeAfterSlider";
import { BuildingPageHeader } from "@/components/BuildingPageHeader";
import { Card } from "@/components/Card";
import { Skeleton } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { parseStored, useStoredValue } from "@/lib/browserStore";
import { useStoredRole } from "@/lib/role";
import {
  RENDER_MODE_LABELS,
  type Building,
  type BuildingPhotoResponse,
  type BusinessFitCandidate,
  type MatchRequest,
  type RenderMode,
  type SpaceRenderResponse,
} from "@/lib/types";

// 업로드 사진은 data URL로 백엔드에 보낸다. 원본 그대로 보내면 수 MB가 되므로
// 캔버스로 긴 변 1024px까지 줄여서 전송한다 (백엔드도 1024로 리사이즈한다).
const MAX_UPLOAD_SIDE = 1024;

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("사진을 읽지 못했습니다."));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("이미지 형식을 인식하지 못했습니다."));
      img.onload = () => {
        const scale = Math.min(MAX_UPLOAD_SIDE / Math.max(img.width, img.height), 1);
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext("2d")?.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/png"));
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  });
}

export default function VisualizePage() {
  const { id } = useParams<{ id: string }>();
  const fileRef = useRef<HTMLInputElement>(null);

  const role = useStoredRole();
  // 매칭 flow(/match/new)를 거쳐 왔다면 그때 입력한 조건을 컨셉 기본값·프롬프트에 재사용한다.
  const matchRequestRaw = useStoredValue("session", "chaeum_match_request");
  const matchRequest = useMemo(() => parseStored<MatchRequest>(matchRequestRaw), [matchRequestRaw]);

  const [building, setBuilding] = useState<Building | null>(null);
  const [top, setTop] = useState<BusinessFitCandidate | null>(null);
  const [renderMode, setRenderMode] = useState<RenderMode | null>(null);
  // 매물에 딸린 공간 사진. 사용자는 공간을 "찾는" 쪽이라 공실 사진을 갖고 있지 않으므로
  // 업로드를 요구하지 않고 매물 데이터에서 받아온다.
  const [buildingPhoto, setBuildingPhoto] = useState<BuildingPhotoResponse | null>(null);

  const [concept, setConcept] = useState("");
  const [photo, setPhoto] = useState<string | null>(null);
  const [photoName, setPhotoName] = useState<string | null>(null);
  const [strength, setStrength] = useState(0.65);

  const [result, setResult] = useState<SpaceRenderResponse | null>(null);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getBuilding(id), api.getBusinessFit(id)])
      .then(([b, candidates]) => {
        setBuilding(b);
        setTop(candidates[0]);
        // 컨셉 기본값: 매칭 flow에서 입력한 업종/브랜드 > 이 건물의 1위 추천 업종
        setConcept((prev) => prev || matchRequest?.business_type || candidates[0]?.type || "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "불러오기 실패"));

    api.getBuildingPhoto(id).then(setBuildingPhoto).catch(() => setBuildingPhoto(null));

    // 모드를 미리 알아둬야 "실제 생성"인지 "미리보기"인지 버튼 옆에 안내할 수 있다.
    api.getRenderMode().then(({ mode }) => setRenderMode(mode)).catch(() => setRenderMode("mock"));
  }, [id, matchRequest]);

  const isBrand = role === "brand";
  // 생성 모델이 없어도 이 매물에 시공 후 촬영본이 있으면 실제 전/후 사진이 나온다.
  // 버튼 옆 안내가 백엔드의 실제 동작과 어긋나지 않도록 매물별로 계산한다.
  const effectiveMode: RenderMode | null =
    renderMode === "mock" && buildingPhoto?.has_after && !photo ? "demo" : renderMode;

  async function handlePhoto(file: File | undefined) {
    if (!file) return;
    setError(null);
    try {
      setPhoto(await fileToDataUrl(file));
      setPhotoName(file.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "사진 처리에 실패했습니다.");
    }
  }

  async function handleRender() {
    if (!concept.trim()) {
      setError("컨셉을 입력해주세요.");
      return;
    }
    setRendering(true);
    setError(null);
    try {
      setResult(
        await api.renderSpace(id, {
          concept: concept.trim(),
          photo_data_url: photo ?? undefined,
          commercial_style_pref: matchRequest?.commercial_style_pref,
          // 매칭 wizard에서 입점 희망 기간을 받았다면 연출 방향(가설 집기 vs 고정 인테리어)에 반영된다.
          occupancy_term: matchRequest?.occupancy_term,
          strength,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "이미지 생성에 실패했습니다.");
    } finally {
      setRendering(false);
    }
  }

  if (error && !building) return <main className="mx-auto max-w-3xl px-6 py-10 text-danger">{error}</main>;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <BuildingPageHeader buildingId={id} />

      <h1 className="mb-1 text-2xl font-bold tracking-tight">시각화</h1>
      <p className="mb-6 text-sm text-muted">
        {isBrand
          ? "이 공간에 기획 중인 팝업을 올려보면 어떤 모습일지 미리 확인해보세요."
          : "이 공간에 추천 업종을 적용하면 어떤 모습일지 미리 확인해보세요."}
      </p>

      {!building || !top ? (
        <Card>
          <Skeleton className="aspect-[4/3] w-full" />
        </Card>
      ) : (
        <>
          <Card className="mb-6">
            <div className="space-y-5">
              <div>
                <label htmlFor="concept" className="mb-2 block text-sm font-medium">
                  {isBrand ? "팝업 브랜드 / 컨셉" : "적용할 업종 컨셉"}
                </label>
                <input
                  id="concept"
                  value={concept}
                  onChange={(e) => setConcept(e.target.value)}
                  placeholder={isBrand ? "예: 북유럽 감성 플라워 팝업" : "예: 원목 인테리어 로스터리 카페"}
                  className="w-full rounded-xl border border-border bg-background px-4 py-2.5 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-400/30"
                />
              </div>

              <div>
                <p className="mb-2 text-sm font-medium">공간 사진</p>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={() => fileRef.current?.click()}
                    className="rounded-xl border border-border px-4 py-2 text-sm font-medium hover:border-accent"
                  >
                    다른 사진으로 해보기
                  </button>
                  {photoName ? (
                    <span className="flex items-center gap-2 text-sm text-muted">
                      {photoName}
                      <button
                        onClick={() => {
                          setPhoto(null);
                          setPhotoName(null);
                        }}
                        className="text-xs underline hover:text-foreground"
                      >
                        매물 사진으로 되돌리기
                      </button>
                    </span>
                  ) : (
                    <span className="text-sm text-muted">
                      {buildingPhoto?.source === "file"
                        ? "매물 등록 사진 사용 중"
                        : "매물 참고 이미지 사용 중 (촬영 사진 미등록)"}
                    </span>
                  )}
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => handlePhoto(e.target.files?.[0])}
                  className="hidden"
                />
              </div>

              <div>
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="text-sm font-medium">변형 강도</span>
                  <span className="text-sm text-muted">{strength.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0.2}
                  max={1}
                  step={0.05}
                  value={strength}
                  onChange={(e) => setStrength(Number(e.target.value))}
                  className="w-full accent-[var(--accent)]"
                  aria-label="변형 강도"
                />
                <p className="mt-1 text-xs text-muted">
                  낮을수록 원래 공간의 구조가 그대로 남고, 높을수록 컨셉이 과감하게 반영됩니다.
                </p>
              </div>

              {error && <p className="text-sm text-danger">{error}</p>}

              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={handleRender}
                  disabled={rendering}
                  className="rounded-2xl bg-brand-gradient px-6 py-2.5 font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand disabled:opacity-50 disabled:shadow-none"
                >
                  {rendering ? "생성 중…" : result ? "다시 생성" : "컨셉 이미지 생성"}
                </button>
                {effectiveMode && (
                  <span className="text-xs text-muted">현재 모드: {RENDER_MODE_LABELS[effectiveMode]}</span>
                )}
              </div>
            </div>
          </Card>

          <Card>
            <BeforeAfterSlider
              beforeLabel="현재"
              afterLabel={
                result?.mode === "demo" ? "시공 후" : result ? `${concept} 적용` : "적용 후"
              }
              before={
                (result?.before_image ?? photo ?? buildingPhoto?.image) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={result?.before_image ?? photo ?? buildingPhoto?.image}
                    alt="현재 공간"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div
                    className="flex h-full w-full flex-col items-center justify-center gap-2 text-white"
                    style={{ backgroundColor: building.thumbnail_color }}
                  >
                    <span className="text-4xl">🏚️</span>
                    <span className="rounded-full bg-black/30 px-3 py-1 text-xs">{building.name}</span>
                  </div>
                )
              }
              after={
                result ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={result.after_image} alt={`${concept} 적용 이미지`} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-accent px-6 text-center text-accent-foreground">
                    <span className="text-4xl">✨</span>
                    <span className="rounded-full bg-black/15 px-3 py-1 text-xs">
                      위에서 컨셉 이미지를 생성해보세요
                    </span>
                  </div>
                )
              }
            />

            {result && (
              <div className="mt-4 space-y-2 text-xs text-muted">
                <p>
                  생성 방식: <span className="font-medium">{RENDER_MODE_LABELS[result.mode]}</span> · {result.model}
                </p>
                {result.note && <p className="text-danger">{result.note}</p>}
                {result.mode === "demo" && (
                  <p>
                    * 실제로 리뉴얼된 이 매물의 시공 전/후 촬영본입니다. AI 생성 결과가 아니며, 입력한 컨셉에 따라
                    바뀌지 않습니다.
                  </p>
                )}
                {result.mode === "mock" && (
                  <p>
                    * 실제 diffusion 생성이 아니라 색보정 기반 미리보기입니다. 백엔드에 HF_TOKEN을 설정하면 실제
                    이미지가 생성됩니다.
                  </p>
                )}
                <details>
                  <summary className="cursor-pointer">생성 프롬프트 보기</summary>
                  <p className="mt-2 leading-relaxed">{result.prompt}</p>
                </details>
              </div>
            )}
          </Card>

          <Link
            href={`/report/${id}`}
            className="mt-8 inline-flex w-full items-center justify-center rounded-2xl bg-brand-gradient py-3 font-semibold uppercase tracking-[0.16em] text-accent-foreground shadow-card transition-all hover:shadow-glow-brand sm:w-auto sm:px-8"
          >
            리포트 보기 →
          </Link>
        </>
      )}
    </main>
  );
}
