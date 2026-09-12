import { mockAnalysisApi } from "./fixtures/analysis";
import { expect, test } from "@playwright/test";
import { mockFootfallApi } from "./fixtures/footfall";
import { mapMatches, seedMatchResults } from "./fixtures/match";

test.beforeEach(async ({ page }) => {
  await mockFootfallApi(page);
  await mockAnalysisApi(page);
});

test("매물 상세 팝업에서 선택한 매물의 유동인구 화면으로 이동한다", async ({ page }) => {
  await seedMatchResults(page, mapMatches.slice(0, 2));
  const footfallCalls: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/footfall?")) footfallCalls.push(request.url());
  });

  await page.goto("/match/results");
  await expect(page.getByRole("button", { name: /추천 [12]위 카드 상세 보기/ })).toHaveCount(2);
  await expect(page.getByRole("region", { name: "추천 매물 주변 유동인구 지도" })).toHaveCount(0);
  await page.getByRole("button", { name: "추천 1위 카드 상세 보기" }).click();
  const link = page.getByRole("dialog").getByRole("link", { name: "주변 유동인구 보기 →" });
  await expect(link).toHaveAttribute("href", "/diagnosis/b1#visualize");
  await page.getByRole("button", { name: "매물 상세 닫기" }).click();

  await page.getByRole("button", { name: "추천 2위 카드 상세 보기" }).click();
  await expect(link).toHaveAttribute("href", "/diagnosis/b2#visualize");
  expect(footfallCalls).toEqual([]);
  await link.click();

  await expect(page).toHaveURL("/diagnosis/b2#visualize");
  await expect(page.getByText(/전주시 태평동 2 반경/)).toBeVisible();
  expect(footfallCalls.every((url) => url.includes("/b2/footfall?"))).toBe(true);
});

test("직접 진입과 새로고침으로 유동인구를 조회하며 이미지 생성 기능은 없다", async ({ page }) => {
  const oldApiCalls: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path === "/api/visualize/mode" || /\/api\/buildings\/[^/]+\/(visualize|photo)$/.test(path)) {
      oldApiCalls.push(path);
    }
  });

  await page.goto("/visualize/b1");
  await expect(page.getByRole("heading", { name: "유동인구 시각화" })).toBeVisible();
  await expect(page.getByText(/전주시 객사길 1 반경/)).toBeVisible();
  await expect(page.getByRole("link", { name: "유동인구", exact: true })).toHaveAttribute("href", "#visualize");
  await expect(page.getByRole("link", { name: "리포트", exact: true })).toHaveAttribute("href", "#report");
  await expect(page.getByLabel(/컨셉/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: /이미지 생성|다른 사진/ })).toHaveCount(0);

  await page.reload();
  await expect(page.getByText("하루 유동인구", { exact: true })).toBeVisible();
  expect(oldApiCalls).toEqual([]);
});

test("매물 선택기를 바꾸면 새 ID를 조회하고 이전 선택을 초기화한다", async ({ page }) => {
  await page.goto("/visualize/b1");
  await page.getByRole("button", { name: "주말", exact: true }).click();
  await expect(page.getByRole("button", { name: "주말", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("slider", { name: "시간대" }).fill("12");
  await page.getByRole("button", { name: /^남쪽 상권/ }).click();

  const response = page.waitForResponse("**/api/buildings/b2/footfall?day_type=weekday");
  await page.getByRole("combobox", { name: "매물 선택" }).selectOption("b2");
  await response;
  await expect(page).toHaveURL("/diagnosis/b2#visualize");
  await expect(page.getByText(/전주시 태평동 2 반경/)).toBeVisible();
  await expect(page.getByText(/전주시 객사길 1 반경/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "평일", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("slider", { name: "시간대" })).toHaveValue("-1");
  await expect(page.getByRole("button", { name: /^남쪽 상권/ })).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("link", { name: "리포트", exact: true })).toHaveAttribute("href", "#report");
});
