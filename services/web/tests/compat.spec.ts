import { expect, test } from "@playwright/test";

test("Solid 2 renders public form and Ark UI compatibility controls", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dark Nemesis application" })).toBeVisible();
  await expect(page.getByLabel("What is your in-game name?")).toBeVisible();
  await page.getByRole("tab", { name: "Details" }).click();
  await page.getByRole("button", { name: "Open dialog" }).click();
  await expect(page.getByRole("dialog")).toContainText("Ark UI Solid primitives render");
});

test("toolbar uses roving tabindex keyboard behavior", async ({ page }) => {
  await page.goto("/");
  const toolbar = page.getByRole("toolbar", { name: "Form actions" });
  await toolbar.getByRole("button", { name: "Draft" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(toolbar.getByRole("button", { name: "Reset" })).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(toolbar.getByRole("button", { name: "Draft" })).toBeFocused();
});
