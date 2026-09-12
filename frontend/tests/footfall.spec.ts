import { expect, test, type Page } from "@playwright/test";

/**
 * 매칭 결과 화면의 "주변 유동인구" 대시보드.
 *
 * 이 스펙이 지키려는 것:
 *  1. 추천 매물을 고르면 그 매물 기준 유동인구가 따라온다.
 *  2. 시간대/요일을 바꾸면 표시 값이 바뀐다 (지도 색의 근거가 되는 수치).
 *  3. 유동인구 조회가 실패해도 매칭 결과 자체는 그대로 보인다.
 *
 * 백엔드(uvicorn :8000)가 떠 있어야 한다.
 */

async function goToResults(page: Page) {
  await page.goto("/match/new?role=founder");
  for (let step = 1; step < 6; step++) {
    await page.getByRole("button", { name: "다음" }).click();
  }
  await page.getByRole("button", { name: /추천받기$/ }).click();
  await page.waitForURL("**/match/results");
}

test("추천 매물 주변 유동인구가 결과 화면에 표시된다", async ({ page }) => {
  await goToResults(page);

  await expect(page.getByRole("heading", { name: "주변 유동인구" })).toBeVisible();
  await expect(page.getByText("하루 유동인구")).toBeVisible();
  await expect(page.getByText("피크 시간대")).toBeVisible();
  await expect(page.getByText("도보권(500m)")).toBeVisible();
  // 구역 목록 (backend footfall_areas.json의 min_areas 이상)
  await expect(page.getByRole("button", { name: /명$/ }).first()).toBeVisible();
  // 색 범례와 지도가 같이 있어야 색으로 읽을 수 있다.
  await expect(page.getByRole("region", { name: "추천 매물 주변 유동인구 지도" })).toBeVisible();
  await expect(page.getByText("색 기준: 구역 중 최댓값 대비 상대값")).toBeVisible();
});

test("매물을 바꾸면 유동인구도 그 매물 기준으로 다시 조회된다", async ({ page }) => {
  const calls: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.pathname.includes("/footfall")) calls.push(url.pathname);
  });

  await goToResults(page);
  await expect(page.getByRole("heading", { name: "주변 유동인구" })).toBeVisible();
  const first = calls.at(-1);

  // 상위 3개 카드 중 아직 선택되지 않은 카드를 누른다.
  await page.locator("button", { has: page.getByText("종합 매칭 점수") }).nth(1).click();
  await expect.poll(() => calls.at(-1)).not.toBe(first);
});

test("평일/주말 전환이 유동인구 수치를 바꾼다", async ({ page }) => {
  await goToResults(page);
  await expect(page.getByRole("heading", { name: "주변 유동인구" })).toBeVisible();

  const dailyTotal = page.getByText("하루 유동인구").locator("xpath=following-sibling::p[1]");
  const weekday = await dailyTotal.textContent();

  await page.getByRole("button", { name: "주말" }).click();
  await expect.poll(async () => dailyTotal.textContent()).not.toBe(weekday);
});

test("유동인구 조회가 실패해도 매칭 결과는 그대로 보인다", async ({ page }) => {
  await page.route("**/footfall**", (route) => route.abort());
  await goToResults(page);

  await expect(page.getByText("종합 매칭 점수").first()).toBeVisible();
  await expect(page.getByText("주변 유동인구를 불러오지 못했습니다.")).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 불러오기" })).toBeVisible();
});
