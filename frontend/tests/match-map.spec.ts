import { expect, test } from "@playwright/test";
import { mapMatches, mockMapTiles, seedMatchResults } from "./fixtures/match";

test.beforeEach(async ({ page }) => { await mockMapTiles(page); });

test("화면 대부분을 차지하는 지도에 상위 3개 매물만 표시한다", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await seedMatchResults(page);
  const apiCalls: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiCalls.push(request.url()); });
  await page.goto("/match/results");
  const map = page.getByRole("region", { name: "추천 TOP 3 매물 지도" });
  await expect(map.getByRole("button", { name: /추천 [123]위/ })).toHaveCount(3);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "왜 이 매물?" })).toHaveCount(0);
  const bounds = (await map.boundingBox())!;
  expect(bounds.width).toBeGreaterThan(1300);
  expect(bounds.height).toBeGreaterThan(700);
  await expect(page.getByText(/시연용 대표 좌표/)).toBeVisible();
  expect(apiCalls).toEqual([]);
  const screenshot = testInfo.outputPath("overview.png");
  await page.screenshot({ path: screenshot });
  await testInfo.attach("추천 지도 데스크톱", { path: screenshot, contentType: "image/png" });
});

test("각 순위 마커를 누르면 선택한 매물의 확대 지도와 추천 근거가 열린다", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await seedMatchResults(page);
  await page.goto("/match/results");
  const map = page.getByRole("region", { name: "추천 TOP 3 매물 지도" });
  for (const [index, match] of mapMatches.slice(0, 3).entries()) {
    const marker = map.getByRole("button", { name: `추천 ${index + 1}위 ${match.address} 상세 보기` });
    await marker.click();
    const dialog = page.getByRole("dialog", { name: match.address });
    await expect(dialog).toBeVisible();
    const closeup = dialog.getByRole("region", { name: "선택한 매물 확대 지도" });
    await expect(closeup.locator(".match-marker")).toHaveCount(1);
    await expect(closeup.locator(".match-marker")).toHaveAttribute("aria-label", `추천 ${index + 1}위 ${match.address} 상세 보기`);
    await expect(dialog.getByRole("heading", { name: "왜 이 매물?" })).toBeVisible();
    await expect(dialog.getByRole("region", { name: "예산 적합도" }).getByText(String(match.agent_scores.budget), { exact: true })).toBeVisible();
    await expect(dialog.getByRole("region", { name: "상권 적합도" }).getByText("이번 추천에서 가중치 60% 반영")).toBeVisible();
    await expect(dialog.getByRole("link", { name: "건물 상세 진단 보기 →" })).toHaveAttribute("href", `/diagnosis/${match.building_id}`);
    await expect(dialog.getByRole("link", { name: "주변 유동인구 보기 →" })).toHaveAttribute("href", `/visualize/${match.building_id}`);
    if (index === 0) {
      await expect(dialog.getByText("노출 59", { exact: true })).toBeVisible();
      const left = (await closeup.boundingBox())!;
      const right = (await dialog.locator(".match-detail-copy").boundingBox())!;
      expect(Math.abs(left.width - right.width)).toBeLessThan(3);
      expect(right.x).toBeGreaterThanOrEqual(left.x + left.width);
      const screenshot = testInfo.outputPath("detail-desktop.png");
      await page.screenshot({ path: screenshot });
      await testInfo.attach("매물 상세 데스크톱", { path: screenshot, contentType: "image/png" });
    }
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(marker).toBeFocused();
  }
});

test("키보드로 팝업을 열고 닫을 수 있으며 포커스가 팝업 안에 유지된다", async ({ page }) => {
  await seedMatchResults(page);
  await page.goto("/match/results");
  const marker = page.getByRole("region", { name: "추천 TOP 3 매물 지도" }).getByRole("button", { name: /추천 1위/ });
  await marker.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  const close = dialog.getByRole("button", { name: "매물 상세 닫기" });
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("link", { name: "주변 유동인구 보기 →" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await close.click();
  await expect(dialog).toHaveCount(0);
  await expect(marker).toBeFocused();
  expect(await page.locator("body").evaluate((body) => body.style.overflow)).not.toBe("hidden");
});

test("나머지 추천 매물도 목록에서 동일한 팝업으로 확인할 수 있다", async ({ page }) => {
  await seedMatchResults(page);
  await page.goto("/match/results");
  await page.getByText("다른 추천 매물 1개 보기", { exact: true }).click();
  await page.getByRole("button", { name: /전주시 노송동 4/ }).click();
  const dialog = page.getByRole("dialog", { name: "전주시 노송동 4" });
  await expect(dialog.getByRole("region", { name: "선택한 매물 확대 지도" })).toBeVisible();
  await expect(dialog.getByText("이 매물의 공간 분석 정보는 아직 제공되지 않습니다.")).toBeVisible();
});

test("위치가 없는 매물은 임의의 마커를 만들지 않고 상세 근거를 제공한다", async ({ page }) => {
  await seedMatchResults(page, mapMatches.map((match, i) => i === 0 ? { ...match, location: null } : match));
  await page.goto("/match/results");
  const map = page.getByRole("region", { name: "추천 TOP 3 매물 지도" });
  await expect(map.getByRole("button", { name: /추천 [123]위/ })).toHaveCount(2);
  await page.getByRole("button", { name: "추천 1위 카드 상세 보기" }).click();
  await expect(page.getByRole("dialog").getByText("이 매물의 위치 정보가 아직 없습니다.")).toBeVisible();
  await expect(page.getByRole("dialog").getByText("노출 59", { exact: true })).toBeVisible();
});

test("이전 세션은 좌표를 추가 조회하고 실패 후 재시도할 수 있다", async ({ page }) => {
  await seedMatchResults(page, mapMatches.map((match) => ({ ...match, location: undefined })));
  let fail = true;
  await page.route("**/api/buildings/locations", (route) => fail
    ? route.fulfill({ status: 503, body: "Unavailable" })
    : route.fulfill({ json: Object.fromEntries(mapMatches.map((match) => [match.building_id, match.location])) }));
  await page.goto("/match/results");
  await expect(page.getByText(/위치를 확인하지 못한 매물 3건/)).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "위치 다시 불러오기" }).click();
  const map = page.getByRole("region", { name: "추천 TOP 3 매물 지도" });
  await expect(map.getByRole("button", { name: /추천 [123]위/ })).toHaveCount(3);
});

test("배경 지도 요청이 실패해도 마커 선택과 상세 닫기가 동작한다", async ({ page }) => {
  await seedMatchResults(page);
  await page.route("https://tile.openstreetmap.org/**", (route) => route.abort());
  await page.goto("/match/results");
  await expect(page.getByText(/배경 지도를 불러오지 못했습니다/)).toBeVisible();
  await page.getByRole("region", { name: "추천 TOP 3 매물 지도" }).getByRole("button", { name: /추천 2위/ }).click();
  await expect(page.getByRole("dialog", { name: mapMatches[1].address })).toBeVisible();
  // 화면 바깥 배경을 클릭해 닫는다.
  await page.mouse.click(2, 2);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("모바일에서는 확대 지도 아래에 근거가 배치되고 가로로 넘치지 않는다", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await seedMatchResults(page);
  await page.goto("/match/results");
  await page.getByRole("button", { name: "추천 1위 카드 상세 보기" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("region", { name: "선택한 매물 확대 지도" }).locator(".match-marker")).toHaveCount(1);
  const left = (await dialog.getByRole("region", { name: "선택한 매물 확대 지도" }).boundingBox())!;
  const right = (await dialog.locator(".match-detail-copy").boundingBox())!;
  expect(right.y).toBeGreaterThanOrEqual(left.y + left.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const screenshot = testInfo.outputPath("detail-mobile.png");
  await page.screenshot({ path: screenshot });
  await testInfo.attach("매물 상세 모바일", { path: screenshot, contentType: "image/png" });
  await dialog.getByRole("link", { name: "주변 유동인구 보기 →" }).scrollIntoViewIfNeeded();
  await expect(dialog.getByRole("button", { name: "매물 상세 닫기" })).toBeVisible();
});

test("저장된 추천 결과가 없으면 입력으로 돌아가며 빈 추천은 안내한다", async ({ page }) => {
  await page.goto("/match/results");
  await expect(page).toHaveURL("/match/new");
  await seedMatchResults(page, []);
  await page.goto("/match/results");
  await expect(page.getByText("추천할 매물을 찾지 못했습니다.")).toBeVisible();
  await expect(page.getByRole("region", { name: "추천 TOP 3 매물 지도" })).toHaveCount(0);
});
