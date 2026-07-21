import { expect, test, type Page } from "@playwright/test";

async function registerUser(page: Page) {
  const suffix = Date.now().toString(36);
  const subdomain = `e2e-${suffix}`.slice(0, 32);
  const email = `e2e-${suffix}@example.com`;
  const password = "password123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByLabel("子域（subdomain）").fill(subdomain);
  await page.getByRole("button", { name: "注册" }).click();

  await page.waitForURL(`https://${subdomain}.lxzxai.com/admin`, {
    timeout: 15000,
  });

  return { subdomain, email, password };
}

async function loginUser(
  page: Page,
  email: string,
  password: string,
  subdomain: string,
) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL(`https://${subdomain}.lxzxai.com/`, {
    timeout: 15000,
  });
}

test.describe("F02 email auth", () => {
  test.beforeEach(({ page }) => {
    test.skip(
      process.env.E2E_ENABLED !== "1",
      "Set E2E_ENABLED=1 with API+DB running",
    );
  });

  test("F02-T03 authenticated admin page reachable", async ({ page }) => {
    await registerUser(page);
    await expect(page.getByRole("heading", { name: "管理" })).toBeVisible({
      timeout: 10000,
    });
  });

  test("F02-T04 unauthenticated admin redirects to login", async ({ page }) => {
    const { subdomain } = await registerUser(page);
    await page.context().clearCookies();
    await page.goto(`https://${subdomain}.lxzxai.com/admin`);
    await page.waitForURL(/lxzxai\.com\/login/, { timeout: 15000 });
  });

  test("F02-T06 logout then admin requires login", async ({ page }) => {
    const { subdomain, email, password } = await registerUser(page);
    await loginUser(page, email, password, subdomain);

    const logout = await page.request.post("/backend/api/v1/auth/logout", {
      headers: { Host: `${subdomain}.lxzxai.com` },
    });
    expect(logout.status()).toBe(204);

    await page.context().clearCookies();
    await page.goto(`https://${subdomain}.lxzxai.com/admin`);
    await page.waitForURL(/lxzxai\.com\/login/, { timeout: 15000 });
  });

  test("F02-T09 tenant /register redirects to apex", async ({ page }) => {
    const { subdomain } = await registerUser(page);
    await page.goto(`https://${subdomain}.lxzxai.com/register`);
    await page.waitForURL(/lxzxai\.com\/register/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "注册" })).toBeVisible();
  });
});
