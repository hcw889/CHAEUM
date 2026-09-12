import { expect, test, type Page, type Request } from "@playwright/test";

/**
 * 팝업 브랜드 매칭 flow — 예비창업자와 동일한 화면·동일한 /api/match 재사용 검증.
 *
 * 이 스펙이 지키려는 원칙:
 *  1. 팝업 브랜드로 진입해도 신규 화면/신규 엔드포인트가 생기지 않는다.
 *  2. role별로 갈라지는 것은 문구와 입점 희망 기간 입력뿐이고, 단계 수와
 *     요청 형태는 동일하다.
 *  3. 입점 희망 기간은 전달만 되고 추천 결과를 바꾸지 않는다.
 */

const BACKEND_PORT = "8000";

/** 백엔드로 나간 요청 경로를 모두 기록한다. */
function recordApiCalls(page: Page): string[] {
  const calls: string[] = [];
  page.on("request", (req: Request) => {
    const url = new URL(req.url());
    if (url.port === BACKEND_PORT) calls.push(`${req.method()} ${url.pathname}`);
  });
  return calls;
}

/** 6단계를 끝까지 진행해 결과 화면까지 간다. */
async function completeWizard(page: Page) {
  for (let step = 1; step < 6; step++) {
    await page.getByRole("button", { name: "다음" }).click();
  }
  await page.getByRole("button", { name: /추천받기$/ }).click();
  await page.waitForURL("**/match/results");
}

test("온보딩에서 팝업 브랜드를 고르면 예비창업자와 같은 매칭 화면으로 간다", async ({ page }) => {
  await page.goto("/");
  await page.getByText("팝업 브랜드").click();

  await expect(page).toHaveURL("/match/new?role=brand");
  await expect(page.getByText("Step 1 / 6")).toBeVisible();
  await expect(page.getByText("팝업 브랜드", { exact: true })).toBeVisible();
});

test("role별로 Step 1 문구가 갈라진다", async ({ page }) => {
  await page.goto("/match/new?role=founder");
  await expect(page.getByRole("heading", { name: "어떤 업종을 계획 중이신가요?" })).toBeVisible();
  // 첫 렌더부터 확정되어야 한다 — 기본 문구가 잠깐 스쳤다 바뀌면 안 된다.
  await expect(page.getByRole("heading", { name: "어떤 브랜드/컨셉을 운영하시나요?" })).toHaveCount(0);

  await page.goto("/match/new?role=brand");
  await expect(page.getByRole("heading", { name: "어떤 브랜드/컨셉을 운영하시나요?" })).toBeVisible();
});

test("입점 희망 기간은 팝업 브랜드에만 보인다", async ({ page }) => {
  await page.goto("/match/new?role=founder");
  await expect(page.getByText("입점 희망 기간")).toHaveCount(0);

  await page.goto("/match/new?role=brand");
  await expect(page.getByText("입점 희망 기간")).toBeVisible();
  await expect(page.getByText("단기 (팝업·시즌)")).toBeVisible();
});

test("팝업 브랜드도 기존 /api/match 하나만 호출하고 결과가 정상 렌더된다", async ({ page }) => {
  const calls = recordApiCalls(page);
  const payloads: Record<string, unknown>[] = [];
  page.on("request", (req) => {
    if (req.url().includes("/api/match") && req.method() === "POST") {
      payloads.push(JSON.parse(req.postData() ?? "{}"));
    }
  });

  await page.goto("/match/new?role=brand");
  await page.getByText("장기", { exact: true }).click();
  await completeWizard(page);

  // 신규 엔드포인트가 생기지 않았다 — role에 따라 갈라지는 경로는 없고,
  // 매칭 스코어링을 부르는 경로는 여전히 POST /api/match 하나뿐이다.
  // GET /api/match/options는 role과 무관한 입력 화면 선택지 조회다 (실데이터로
  // 전환되면 매물이 실제로 수집된 지역만 보여야 하므로 필요하다).
  expect(calls.filter((call) => call === "POST /api/match")).toHaveLength(1);
  expect(new Set(calls)).toEqual(new Set(["GET /api/match/options", "POST /api/match"]));

  // 기존 6개 필드는 그대로, occupancy_term만 추가된다
  expect(payloads).toHaveLength(1);
  expect(Object.keys(payloads[0]).sort()).toEqual(
    ["area_pyeong", "budget", "business_type", "commercial_style_pref", "occupancy_term", "priority", "region_pref"],
  );
  expect(payloads[0].occupancy_term).toBe("장기");

  // 결과 화면은 예비창업자와 동일한 지도·추천 카드·상세 팝업을 쓴다.
  await expect(page.getByRole("heading", { name: "팝업 공간 추천 결과" })).toBeVisible();
  await expect(page.getByText("종합 매칭 점수")).toHaveCount(3);
  await page.getByRole("button", { name: "추천 1위 카드 상세 보기" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  // 추천 사유와 아이콘을 제외하고 점수 카드의 접근 가능한 제목을 확인한다.
  await expect(page.getByRole("dialog").getByRole("heading", { name: "예산 적합도", exact: true })).toBeVisible();
  await expect(page.getByRole("dialog").getByRole("heading", { name: "상권 적합도", exact: true })).toBeVisible();
  await expect(page.getByRole("dialog").getByRole("heading", { name: "건물 컨디션", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /건물 상세 진단 보기/ })).toBeVisible();
});

test("예비창업자 payload에는 occupancy_term이 없다", async ({ page }) => {
  const payloads: Record<string, unknown>[] = [];
  page.on("request", (req) => {
    if (req.url().includes("/api/match") && req.method() === "POST") {
      payloads.push(JSON.parse(req.postData() ?? "{}"));
    }
  });

  await page.goto("/match/new?role=founder");
  await completeWizard(page);

  expect(payloads[0]).not.toHaveProperty("occupancy_term");
  await expect(page.getByRole("heading", { name: "매물 추천 결과" })).toBeVisible();
});

test("입점 희망 기간은 추천 결과를 바꾸지 않는다 (스코어링 미반영)", async ({ page }) => {
  async function run(url: string, term?: string) {
    await page.goto(url);
    if (term) await page.getByText(term, { exact: true }).click();
    await completeWizard(page);
    return page.evaluate(() => sessionStorage.getItem("chaeum_match_result"));
  }

  const founder = await run("/match/new?role=founder");
  const brandShort = await run("/match/new?role=brand", "단기 (팝업·시즌)");
  const brandLong = await run("/match/new?role=brand", "장기");

  expect(brandShort).toBe(founder);
  expect(brandLong).toBe(founder);
});
