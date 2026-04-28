import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chromium } from "playwright";

const flow = process.env.E2E_BROWSER_FLOW;
const sessionDir = process.env.E2E_SESSION_DIR;
const username = process.env.AUTHENTIK_USERNAME;
const password = process.env.AUTHENTIK_PASSWORD;

if (!flow || !sessionDir || !username || !password) {
  throw new Error("E2E_BROWSER_FLOW, E2E_SESSION_DIR, AUTHENTIK_USERNAME, and AUTHENTIK_PASSWORD are required");
}

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
      await page.goto("https://web.local.humility.local/");
      await page.getByRole("heading", { name: "Dark Nemesis application" }).waitFor({ timeout: 30_000 });
      await page.getByLabel("What is your in-game name?").fill("E2E Applicant");
      await page.getByRole("button", { name: "Preview submission" }).click();
      await page.getByText("E2E Applicant").waitFor({ timeout: 10_000 });
    },
  },
};

const target = targets[flow];
if (!target) {
  throw new Error(`unknown browser flow: ${flow}`);
}

async function firstVisible(locator) {
  const count = await locator.count();
  for (let index = 0; index < count; index += 1) {
    const item = locator.nth(index);
    if (await item.isVisible().catch(() => false)) {
      return item;
    }
  }
  return null;
}

async function loginIfNeeded(page) {
  await page.waitForLoadState("domcontentloaded", { timeout: 30_000 }).catch(() => {});
  if (!/auth\.local\.humility\.local|authenticate\.local\.humility\.local/.test(page.url())) {
    return;
  }

  const userInput = await firstVisible(
    page.locator('input[type="email"], input[name="uid"], input[name="username"], input[name="identification"], input[autocomplete="username"]'),
  );
  if (!userInput) {
    throw new Error(`could not find Authentik username field at ${page.url()}`);
  }
  await userInput.fill(username);

  const passwordInput = await firstVisible(
    page.locator('input[type="password"], input[name="password"], input[autocomplete="current-password"]'),
  );
  if (!passwordInput) {
    throw new Error(`could not find Authentik password field at ${page.url()}`);
  }
  await passwordInput.fill(password);

  const submit = await firstVisible(page.locator('button[type="submit"], input[type="submit"]'));
  if (!submit) {
    throw new Error(`could not find Authentik submit button at ${page.url()}`);
  }
  await Promise.all([
    page.waitForLoadState("domcontentloaded", { timeout: 30_000 }).catch(() => {}),
    submit.click(),
  ]);
}

await mkdir(sessionDir, { recursive: true });
const statePath = join(sessionDir, `${flow}-sample-user.json`);
const hostLoopback = process.env.E2E_HOST_LOOPBACK || "127.0.0.1";
const hostHttpsPort = process.env.E2E_HOST_HTTPS_PORT || "8443";
const launchArgs = [
  `--host-resolver-rules=MAP *.local.humility.local:443 ${hostLoopback}:${hostHttpsPort}`,
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
  await target.assert(page);
  await context.storageState({ path: statePath });
  await writeFile(join(sessionDir, `${flow}.last-url.txt`), page.url());
  await context.close();
} finally {
  await browser.close();
}
