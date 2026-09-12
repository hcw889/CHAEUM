import { expect, test, type Page } from "@playwright/test";
import { mapMatches, mockMapTiles, seedMatchResults } from "./fixtures/match";

async function installSdk(page: Page, mode: "ready" | "unavailable" | "retry" = "ready") {
  await page.addInitScript((mode) => {
    let loads = 0;
    const events = new WeakMap<object, () => void>();
    class LatLng {
      constructor(private lat: number, private lng: number) {}
      getLat() { return this.lat; }
      getLng() { return this.lng; }
    }
    class Roadview {
      position = new LatLng(35.818, 127.143);
      constructor(private container: HTMLElement) {}
      getPosition() { return this.position; }
      setPanoId(id: number, position: LatLng) {
        this.position = position;
        this.container.textContent = `파노라마 ${id}`;
        this.container.dataset.latitude = String(position.getLat());
        queueMicrotask(() => events.get(this)?.());
      }
      setViewpoint() {}
      relayout() {}
    }
    Object.defineProperty(window, "kakao", { configurable: true, value: { maps: {
      load(callback: () => void) {
        loads++;
        if (mode === "retry" && loads === 1) throw new Error("일시적 SDK 실패");
        callback();
      },
      LatLng, Roadview,
      RoadviewClient: class {
        getNearestPanoId(_position: LatLng, radius: number, callback: (id: number | null) => void) {
          queueMicrotask(() => callback(mode === "unavailable" || radius < 150 ? null : 123));
        }
      },
      event: {
        addListener(target: object, _type: string, handler: () => void) { events.set(target, handler); },
        removeListener(target: object) { events.delete(target); },
      },
      services: {
        Geocoder: class {
          addressSearch(_address: string, callback: (results: { x: string; y: string }[], status: string) => void) {
            callback([{ x: "127.143", y: "35.818" }], "OK");
          }
        },
        Status: { OK: "OK" },
      },
    } } });
  }, mode);
}

test.beforeEach(async ({ page }) => {
  await mockMapTiles(page);
  await seedMatchResults(page, [{ ...mapMatches[0], lat: 35.819, lng: 127.144, photo_url: "https://picsum.photos/seed/unrelated/800/600" }]);
});

async function openDetail(page: Page) {
  await page.goto("/match/results");
  await page.getByRole("button", { name: "추천 1위 카드 상세 보기" }).click();
  return page.getByRole("region", { name: "매물 로드뷰", exact: true });
}

test("키나 SDK 연결이 없으면 원인을 안내하고 임시 사진을 요청하지 않는다", async ({ page }) => {
  const photos: string[] = [];
  page.on("request", (request) => { if (request.url().includes("picsum.photos")) photos.push(request.url()); });
  await page.route("https://dapi.kakao.com/**", (route) => route.abort());
  const panel = await openDetail(page);
  await expect(panel.getByRole("status")).toContainText(/연결이 아직 설정되지 않았습니다|불러오지 못했습니다/);
  await expect(panel.locator("img")).toHaveCount(0);
  await expect(panel.getByRole("link", { name: "카카오맵에서 로드뷰 보기 ↗" })).toHaveAttribute("href", "https://map.kakao.com/link/roadview/35.819,127.144");
  expect(photos).toEqual([]);
});

test("정확한 좌표로 반경을 넓혀 파노라마를 표시하고 재진입해도 정상 동작한다", async ({ page }) => {
  await installSdk(page);
  const panel = await openDetail(page);
  await expect(panel.getByRole("status")).toContainText("카카오 로드뷰");
  await expect(panel.locator("[data-latitude]")).toHaveAttribute("data-latitude", "35.819");
  await expect(panel.getByText("파노라마 123")).toBeVisible();
  await page.getByRole("button", { name: "매물 상세 닫기" }).click();
  await page.getByRole("button", { name: "추천 1위 카드 상세 보기" }).click();
  await expect(panel.getByRole("status")).toContainText("카카오 로드뷰");
});

test("촬영 지점이 없는 경우 연결 오류와 구분해 안내한다", async ({ page }) => {
  await installSdk(page, "unavailable");
  const panel = await openDetail(page);
  await expect(panel.getByRole("status")).toHaveText("이 위치 주변에서 제공되는 로드뷰를 찾지 못했습니다.");
  await expect(panel.locator("img")).toHaveCount(0);
});

test("SDK의 일시적인 실패는 재시도로 복구한다", async ({ page }) => {
  await installSdk(page, "retry");
  const panel = await openDetail(page);
  await expect(panel.getByRole("status")).toContainText("불러오지 못했습니다");
  await panel.getByRole("button", { name: "로드뷰 다시 불러오기" }).click();
  await expect(panel.getByRole("status")).toContainText("카카오 로드뷰");
});
