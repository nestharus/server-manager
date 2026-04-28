import { existsSync, readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const flow = process.env.E2E_BROWSER_FLOW;
const sessionDir = process.env.E2E_SESSION_DIR;
const username = process.env.AUTHENTIK_USERNAME;
const password = process.env.AUTHENTIK_PASSWORD;

if (!flow || !sessionDir || !username || !password) {
  throw new Error("E2E_BROWSER_FLOW, E2E_SESSION_DIR, AUTHENTIK_USERNAME, and AUTHENTIK_PASSWORD are required");
}

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, "../../../../..");
const webContract = JSON.parse(
  readFileSync(resolve(repoRoot, "infra/tests/fixtures/web-ui/contract.json"), "utf8"),
);

const targets = {
  "auth-stack": {
    url: "https://protected-api.local.humility.local/api/v1/protected/authz-proof",
    assert: async (page) => {
      await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {});
      const body = await page.locator("body").innerText({ timeout: 10_000 });
      if (!body.includes("Allow") || !body.includes("sample@local.humility.local")) {
        throw new Error(`protected API did not return Allow proof: ${body.slice(0, 500)}`);
      }
    },
  },
  "web-ui": {
    url: "https://web.local.humility.local/admin/chapters",
    assert: async (page) => {
      await page.getByRole("heading", { name: "Chapter administration" }).waitFor({ timeout: 30_000 });
      await page.getByTestId("chapter-table").waitFor({ timeout: 30_000 });
      await page.goto(`https://web.local.humility.local${webContract.form.route}`, {
        waitUntil: "domcontentloaded",
        timeout: 45_000,
      });
      await page.route(`**${webContract.form.submit.endpoint}`, async (route) => {
        const request = route.request();
        if (request.method() !== webContract.form.submit.method) {
          await route.continue();
          return;
        }
        let payload;
        try {
          payload = JSON.parse(request.postData() ?? "");
        } catch (error) {
          throw new Error(`application submit body was not JSON: ${error.message}`);
        }
        for (const field of webContract.form.fields) {
          if (!Object.hasOwn(payload, field.name)) {
            throw new Error(`application submit body missing field: ${field.name}`);
          }
        }
        await route.fulfill({
          status: webContract.form.submit.success_status,
          contentType: "application/json",
          body: JSON.stringify({ message: webContract.form.submit.success_message }),
        });
      });
      await page.getByRole("heading", { name: "Humility applications" }).waitFor({ timeout: 30_000 });
      for (const field of webContract.form.fields) {
        await page.getByLabel(field.label).fill(field.value);
      }
      await page.getByRole("button", { name: webContract.form.submit.button_name }).click();
      await page.getByText(webContract.form.submit.success_message).waitFor({ timeout: 30_000 });
    },
  },
};

const target = targets[flow];
if (!target) {
  throw new Error(`unknown browser flow: ${flow}`);
}

async function loginIfNeeded(page) {
  await page.waitForLoadState("domcontentloaded", { timeout: 30_000 }).catch(() => {});
  if (!/auth\.local\.humility\.local|authenticate\.local\.humility\.local/.test(page.url())) {
    return;
  }

  // If we're on Pomerium's intermediate sign_in endpoint, wait for the
  // upstream redirect to land us on the Authentik IdP login screen.
  if (/authenticate\.local\.humility\.local\/\.pomerium\/sign_in/.test(page.url())) {
    await page
      .waitForURL(/auth\.local\.humility\.local/, { timeout: 30_000, waitUntil: "domcontentloaded" })
      .catch(() => {});
  }

  // Authentik 2026.x uses Lit web components (<ak-stage-identification>,
  // <ak-stage-password>) with form inputs in the shadow root. Playwright's
  // locator engine pierces shadow DOM, so we drive the form by clicking
  // through actual input elements — preserving the OAuth state cookies
  // that Pomerium needs on the callback.
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {});

  const userField = page.locator("input#ak-identifier-input");
  await userField.waitFor({ state: "visible", timeout: 30_000 });
  await userField.fill(username);

  const idSubmit = page.locator('button[type="submit"]:has-text("Log in")');
  await idSubmit.click();

  const passwordField = page.locator("input#ak-stage-password-input");
  await passwordField.waitFor({ state: "visible", timeout: 30_000 });
  await page.waitForTimeout(500);
  await passwordField.fill(password);

  const pwSubmit = page.locator('button[type="submit"]:has-text("Continue")');
  await pwSubmit.click();

  for (let attempt = 0; attempt < 120; attempt += 1) {
    const cur = page.url();
    const waitingOnAuth = /auth\.local\.humility\.local/.test(cur);
    const waitingOnAuthenticate = /authenticate\.local\.humility\.local\/(oauth2\/callback|\.pomerium\/sign_in)/.test(cur);
    if (!waitingOnAuth && !waitingOnAuthenticate) {
      await page.waitForLoadState("domcontentloaded", { timeout: 5_000 }).catch(() => {});
      return;
    }
    await page.waitForTimeout(1000);
  }
}

await mkdir(sessionDir, { recursive: true });
const statePath = join(sessionDir, `${flow}-sample-user.json`);
const hostLoopback = process.env.E2E_HOST_LOOPBACK || "127.0.0.1";
const launchArgs = [
  `--host-resolver-rules=MAP *.local.humility.local ${hostLoopback}`,
  "--ignore-certificate-errors",
];
const browser = await chromium.launch({ headless: true, args: launchArgs });
try {
  const contextOptions = {
    ignoreHTTPSErrors: true,
    baseURL: "https://web.local.humility.local",
  };
  if (existsSync(statePath)) {
    contextOptions.storageState = statePath;
  }
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();
  await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: 45_000 });
  await loginIfNeeded(page);
  // Re-navigate to the original target URL once auth cookies are set, so
  // Pomerium serves the protected resource directly instead of any
  // post-auth landing page.
  if (page.url() !== target.url) {
    await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: 45_000 }).catch(() => {});
  }
  await target.assert(page);
  await context.storageState({ path: statePath });
  await writeFile(join(sessionDir, `${flow}.last-url.txt`), page.url());
  await context.close();
} finally {
  await browser.close();
}
