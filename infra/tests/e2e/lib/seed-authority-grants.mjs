import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const kubeconfig = process.env.KUBECONFIG_PATH || process.env.KUBECONFIG;
const moduleDir = dirname(fileURLToPath(import.meta.url));
const webContract = JSON.parse(
  readFileSync(resolve(moduleDir, "../../fixtures/web-ui/contract.json"), "utf8"),
);
const discordUserId = process.env.E2E_OFFICER_DISCORD_USER_ID || webContract.auth.identity.discord_user_id;
const scopeKind = process.env.E2E_APPLICATION_SCOPE_KIND || "global";
const scopeId = process.env.E2E_APPLICATION_SCOPE_ID || null;

if (!kubeconfig) {
  throw new Error("KUBECONFIG_PATH or KUBECONFIG is required");
}

function kubectl(args, options = {}) {
  return execFileSync("kubectl", ["--kubeconfig", kubeconfig, ...args], {
    encoding: "utf8",
    ...options,
  }).trim();
}

function sqlLiteral(value) {
  if (value === null) return "NULL";
  // sqlLiteral uses E'' so backslashes round-trip even if standard_conforming_strings differs.
  const escaped = String(value)
    .replaceAll("\0", "")
    .replaceAll("\\", "\\\\")
    .replaceAll("'", "''");
  return `E'${escaped}'`;
}

const primaryPod = kubectl([
  "-n",
  "server-manager",
  "get",
  "pods",
  "-l",
  "cnpg.io/cluster=server-manager-postgres,role=primary",
  "-o",
  "jsonpath={.items[0].metadata.name}",
]);
const postgresUrl = Buffer.from(
  kubectl([
    "-n",
    "server-manager",
    "get",
    "secret",
    "server-manager-postgres-url",
    "-o",
    "jsonpath={.data.url}",
  ]),
  "base64",
).toString("utf8");

const memberId = randomUUID();
const grantId = randomUUID();
const permissions = JSON.stringify(["application.claim", "application.review"]);
const sql = `
WITH resolved_member AS (
  INSERT INTO members (id, discord_user_id, joined_at, status, kind)
  VALUES (${sqlLiteral(memberId)}::uuid, ${sqlLiteral(discordUserId)}, now(), 'active', 'discord')
  ON CONFLICT (discord_user_id) DO UPDATE
    SET discord_user_id = EXCLUDED.discord_user_id
  RETURNING id, kind
),
checked_member AS (
  SELECT id, kind FROM resolved_member
  UNION ALL
  SELECT id, kind FROM members WHERE discord_user_id = ${sqlLiteral(discordUserId)}
  LIMIT 1
),
inserted_grant AS (
  INSERT INTO authority_grants (
    id,
    grantee_id,
    scope_kind,
    scope_id,
    permissions,
    expires_at,
    revoked_at,
    revoked_by,
    revocation_reason,
    predecessor_grant_id
  )
  SELECT
    ${sqlLiteral(grantId)}::uuid,
    cm.id::text,
    ${sqlLiteral(scopeKind)},
    ${sqlLiteral(scopeId)},
    ${sqlLiteral(permissions)}::jsonb,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  FROM checked_member AS cm
  WHERE cm.kind = 'discord'
    AND NOT EXISTS (
      SELECT 1
      FROM authority_grants existing
      WHERE existing.grantee_id = cm.id::text
        AND existing.scope_kind = ${sqlLiteral(scopeKind)}
        AND existing.scope_id IS NOT DISTINCT FROM ${sqlLiteral(scopeId)}
        AND existing.permissions = ${sqlLiteral(permissions)}::jsonb
        AND existing.revoked_at IS NULL
    )
  RETURNING grantee_id
)
SELECT id::text
FROM checked_member
WHERE kind = 'discord';
`;

const output = kubectl([
  "-n",
  "server-manager",
  "exec",
  primaryPod,
  "-c",
  "postgres",
  "--",
  "psql",
  postgresUrl,
  "-v",
  "ON_ERROR_STOP=1",
  "-At",
  "-c",
  sql,
]);

if (!output) {
  throw new Error(
    `failed to resolve Discord officer member: discord_user_id=${discordUserId}, scope_kind=${scopeKind}, scope_id=${scopeId}, output=empty`,
  );
}

const resolvedMemberId = output
  .split("\n")
  .map((line) => line.trim())
  .filter(Boolean)
  .at(-1);

if (!resolvedMemberId) {
  throw new Error(
    `failed to parse Discord officer member: discord_user_id=${discordUserId}, scope_kind=${scopeKind}, scope_id=${scopeId}, output=${JSON.stringify(output)}`,
  );
}

console.log(
  JSON.stringify({
    discord_user_id: discordUserId,
    member_id: resolvedMemberId,
    scope_kind: scopeKind,
    scope_id: scopeId,
    permissions: ["application.claim", "application.review"],
  }),
);
