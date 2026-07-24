import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test.use({
  launchOptions: {
    args: [
      "--host-resolver-rules=MAP *.lxzxai.com 127.0.0.1, MAP lxzxai.com 127.0.0.1",
    ],
  },
});

function localPort(): string {
  const base = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
  try {
    return new URL(base).port || "";
  } catch {
    return process.env.WEB_PORT ?? "3000";
  }
}

function tenantOrigin(subdomain: string): string {
  const port = localPort();
  const proto = (process.env.PLAYWRIGHT_BASE_URL ?? "http://").startsWith(
    "https",
  )
    ? "https"
    : "http";
  return port
    ? `${proto}://${subdomain}.lxzxai.com:${port}`
    : `${proto}://${subdomain}.lxzxai.com`;
}

async function registerUser(page: Page) {
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const subdomain = `e2e-${suffix}`.slice(0, 32);
  const email = `e2e-${suffix}@example.com`;
  const password = "password123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByLabel("子域（subdomain）").fill(subdomain);
  await page.getByRole("button", { name: "注册" }).click();

  await page.waitForURL(
    (url) =>
      url.hostname === `${subdomain}.lxzxai.com` &&
      url.pathname.startsWith("/admin"),
    { timeout: 20000 },
  );

  return { subdomain, email, password };
}

test("F12-T07 widget.js and harness have no rk_live_", async ({ page }) => {
  const widgetPath = path.join(__dirname, "..", "public", "widget.js");
  const text = fs.readFileSync(widgetPath, "utf8");
  expect(text).not.toContain("rk_live_");

  const { subdomain } = await registerUser(page);
  const res = await page.goto(`${tenantOrigin(subdomain)}/widget.js`);
  expect(res?.ok()).toBeTruthy();
  const body = await res!.text();
  expect(body).not.toContain("rk_live_");
  expect(body).toContain("data-site-key");
});

test("F12-T08 harness /widget contains widget snippet markers", async ({
  page,
}) => {
  const { subdomain } = await registerUser(page);
  await page.goto(`${tenantOrigin(subdomain)}/widget`);
  await expect(page.getByTestId("widget-harness")).toBeVisible();
  await expect(page.getByTestId("draft-hero")).toBeVisible();

  // After login, harness auto-creates a real pk_ and injects widget.js
  await expect
    .poll(async () => {
      return page.locator('script[src*="widget.js"][data-site-key^="pk_"]').count();
    }, { timeout: 20000 })
    .toBeGreaterThan(0);

  const html = await page.content();
  expect(html).toContain("widget.js");
  expect(html).toContain("data-site-key");
  expect(html).not.toContain("rk_live_");
  expect(html).not.toContain("pk_PLACEHOLDER");
});
