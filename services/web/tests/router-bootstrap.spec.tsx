import { expect, test } from "@playwright/test";

const principal = {
  subject: "sample-sub",
  email: "sample@local.humility.local",
  display_name: "Sample Officer",
  provider: "pomerium",
  groups: ["officers"],
  discord_user_id: "210987654321098765",
};

const chapters = {
  chapters: [
    {
      id: "chapter-alpha",
      name: "Alpha Chapter",
      state: "active",
      version: 1,
      created_at: "2026-04-30T12:00:00Z",
    },
  ],
};

test("admin chapters route mounts under QueryClientProvider", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.route("**/api/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(principal),
    });
  });
  await page.route("**/api/web/admin/chapters", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(chapters),
    });
  });
  await page.route("**/api/v1/web/admin/chapters", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(chapters),
    });
  });

  await page.goto("/admin/chapters");

  await expect(page.locator("#root")).not.toBeEmpty();
  await expect(page.getByRole("heading", { name: "Chapter administration" })).toBeVisible();
  expect(pageErrors).toEqual([]);
});
