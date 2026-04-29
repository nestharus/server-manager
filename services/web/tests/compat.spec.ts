import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

type Contract = {
  routes: {
    public: { path: string; heading: string };
    application_form: { path: string; link_name: string };
    officer_queue?: { path: string; link_name: string; requires_auth: boolean };
    admin: { path: string; requires_auth: boolean };
  };
  auth: {
    identity?: { groups: string[]; discord_user_id: string | null };
    headers?: Record<string, string>;
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
      success_application_id: string;
      client_application_id_pattern: string;
      payload_fields: Array<{ name: string; value?: string | null; source_field?: string }>;
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

function payloadValue(payload: Record<string, unknown>, dottedPath: string): unknown {
  return dottedPath.split(".").reduce<unknown>((current, part) => {
    if (current && typeof current === "object" && part in current) {
      return (current as Record<string, unknown>)[part];
    }
    return undefined;
  }, payload);
}

function fieldValue(name: string): string {
  const field = contract.form.fields.find((candidate) => candidate.name === name);
  if (!field) {
    throw new Error(`missing form field fixture: ${name}`);
  }
  return field.value;
}

test("web UI routes public and auth-gated surfaces", async ({ page }) => {
  await page.route(`**${contract.auth.probe_endpoint}`, async (route) => {
    await route.fulfill({
      status: contract.auth.unauthenticated_api_status,
      contentType: "application/json",
      body: JSON.stringify({ detail: "authentication required" }),
    });
  });

  await page.goto(contract.routes.public.path);
  await expect(page.getByRole("heading", { name: contract.routes.public.heading })).toBeVisible();

  const status = await page.evaluate(async (endpoint) => {
    const response = await fetch(endpoint);
    return response.status;
  }, contract.auth.probe_endpoint);
  expect(status).toBe(contract.auth.unauthenticated_api_status);

  expect(contract.routes.admin.requires_auth).toBe(true);
});

const applicantDiscordTest = test.extend<{ applicantAuthApi: void; publicSubmitApi: void }>({
  applicantAuthApi: [
    async ({ page }, use) => {
      await page.route("**/auth/discord/me", async (route) => {
        const cookie = route.request().headers()["cookie"] ?? "";
        if (!cookie.includes("applicant_receipt=")) {
          await route.fulfill({
            status: 401,
            contentType: "application/json",
            body: JSON.stringify({ detail: "authentication required" }),
          });
          return;
        }

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ discord_user_id: "123456789012345678" }),
        });
      });
      await use();
    },
    { auto: true },
  ],
  publicSubmitApi: [
    async ({ page }, use) => {
      await page.route(`**${contract.form.submit.endpoint}`, async (route) => {
        const request = route.request();
        expect(request.method()).toBe(contract.form.submit.method);
        expect(request.headers()["x-discord-user-id"]).toBeUndefined();
        const payload = request.postDataJSON() as Record<string, unknown>;
        for (const field of contract.form.submit.payload_fields) {
          const expected =
            "source_field" in field && field.source_field
              ? fieldValue(field.source_field)
              : field.value;
          expect(payloadValue(payload, field.name)).toBe(expected);
        }
        await route.fulfill({
          status: contract.form.submit.success_status,
          contentType: "application/json",
          body: JSON.stringify({
            message: contract.form.submit.success_message,
            application_id: contract.form.submit.success_application_id,
          }),
        });
      });
      await use();
    },
    { auto: true },
  ],
});

const loggedInApplicantTest = applicantDiscordTest.extend<{ applicantReceiptCookie: void }>({
  applicantReceiptCookie: [
    async ({ context, baseURL }, use) => {
      await context.addCookies([
        {
          name: "applicant_receipt",
          value: "fixture-applicant-receipt",
          url: baseURL ?? "http://127.0.0.1:4173",
          httpOnly: true,
          secure: false,
          sameSite: "Lax",
        },
      ]);
      await use();
    },
    { auto: true },
  ],
});

const staleApplicantReceiptTest = test.extend<{ applicantReceiptCookie: void; expiringAuthApi: void }>({
  applicantReceiptCookie: [
    async ({ context, baseURL }, use) => {
      await context.addCookies([
        {
          name: "applicant_receipt",
          value: "expired-fixture-applicant-receipt",
          url: baseURL ?? "http://127.0.0.1:4173",
          httpOnly: true,
          secure: false,
          sameSite: "Lax",
        },
      ]);
      await use();
    },
    { auto: true },
  ],
  expiringAuthApi: [
    async ({ page }, use) => {
      let callCount = 0;
      await page.route("**/auth/discord/me", async (route) => {
        callCount += 1;
        if (callCount === 1) {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ discord_user_id: "123456789012345678" }),
          });
          return;
        }
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ code: "applicant_receipt_required" }),
        });
      });
      await use();
    },
    { auto: true },
  ],
});

applicantDiscordTest("applications page without receipt shows only Discord login", async ({ page }) => {
  // Risk annotation: group=TG-7; named_risk=spa_allows_anonymous_form_before_receipt;
  // level=component; source=.tmp/init-128/phase6/step6a-contract.md#C7.
  await page.goto(contract.form.route);

  const loginButton = page.getByRole("button", { name: "Login with Discord" });
  await expect(loginButton).toBeVisible();
  await expect(page.getByRole("form", { name: "Application form" })).toBeHidden();
  await expect(page.getByRole("button", { name: contract.form.submit.button_name })).toBeHidden();
  await loginButton.click();

  await expect(page).toHaveURL(/\/auth\/discord\/start\?return_to=\/applications$/);
});

applicantDiscordTest("test_anonymous_state_dom_tightening", async ({ page }) => {
  // Risk annotation: group=TG-5;
  //   named_risk=dom_tightening;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-5
  await page.goto(contract.form.route);

  await expect(page.locator("#discord-login")).toBeVisible();
  await expect(page.locator("#discord-login-state")).toHaveText("Not logged in with Discord.");
  await expect(page.locator("#tab-overview")).toHaveCount(0);
  await expect(page.locator("#tab-details")).toHaveCount(0);
  await expect(page.locator("#details-panel")).toHaveCount(0);
});

loggedInApplicantTest(
  "applications page with valid receipt shows form and Discord identity",
  async ({ page }) => {
    // Risk annotation: group=TG-7; named_risk=spa_receipt_state_not_verified;
    // level=component; source=.tmp/init-128/phase6/step6a-contract.md#C7.
    await page.goto(contract.form.route);

    await expect(page.getByRole("form", { name: "Application form" })).toBeVisible();
    await expect(page.getByText("Logged in as Discord 123456789012345678")).toBeVisible();
  },
);

loggedInApplicantTest("test_verified_state_details_panel_hidden_initially", async ({ page }) => {
  // Risk annotation: group=TG-5;
  //   named_risk=hidden_toggle;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-5
  await page.goto(contract.form.route);

  await expect(page.locator("#details-panel")).toHaveCount(1);
  await expect(page.locator("#details-panel")).toHaveAttribute("hidden", "");
  await page.getByRole("tab", { name: "Details" }).click();
  await expect(page.locator("#details-panel")).not.toHaveAttribute("hidden", "");
});

loggedInApplicantTest("web UI keeps Ark FontAwesome and TanStack controls integrated", async ({ page }) => {
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

  await page.getByRole("button", { name: contract.ui_libraries.ark.dialog_button_name }).click();
  await expect(page.getByRole("dialog")).toContainText(contract.ui_libraries.ark.dialog_text);
});

loggedInApplicantTest(
  "application form submits with a valid receipt and shows success",
  async ({ page }) => {
    // Risk annotation: group=TG-7; named_risk=spa_valid_receipt_submit_not_posted;
    // level=component; source=.tmp/init-128/phase6/step6a-contract.md#C7.
    await page.goto(contract.form.route);

    for (const field of contract.form.fields) {
      await page.getByLabel(field.label).fill(field.value);
    }
    const submitRequest = page.waitForRequest((request) => {
      const url = new URL(request.url());
      return (
        url.pathname === contract.form.submit.endpoint &&
        request.method() === contract.form.submit.method
      );
    });
    await page.getByRole("button", { name: contract.form.submit.button_name }).click();

    await submitRequest;
    await expect(page.locator("#submit-status")).toContainText(contract.form.submit.success_message);
  },
);

staleApplicantReceiptTest(
  "application submit with expired receipt redirects to Discord auth start",
  async ({ page }) => {
    // Risk annotation: group=TG-7; named_risk=spa_submit_skips_defensive_receipt_recheck;
    // level=component; source=.tmp/init-128/phase6/step6a-contract.md#C7.
    let posted = false;
    await page.route(`**${contract.form.submit.endpoint}`, async (route) => {
      posted = true;
      await route.abort();
    });

    await page.goto(contract.form.route);
    for (const field of contract.form.fields) {
      await page.getByLabel(field.label).fill(field.value);
    }
    await page.getByRole("button", { name: contract.form.submit.button_name }).click();

    await expect(page).toHaveURL(/\/auth\/discord\/start\?return_to=\/applications$/);
    expect(posted).toBe(false);
  },
);
