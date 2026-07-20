import { expect, test } from "@playwright/test";

test.describe("F01 registration", () => {
  test("F01-T07 register redirects with cookie domain", async ({ page }) => {
    test.skip(
      process.env.E2E_ENABLED !== "1",
      "Set E2E_ENABLED=1 with API+DB running",
    );

    const suffix = Date.now().toString(36);
    const subdomain = `e2e-${suffix}`.slice(0, 32);
    const email = `e2e-${suffix}@example.com`;

    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("密码").fill("password123");
    await page.getByLabel("子域（subdomain）").fill(subdomain);
    await page.getByRole("button", { name: "注册" }).click();

    await page.waitForURL(`https://${subdomain}.lxzxai.com/admin`, {
      timeout: 15000,
    });

    const cookies = await page.context().cookies();
    const sessionCookie = cookies.find((cookie) => cookie.name === "pb_session");
    expect(sessionCookie).toBeTruthy();
    expect(sessionCookie?.domain).toBe(".lxzxai.com");
  });
});
