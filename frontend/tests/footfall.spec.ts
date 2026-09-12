import { expect, test } from "@playwright/test";
import { footfallResponse, mockFootfallApi } from "./fixtures/footfall";

test.beforeEach(async ({ page }) => {
  await mockFootfallApi(page);
});

test("유동인구 지도와 요약을 표시하고 타일 실패 시에도 구역을 비교할 수 있다", async ({ page }) => {
  await page.goto("/visualize/b1");
  await expect(page.getByRole("heading", { name: "주변 유동인구", exact: true })).toBeVisible();
  await expect(page.getByText("3,950명", { exact: true })).toBeVisible();
  await expect(page.getByText("피크 시간대", { exact: true })).toBeVisible();
  await expect(page.getByText("도보권(500m)", { exact: true })).toBeVisible();
  const map = page.getByRole("region", { name: "추천 매물 주변 유동인구 지도" });
  await expect(map).toBeVisible();
  // 출처 로고의 SVG는 제외하고 실제 지도 구역 2개와 매물 위치만 센다.
  await expect(map.locator(".leaflet-pane svg path")).toHaveCount(3);
  await expect(page.getByText("색 기준: 구역 중 최댓값 대비 상대값")).toBeVisible();
  await expect(page.getByText(/배경 지도를 불러오지 못했습니다/)).toBeVisible();
  await page.getByRole("button", { name: /^남쪽 상권/ }).click();
  await expect(page.getByText(/하루 1,550명 · 피크 12시 · 매물에서 650m/)).toBeVisible();
});

test("평일과 주말 전환이 수치와 집계 기준일을 바꾼다", async ({ page }) => {
  await page.goto("/visualize/b1");
  await expect(page.getByText("3,950명", { exact: true })).toBeVisible();
  await expect(page.getByText(/2026.09.04 기준/)).toBeVisible();
  await page.getByRole("button", { name: "주말", exact: true }).click();
  await expect(page.getByText("7,900명", { exact: true })).toBeVisible();
  await expect(page.getByText(/2026.09.05 기준/)).toBeVisible();
  await page.getByRole("button", { name: "평일", exact: true }).click();
  await expect(page.getByText("3,950명", { exact: true })).toBeVisible();
});

test("시간대를 바꾸면 구역 수치와 순위가 바뀌고 하루 전체로 돌아갈 수 있다", async ({ page }) => {
  await page.goto("/visualize/b1");
  const areas = page.getByRole("button", { name: /^(북쪽|남쪽) 상권/ });
  await expect(areas.first()).toContainText("북쪽 상권");
  const slider = page.getByRole("slider", { name: "시간대" });
  await slider.fill("12");
  await expect(slider).toHaveAttribute("aria-valuetext", "12시");
  await expect(areas.first()).toContainText("남쪽 상권");
  await expect(areas.first()).toContainText("400명");
  await page.getByTitle("00시 150명", { exact: true }).click();
  await expect(slider).toHaveValue("0");
  await expect(areas.first()).toContainText("북쪽 상권");
  await expect(areas.first()).toContainText("100명");
  await slider.fill("-1");
  await expect(areas.first()).toContainText("2,400명");
});

test("조회 실패를 안내하고 재시도로 데이터를 복구한다", async ({ page }) => {
  let failed = true;
  await page.route("**/api/buildings/b1/footfall?**", (route) =>
    failed
      ? route.fulfill({ status: 503, json: { detail: "일시적인 조회 실패" } })
      : route.fulfill({ json: footfallResponse() }),
  );
  await page.goto("/visualize/b1");
  await expect(page.getByText("주변 유동인구를 불러오지 못했습니다.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "유동인구 시각화" })).toBeVisible();
  await expect(page.getByRole("link", { name: "진단 결과", exact: true })).toBeVisible();
  failed = false;
  await page.getByRole("button", { name: "다시 불러오기", exact: true }).click();
  await expect(page.getByText("3,950명", { exact: true })).toBeVisible();
  await expect(page.getByText("주변 유동인구를 불러오지 못했습니다.")).toHaveCount(0);
});

test("없는 매물로 직접 진입하면 오류를 표시하고 다른 매물을 선택할 수 있다", async ({ page }) => {
  await page.goto("/visualize/unknown");
  await expect(page.getByText("주변 유동인구를 불러오지 못했습니다.")).toBeVisible();
  await expect(page.getByText("하루 유동인구", { exact: true })).toHaveCount(0);
  await page.getByRole("combobox", { name: "데모 매물" }).selectOption("b2");
  await expect(page).toHaveURL("/visualize/b2");
  await expect(page.getByText(/전주시 태평동 2 반경/)).toBeVisible();
});

test("모바일에서도 지도와 시간대 조작을 사용할 수 있다", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/visualize/b1");
  await expect(page.getByRole("region", { name: "추천 매물 주변 유동인구 지도" })).toBeVisible();
  await page.getByRole("slider", { name: "시간대" }).fill("12");
  await expect(page.getByRole("button", { name: /^남쪽 상권/ })).toContainText("400명");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
