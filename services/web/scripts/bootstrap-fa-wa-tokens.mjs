import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright";

const credsPath = join(homedir(), ".config/server-manager/fa-wa-creds.env");

function readEnvFile(path) {
  if (!existsSync(path)) {
    throw new Error(`missing credential file: ${path}`);
  }
  return Object.fromEntries(
    readFileSync(path, "utf8")
      .split(/\r?\n/)
      .filter((line) => line.trim() && !line.trim().startsWith("#"))
      .map((line) => {
        const index = line.indexOf("=");
        return [line.slice(0, index), line.slice(index + 1)];
      }),
  );
}

async function main() {
  const creds = readEnvFile(credsPath);
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto("https://fontawesome.com/account/general", { waitUntil: "domcontentloaded" });
    console.log(
      JSON.stringify({
        status: "manual-dashboard-bootstrap-required",
        has_fa_username: Boolean(creds.FA_USERNAME),
        has_wa_username: Boolean(creds.WA_USERNAME),
      }),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
