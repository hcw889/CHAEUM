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

test("업로드 없이도 매물 사진이 바로 보인다", async ({ page }) => {
  // 이 화면의 사용자는 공간을 "찾는" 쪽이라 공실 사진을 갖고 있지 않다.
  // 사진은 매물 데이터에서 와야 하고, 업로드는 선택 사항이어야 한다.
  await page.goto(`/visualize/${BUILDING_ID}`);

  const before = page.getByRole("img", { name: "현재 공간" });
  await expect(before).toBeVisible();
  await expect(before).toHaveAttribute("src", /^data:image\/png;base64,/);

  // 업로드 버튼은 "필수 입력"이 아니라 대체 수단으로 제시된다
  await expect(page.getByRole("button", { name: "다른 사진으로 해보기" })).toBeVisible();
  // 참고용 이미지를 실제 촬영본인 것처럼 보여주지 않는다
  await expect(page.getByText(/촬영 사진 미등록|매물 등록 사진 사용 중/)).toBeVisible();
});

test("시공 전/후 촬영본이 있는 매물은 생성물이 아님을 명시한다", async ({ page, request }) => {
  // 매물 사진은 저작권 확인이 끝난 것만 커밋하므로 저장소에 없을 수 있다.
  // (backend/app/data/photos/README.md 참고)
  const photo = await (await request.get(`http://localhost:8000/api/buildings/${BUILDING_ID}/photo`)).json();
  test.skip(!photo.has_after, "b1 시공 후 사진이 없는 환경");

  await page.goto(`/visualize/${BUILDING_ID}`);
  await page.getByLabel(/컨셉/).fill("북유럽 감성 플라워 팝업");
  await page.getByRole("button", { name: /컨셉 이미지 생성|다시 생성/ }).click();
  await page.getByRole("img", { name: /적용 이미지/ }).waitFor({ timeout: 60_000 });

  // 실제 사진임을 밝히고, 컨셉이 반영된 것처럼 라벨링하지 않는다
  await expect(page.getByText("생성 방식: 실제 시공 전/후 사진", { exact: false })).toBeVisible();
  await expect(page.getByText(/AI 생성 결과가 아니며/)).toBeVisible();
  await expect(page.getByText("시공 후", { exact: true })).toBeVisible();
  await expect(page.getByText("북유럽 감성 플라워 팝업 적용")).toHaveCount(0);
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
