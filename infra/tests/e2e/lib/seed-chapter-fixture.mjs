import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const moduleDir = dirname(fileURLToPath(import.meta.url));
const webContract = JSON.parse(
  readFileSync(resolve(moduleDir, "../../fixtures/web-ui/contract.json"), "utf8"),
);
const expectedChapterId = "chapter-alpha";
const expectedChapterName = "Alpha Chapter";
const templateKey = "e2e-template";
const templateId = deterministicUuid(templateKey);
const templateName = "E2E Chapter Template";
const kubeconfig = process.env.KUBECONFIG_PATH || process.env.KUBECONFIG;
const directPostgresUrl = process.env.SUPABASE_DB_URL || process.env.DATABASE_URL || null;

assertContractChapterFixture(webContract);

function deterministicUuid(seed) {
  const bytes = Buffer.from(createHash("sha256").update(seed).digest().subarray(0, 16));
  bytes[6] = (bytes[6] & 0x0f) | 0x50;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`web UI contract chapter fixture drift: ${label} expected ${expected}, got ${actual}`);
  }
}

function assertContractChapterFixture(contract) {
  const chapter = contract.form?.chapters;
  const responseChapter = chapter?.response?.chapters?.[0];
  const chapterField = contract.form?.fields?.find((field) => field.type === "chapter_select");
  const submitScope = contract.form?.submit?.payload_fields?.find(
    (field) => field.name === "scope.scope_id",
  );

  assertEqual(chapter?.selected_id, expectedChapterId, "form.chapters.selected_id");
  assertEqual(chapter?.selected_name, expectedChapterName, "form.chapters.selected_name");
  assertEqual(responseChapter?.id, expectedChapterId, "form.chapters.response.chapters[0].id");
  assertEqual(responseChapter?.name, expectedChapterName, "form.chapters.response.chapters[0].name");
  assertEqual(chapterField?.value, expectedChapterId, "chapter_select field value");
  assertEqual(submitScope?.value, expectedChapterId, "submit scope.scope_id");
}

function kubectl(args, options = {}) {
  if (!kubeconfig) {
    throw new Error("KUBECONFIG_PATH or KUBECONFIG is required when SUPABASE_DB_URL or DATABASE_URL is not set");
  }
  return execFileSync("kubectl", ["--kubeconfig", kubeconfig, ...args], {
    encoding: "utf8",
    ...options,
  }).trim();
}

function sqlLiteral(value) {
  if (value === null) return "NULL";
  const escaped = String(value)
    .replaceAll("\0", "")
    .replaceAll("\\", "\\\\")
    .replaceAll("'", "''");
  return `E'${escaped}'`;
}

const emptyArrayJson = JSON.stringify([]);
const emptyObjectJson = JSON.stringify({});
const templateSnapshot = JSON.stringify({
  template_id: templateId,
  template_family_id: templateId,
  template_version: 1,
  schema_version: 1,
  channel_structure: [],
  role_structure: [],
  default_permission_intents: [],
});

const sql = `
WITH seed AS (
  SELECT
    ${sqlLiteral(expectedChapterId)}::text AS chapter_id,
    ${sqlLiteral(expectedChapterName)}::text AS chapter_name,
    ${sqlLiteral(templateId)}::uuid AS template_id,
    ${sqlLiteral(templateName)}::text AS template_name,
    ${sqlLiteral(emptyArrayJson)}::jsonb AS empty_array,
    ${sqlLiteral(emptyObjectJson)}::jsonb AS empty_object,
    ${sqlLiteral(templateSnapshot)}::jsonb AS template_snapshot
),
existing AS (
  SELECT
    EXISTS (
      SELECT 1
      FROM chapter_templates t, seed s
      WHERE t.id = s.template_id
    ) AS template_exists,
    EXISTS (
      SELECT 1
      FROM chapters c, seed s
      WHERE c.id = s.chapter_id
    ) AS chapter_exists,
    EXISTS (
      SELECT 1
      FROM aggregate_heads h, seed s
      WHERE h.aggregate_type = 'chapter'
        AND h.aggregate_id = s.chapter_id
    ) AS head_exists
),
conflicts AS (
  SELECT 'fixture template exists with incompatible shape' AS reason
  FROM seed s
  WHERE EXISTS (
    SELECT 1
    FROM chapter_templates t
    WHERE t.id = s.template_id
      AND (
        t.template_family_id IS DISTINCT FROM s.template_id
        OR t.version IS DISTINCT FROM 1
        OR t.name IS DISTINCT FROM s.template_name
        OR t.schema_version IS DISTINCT FROM 1
        OR t.channel_structure IS DISTINCT FROM s.empty_array
        OR t.role_structure IS DISTINCT FROM s.empty_array
        OR t.default_permission_intents IS DISTINCT FROM s.empty_array
      )
  )
  UNION ALL
  SELECT 'fixture template family/version already belongs to a different template' AS reason
  FROM seed s
  WHERE EXISTS (
    SELECT 1
    FROM chapter_templates t
    WHERE t.template_family_id = s.template_id
      AND t.version = 1
      AND t.id <> s.template_id
  )
  UNION ALL
  SELECT 'chapter fixture name already belongs to a different chapter' AS reason
  FROM seed s
  WHERE EXISTS (
    SELECT 1
    FROM chapters c
    WHERE LOWER(c.name) = LOWER(s.chapter_name)
      AND c.id <> s.chapter_id
  )
  UNION ALL
  SELECT 'fixture chapter exists with incompatible name, state, or template_id' AS reason
  FROM seed s
  WHERE EXISTS (
    SELECT 1
    FROM chapters c
    WHERE c.id = s.chapter_id
      AND (
        c.name IS DISTINCT FROM s.chapter_name
        OR c.state IS DISTINCT FROM 'active'
        OR c.template_id IS DISTINCT FROM s.template_id
      )
  )
  UNION ALL
  SELECT 'fixture aggregate head exists with incompatible sequence or latest_change_id' AS reason
  FROM seed s
  WHERE EXISTS (
    SELECT 1
    FROM aggregate_heads h
    WHERE h.aggregate_type = 'chapter'
      AND h.aggregate_id = s.chapter_id
      AND (
        h.current_seq IS DISTINCT FROM 1
        OR h.latest_change_id IS NOT NULL
      )
  )
),
guard AS (
  SELECT COUNT(*) AS conflict_count, STRING_AGG(reason, '; ' ORDER BY reason) AS conflict_reason
  FROM conflicts
),
inserted_template AS (
  INSERT INTO chapter_templates (
    id,
    template_family_id,
    version,
    name,
    schema_version,
    channel_structure,
    role_structure,
    default_permission_intents
  )
  SELECT
    s.template_id,
    s.template_id,
    1,
    s.template_name,
    1,
    s.empty_array,
    s.empty_array,
    s.empty_array
  FROM seed s, guard g
  WHERE g.conflict_count = 0
    AND NOT EXISTS (
      SELECT 1
      FROM chapter_templates t
      WHERE t.id = s.template_id
    )
  RETURNING id
),
inserted_chapter AS (
  INSERT INTO chapters (
    id,
    name,
    template_id,
    template_snapshot,
    configuration,
    state,
    discord_resources
  )
  SELECT
    s.chapter_id,
    s.chapter_name,
    s.template_id,
    s.template_snapshot,
    s.empty_object,
    'active',
    s.empty_object
  FROM seed s, guard g
  WHERE g.conflict_count = 0
    AND NOT EXISTS (
      SELECT 1
      FROM chapters c
      WHERE c.id = s.chapter_id
    )
  RETURNING id
),
inserted_head AS (
  INSERT INTO aggregate_heads (
    aggregate_type,
    aggregate_id,
    current_seq,
    latest_change_id
  )
  SELECT
    'chapter',
    s.chapter_id,
    1,
    NULL
  FROM seed s, guard g
  WHERE g.conflict_count = 0
    AND NOT EXISTS (
      SELECT 1
      FROM aggregate_heads h
      WHERE h.aggregate_type = 'chapter'
        AND h.aggregate_id = s.chapter_id
    )
  RETURNING aggregate_id
),
counts AS (
  SELECT
    (SELECT COUNT(*) FROM inserted_template) AS templates_inserted,
    (SELECT COUNT(*) FROM inserted_chapter) AS chapters_inserted,
    (SELECT COUNT(*) FROM inserted_head) AS heads_inserted
)
SELECT json_build_object(
  'outcome',
  CASE
    WHEN g.conflict_count > 0 THEN 'aborted'
    WHEN NOT e.template_exists AND NOT e.chapter_exists AND NOT e.head_exists THEN 'inserted'
    WHEN (c.templates_inserted + c.chapters_inserted + c.heads_inserted) > 0 THEN 'partial'
    ELSE 'noop'
  END,
  'chapter_id', s.chapter_id,
  'chapter_name', s.chapter_name,
  'template_id', s.template_id::text,
  'template_name', s.template_name,
  'error', g.conflict_reason
)::text
FROM seed s, existing e, guard g, counts c;
`;

function executeSqlWithKubectl(sqlText) {
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

  return kubectl([
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
    sqlText,
  ]);
}

function executeSqlDirect(sqlText, postgresUrl) {
  return execFileSync("psql", [postgresUrl, "-v", "ON_ERROR_STOP=1", "-At", "-c", sqlText], {
    encoding: "utf8",
  }).trim();
}

const output = directPostgresUrl ? executeSqlDirect(sql, directPostgresUrl) : executeSqlWithKubectl(sql);
const result = JSON.parse(
  output
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .at(-1),
);

if (result.outcome === "noop") {
  console.error("chapter fixture already present");
} else if (result.outcome === "aborted") {
  console.error(`chapter fixture aborted: ${result.error}`);
}

console.log(JSON.stringify(result));

if (result.outcome === "aborted") {
  process.exitCode = 1;
}
