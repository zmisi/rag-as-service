import { expect, test, type Page } from "@playwright/test";

test.use({
  // Local /etc/hosts often only lists apex + a few tenants; map all *.lxzxai.com.
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

async function openPortal(page: Page, subdomain: string) {
  await page.goto(`${tenantOrigin(subdomain)}/chat`);
  await expect(page.getByTestId("portal-shell")).toBeVisible({
    timeout: 15000,
  });
}

test.describe("F14 portal shell", () => {
  test.beforeEach(() => {
    test.skip(
      process.env.E2E_ENABLED !== "1",
      "Set E2E_ENABLED=1 with API+DB+web running",
    );
  });

  test("F14-T01 New task does not POST /conversations", async ({ page }) => {
    const { subdomain } = await registerUser(page);
    await openPortal(page, subdomain);

    let createPosted = false;
    page.on("request", (req) => {
      if (
        req.method() === "POST" &&
        /\/backend\/v1\/conversations\/?$/.test(req.url())
      ) {
        createPosted = true;
      }
    });

    const listBefore = page.getByTestId("conversation-list");
    const countBefore = await listBefore.locator(".conv-item").count();

    await page.getByTestId("new-task").click();
    await expect(page.getByTestId("draft-hero")).toBeVisible();
    await page.waitForTimeout(400);

    expect(createPosted).toBe(false);
    const countAfter = await listBefore.locator(".conv-item").count();
    expect(countAfter).toBe(countBefore);
  });

  test("F14-T03 desktop shell has sidebar main composer", async ({ page }) => {
    const { subdomain } = await registerUser(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await openPortal(page, subdomain);

    await expect(page.getByTestId("portal-sidebar")).toBeVisible();
    await expect(page.getByTestId("portal-main")).toBeVisible();
    await expect(page.getByTestId("portal-composer")).toBeVisible();
    await expect(page.getByTestId("portal-sidebar")).not.toHaveClass(
      /sidebar-collapsed/,
    );
  });

  test("F14-T04 draft hero hides when conversation selected", async ({
    page,
  }) => {
    const { subdomain } = await registerUser(page);
    await openPortal(page, subdomain);

    await expect(page.getByTestId("draft-hero")).toBeVisible();

    const create = await page.request.post(
      "/backend/v1/conversations/messages",
      {
        headers: {
          Host: `${subdomain}.lxzxai.com`,
          "X-Forwarded-Host": `${subdomain}.lxzxai.com`,
          "Content-Type": "application/json",
        },
        data: { role: "user", content: "e2e seeded conversation" },
      },
    );
    expect(create.status()).toBe(201);
    const body = await create.json();
    expect(body.conversation_id).toBeTruthy();

    await page.reload();
    await expect(page.getByTestId("portal-shell")).toBeVisible();
    await page.getByTestId("new-task").click();
    await expect(page.getByTestId("draft-hero")).toBeVisible();

    await page
      .locator(`[data-conversation-id="${body.conversation_id}"] .conv-main`)
      .click();
    await expect(page.getByTestId("draft-hero")).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "e2e seeded conversation" }),
    ).toBeVisible();
    await expect(page.locator(".bubble.role-user")).toContainText(
      "e2e seeded conversation",
    );
  });
});
