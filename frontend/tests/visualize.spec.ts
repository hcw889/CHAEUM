import { expect, test } from "@playwright/test";

/**
 * 공간 시각화(/visualize/[id]) — 팝업 브랜드가 입지를 고르며 컨셉 이미지를 확인하는 화면.
 *
 * 검증 관점:
 *  - 이미지 생성이 매칭 flow와 분리되어 있는가 (/api/match를 호출하지 않는가)
 *  - 생성 실패/미연결 환경에서도 화면이 죽지 않는가 (mock 폴백)
 */

const BUILDING_ID = "b1";

test("컨셉 이미지를 생성하면 Before/After에 실제 이미지가 표시된다", async ({ page }) => {
  const calledPaths: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.port === "8000") calledPaths.push(`${req.method()} ${url.pathname}`);
  });

  await page.goto(`/visualize/${BUILDING_ID}`);

  const concept = page.getByLabel(/컨셉/);
  await expect(concept).toBeVisible();
  await concept.fill("북유럽 감성 플라워 팝업");

  await page.getByRole("button", { name: "컨셉 이미지 생성" }).click();

  const after = page.getByRole("img", { name: /적용 이미지/ });
  await expect(after).toBeVisible({ timeout: 60_000 });
  await expect(after).toHaveAttribute("src", /^data:image\/png;base64,/);
  await expect(page.getByRole("img", { name: "현재 공간" })).toBeVisible();

  // 매칭 flow 엔드포인트를 건드리지 않는다 (기능 분리 확인)
  expect(calledPaths.filter((p) => p.includes("/api/match"))).toHaveLength(0);
  expect(calledPaths).toContain(`POST /api/buildings/${BUILDING_ID}/visualize`);
});

test("컨셉이 비어 있으면 생성하지 않고 안내한다", async ({ page }) => {
  await page.goto(`/visualize/${BUILDING_ID}`);
  const concept = page.getByLabel(/컨셉/);
  await expect(concept).not.toHaveValue("");
  await concept.fill("");
  await page.getByRole("button", { name: "컨셉 이미지 생성" }).click();
  await expect(page.getByText("컨셉을 입력해주세요.")).toBeVisible();
});

test("생성 API가 실패해도 화면이 죽지 않는다", async ({ page }) => {
  await page.route("**/api/buildings/*/visualize", (route) => route.fulfill({ status: 500, body: "boom" }));

  await page.goto(`/visualize/${BUILDING_ID}`);
  await page.getByRole("button", { name: "컨셉 이미지 생성" }).click();

  await expect(page.getByText(/API 요청 실패 \(500\)/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "시각화" })).toBeVisible();
});
