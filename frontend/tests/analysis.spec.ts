import { expect, test } from "@playwright/test";
import { mockAnalysisApi, candidates } from "./fixtures/analysis";
import { mockFootfallApi } from "./fixtures/footfall";

test.beforeEach(async ({ page }) => {
  await mockFootfallApi(page);
  await mockAnalysisApi(page);
});

test("일곱 섹션을 한 페이지에서 보고 이동해도 재조회나 입력 초기화가 없다", async ({ page }) => {
  const calls: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) calls.push(new URL(request.url()).pathname); });
  await page.goto("/diagnosis/b1");
  await expect(page.locator(".analysis-section")).toHaveCount(7);
  await expect(page.locator("#diagnosis").getByText("객사길 테스트 매물", { exact: true })).toBeVisible();
  await expect(page.locator("#report").getByRole("button", { name: "PDF 다운로드" })).toBeAttached();
  const nav = page.getByRole("navigation", { name: "건물 분석 섹션" });
  await nav.getByRole("link", { name: "인허가", exact: true }).click();
  const checkbox = page.locator("#permits").getByRole("checkbox").first();
  await checkbox.check();
  await nav.getByRole("link", { name: "업종 순위", exact: true }).click();
  await page.locator("#ranking").getByRole("button", { name: /학원/ }).click();
  await nav.getByRole("link", { name: "리포트", exact: true }).click();
  await expect(page).toHaveURL("/diagnosis/b1#report");
  await nav.getByRole("link", { name: "인허가", exact: true }).click();
  await expect(checkbox).toBeChecked();
  await expect(page.locator("#ranking").getByRole("heading", { name: "학원 스코어 근거" })).toBeAttached();
  for (const path of ["/api/buildings/b1", "/api/buildings/b1/business-fit", "/api/buildings/b1/dashboard", "/api/buildings/b1/report", "/api/buildings/b1/permits"]) {
    expect(calls.filter((call) => call === path)).toHaveLength(1);
  }
});

test("고정 메뉴가 스크롤 위치를 표시하고 섹션 제목을 가리지 않는다", async ({ page }, testInfo) => {
  await page.goto("/diagnosis/b1");
  const nav = page.getByRole("navigation", { name: "건물 분석 섹션" });
  await nav.getByRole("link", { name: "전략", exact: true }).click();
  await expect(nav.getByRole("link", { name: "전략", exact: true })).toHaveAttribute("aria-current", "location");
  await expect.poll(async () => (await nav.boundingBox())!.y).toBe(0);
  const header = (await nav.boundingBox())!;
  const section = (await page.locator("#strategy-title").boundingBox())!;
  expect(section.y).toBeGreaterThanOrEqual(header.height);
  await page.screenshot({ path: testInfo.outputPath("analysis-desktop.png"), animations: "disabled" });
  await page.mouse.wheel(0, -1500);
  await expect(nav.getByRole("link", { name: "전략", exact: true })).not.toHaveAttribute("aria-current", "location");
  await expect.poll(async () => (await nav.boundingBox())!.y).toBe(0);
});

test("모바일 고정 메뉴와 긴 페이지에 가로 넘침이 없다", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/diagnosis/b1#report");
  const nav = page.getByRole("navigation", { name: "건물 분석 섹션" });
  await expect(page.getByRole("button", { name: "PDF 다운로드" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "리포트", exact: true })).toHaveAttribute("aria-current", "location");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect.poll(async () => (await nav.boundingBox())!.y).toBe(0);
  const link = (await nav.getByRole("link", { name: "리포트", exact: true }).boundingBox())!;
  expect(link.x + link.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: testInfo.outputPath("analysis-mobile.png"), animations: "disabled" });
});

test("일부 조회 실패는 해당 섹션에서 재시도하고 다른 섹션을 유지한다", async ({ page }) => {
  let fail = true;
  await page.route("**/api/buildings/b1/business-fit", (route) => fail ? route.fulfill({ status: 503, json: { detail: "일시적 오류" } }) : route.fulfill({ json: candidates }));
  await page.goto("/diagnosis/b1#ranking");
  await expect(page.locator("#ranking").getByRole("alert")).toBeVisible();
  await expect(page.locator("#diagnosis").getByText("객사길 테스트 매물", { exact: true })).toBeAttached();
  fail = false;
  await page.locator("#ranking").getByRole("button", { name: "다시 불러오기" }).click();
  await expect(page.locator("#ranking").getByRole("button", { name: /카페/ })).toBeVisible();
  await expect(page.locator("#permits").getByRole("checkbox")).toHaveCount(2);
});

test("기존 상세 주소는 해당 섹션으로 이동하고 리포트만 인쇄한다", async ({ page }) => {
  await page.goto("/ranking/b1");
  await expect(page).toHaveURL("/diagnosis/b1#ranking");
  await expect(page.locator("#ranking-title")).toBeVisible();
  await page.getByRole("navigation", { name: "건물 분석 섹션" }).getByRole("link", { name: "리포트", exact: true }).click();
  await expect(page.getByRole("button", { name: "PDF 다운로드" })).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("#report")).toBeVisible();
  await expect(page.locator("#diagnosis")).toBeHidden();
  await expect(page.locator(".analysis-nav")).toBeHidden();
});
