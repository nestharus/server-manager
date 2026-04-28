import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

type Contract = {
  routes: {
    public: { path: string; heading: string };
    application_form: { path: string; link_name: string };
    admin: { path: string; requires_auth: boolean };
  };
  auth: {
    probe_endpoint: string;
    unauthenticated_api_status: number;
  };
  form: {
    route: string;
    fields: Array<{ name: string; label: string; value: string }>;
    submit: {
      button_name: string;
      endpoint: string;
      method: string;
      success_status: number;
      success_message: string;
    };
  };
  ui_libraries: {
    ark: { tab_name: string; dialog_button_name: string; dialog_text: string };
    fontawesome: { submit_icon_test_id: string; status_icon_test_id: string };
    tanstack: { navigation_link_name: string; resolved_path: string };
  };
};

function loadContract(): Contract {
  const candidates = [
    path.resolve(process.cwd(), "../../infra/tests/fixtures/web-ui/contract.json"),
    path.resolve(process.cwd(), "infra/tests/fixtures/web-ui/contract.json"),
  ];
  const contractPath = candidates.find((candidate) => fs.existsSync(candidate));
  if (!contractPath) {
    throw new Error(`contract.json not found in ${candidates.join(", ")}`);
  }
  return JSON.parse(fs.readFileSync(contractPath, "utf8")) as Contract;
}

const contract = loadContract();

test("web UI routes public and auth-gated surfaces", async ({ page }) => {
  await page.route(`**${contract.auth.probe_endpoint}`, async (route) => {
    await route.fulfill({
      status: contract.auth.unauthenticated_api_status,
      contentType: "application/json",
      body: JSON.stringify({ detail: "authentication required" }),
    });
  });

  await page.goto(contract.routes.public.path);
  await expect(
    page.getByRole("heading", { name: contract.routes.public.heading }),
  ).toBeVisible();

  const status = await page.evaluate(async (endpoint) => {
    const response = await fetch(endpoint);
    return response.status;
  }, contract.auth.probe_endpoint);
  expect(status).toBe(contract.auth.unauthenticated_api_status);

  expect(contract.routes.admin.requires_auth).toBe(true);
});

test("web UI submits the application form through the API contract", async ({ page }) => {
  let submitted = false;

  await page.route(`**${contract.form.submit.endpoint}`, async (route) => {
    const request = route.request();
    expect(request.method()).toBe(contract.form.submit.method);
    const payload = request.postDataJSON() as Record<string, unknown>;
    for (const field of contract.form.fields) {
      expect(payload[field.name]).toBe(field.value);
    }
    submitted = true;
    await route.fulfill({
      status: contract.form.submit.success_status,
      contentType: "application/json",
      body: JSON.stringify({ message: contract.form.submit.success_message }),
    });
  });

  await page.goto(contract.form.route);
  for (const field of contract.form.fields) {
    await page.getByLabel(field.label).fill(field.value);
  }
  await page.getByRole("button", { name: contract.form.submit.button_name }).click();

  await expect(page.getByText(contract.form.submit.success_message)).toBeVisible();
  expect(submitted).toBe(true);
});

test("web UI keeps Ark FontAwesome and TanStack controls integrated", async ({ page }) => {
  await page.goto(contract.routes.public.path);

  await page
    .getByRole("link", { name: contract.ui_libraries.tanstack.navigation_link_name })
    .click();
  await expect(page).toHaveURL(new RegExp(`${contract.ui_libraries.tanstack.resolved_path}$`));

  await page.getByRole("tab", { name: contract.ui_libraries.ark.tab_name }).click();
  await expect(
    page.getByTestId(contract.ui_libraries.fontawesome.status_icon_test_id),
  ).toBeVisible();
  await expect(
    page.getByTestId(contract.ui_libraries.fontawesome.submit_icon_test_id),
  ).toBeVisible();

  await page
    .getByRole("button", { name: contract.ui_libraries.ark.dialog_button_name })
    .click();
  await expect(page.getByRole("dialog")).toContainText(contract.ui_libraries.ark.dialog_text);
});
