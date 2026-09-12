import { defineConfig, devices } from "@playwright/test";

/**
 * 프론트(next dev)는 Playwright가 자동 기동한다.
 * 백엔드(uvicorn :8000)는 별도로 띄워둬야 한다 — README 실행 방법 참고.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
