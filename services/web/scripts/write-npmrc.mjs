import { writeFileSync } from "node:fs";

const lines = ["legacy-peer-deps=true"];

if (process.env.NPM_TOKEN) {
  lines.push(`//registry.npmjs.org/:_authToken=${process.env.NPM_TOKEN}`);
}

if (process.env.FA_NPM_TOKEN) {
  lines.push("@fortawesome:registry=https://npm.fontawesome.com/");
  lines.push(`//npm.fontawesome.com/:_authToken=${process.env.FA_NPM_TOKEN}`);
}

if (process.env.WA_NPM_TOKEN) {
  lines.push("@awesome.me:registry=https://npm.fontawesome.com/");
  lines.push(`//npm.fontawesome.com/:_authToken=${process.env.WA_NPM_TOKEN}`);
}

writeFileSync(new URL("../.npmrc", import.meta.url), `${lines.join("\n")}\n`, {
  mode: 0o600,
});
