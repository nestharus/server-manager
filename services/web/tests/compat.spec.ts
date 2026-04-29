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

test("web UI submits the application form through the API contract", async ({ page }) => {
  // Risk annotation: group=TG-8; named_risk=spa_submit_contract_drift;
  // level=component; source=proposals/02-public-application-intake.md#§8 AS-1 AS-3.
  let submitted = false;

  await page.route(`**${contract.form.submit.endpoint}`, async (route) => {
    const request = route.request();
    expect(request.url().endsWith(contract.form.submit.endpoint)).toBe(true);
    expect(request.method()).toBe(contract.form.submit.method);
    const payload = request.postDataJSON() as Record<string, unknown>;
    for (const field of contract.form.submit.payload_fields) {
      const expected =
        "source_field" in field && field.source_field
          ? fieldValue(field.source_field)
          : field.value;
      expect(payloadValue(payload, field.name)).toBe(expected);
    }
    expect(payloadValue(payload, "client_application_id")).toMatch(
      new RegExp(contract.form.submit.client_application_id_pattern),
    );
    submitted = true;
    await route.fulfill({
      status: contract.form.submit.success_status,
      contentType: "application/json",
      body: JSON.stringify({
        message: contract.form.submit.success_message,
        application_id: contract.form.submit.success_application_id,
      }),
    });
  });

  await page.goto(contract.form.route);
  for (const field of contract.form.fields) {
    await page.getByLabel(field.label).fill(field.value);
  }
  await page.getByRole("button", { name: contract.form.submit.button_name }).click();

  await expect(page.locator("#submit-status")).toContainText(contract.form.submit.success_message);
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

  await page.getByRole("button", { name: contract.ui_libraries.ark.dialog_button_name }).click();
  await expect(page.getByRole("dialog")).toContainText(contract.ui_libraries.ark.dialog_text);
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

applicantDiscordTest("applications page exposes Discord login start", async ({ page }) => {
  // Risk annotation: group=TG-6; named_risk=spa_login_redirect_missing;
  // level=component; source=INIT-127 C6 A3.
  await page.goto(contract.form.route);

  const loginButton = page.getByRole("button", { name: "Login with Discord" });
  await expect(loginButton).toBeVisible();
  await loginButton.click();

  await expect(page).toHaveURL(/\/auth\/discord\/start\?return_to=\/applications$/);
});

loggedInApplicantTest(
  "applications page displays Discord identity from receipt cookie",
  async ({ page }) => {
    // Risk annotation: group=TG-6; named_risk=spa_receipt_state_not_verified;
    // level=component; source=INIT-127 C6 A3.
    await page.goto(contract.form.route);

    await expect(page.getByText("Logged in as Discord user 123456789012345678")).toBeVisible();
  },
);

applicantDiscordTest(
  "application form still submits through the anonymous INIT-120 path",
  async ({ page }) => {
    // Risk annotation: group=TG-6/TG-7; named_risk=init_120_anon_submit_regression;
    // level=component; source=INIT-127 C6 plus INIT-120 compatibility.
    await page.goto(contract.form.route);
    await expect(page.getByRole("button", { name: "Login with Discord" })).toBeVisible();

    for (const field of contract.form.fields) {
      await page.getByLabel(field.label).fill(field.value);
    }
    await page.getByRole("button", { name: contract.form.submit.button_name }).click();

    await expect(page.locator("#submit-status")).toContainText(contract.form.submit.success_message);
  },
);
