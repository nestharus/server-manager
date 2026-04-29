import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

type ApplicationRead = {
  id: string;
  applicant_id: string;
  target_scope: { scope_kind: string; scope_id: string | null };
  state: string;
  owner_id: string | null;
  submitted_at: string;
  version: number;
  form_snapshot: Readonly<Record<string, unknown>>;
  responses: Readonly<Record<string, unknown>>;
  queued_at: string | null;
  claimed_at: string | null;
  review_started_at: string | null;
  decided_at: string | null;
  withdrawn_at: string | null;
  created_at: string;
  updated_at: string;
};

type TranscriptEntry =
  | {
      type: "state_change";
      occurred_at: string;
      change_type: string;
      from_state: string | null;
      to_state: string | null;
      actor_kind: string;
      actor_id: string;
      aggregate_seq: number;
    }
  | {
      type: "message";
      occurred_at: string;
      message_seq: number;
      author_actor_kind: string;
      author_actor_id: string;
      visibility: "applicant_visible" | "officer_only";
      body_markdown: string;
    };

type ApplicationTranscriptRead = {
  application_id: string;
  entries: TranscriptEntry[];
};

type Contract = {
  routes: {
    officer_detail: { path: string; requires_auth: boolean };
  };
  auth: {
    probe_endpoint: string;
    unauthenticated_api_status: number;
    identity: {
      subject: string;
      email: string;
      groups: string[];
      discord_user_id: string | null;
    };
  };
  applications: {
    detail: { endpoint: string };
    transcript: { endpoint: string };
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
const applicationId = "11111111-1111-4111-8111-111111111111";
const officerId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

const detailPath = contract.routes.officer_detail.path.replace("{id}", applicationId);
const detailEndpoint = contract.applications.detail.endpoint.replace("{id}", applicationId);
const transcriptEndpoint = contract.applications.transcript.endpoint.replace(
  "{id}",
  applicationId,
);

const applicationDetail: ApplicationRead = {
  id: applicationId,
  applicant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  target_scope: { scope_kind: "chapter", scope_id: "chapter-1" },
  state: "claimed",
  owner_id: officerId,
  submitted_at: "2026-04-29T12:00:00Z",
  version: 3,
  form_snapshot: {
    fields: [
      { id: "nickname", label: "Nickname" },
      { id: "class", label: "Class" },
    ],
  },
  responses: {
    nickname: "Ada",
    class: "mage",
  },
  queued_at: "2026-04-29T12:01:00Z",
  claimed_at: "2026-04-29T12:10:00Z",
  review_started_at: null,
  decided_at: null,
  withdrawn_at: null,
  created_at: "2026-04-29T12:00:00Z",
  updated_at: "2026-04-29T12:10:00Z",
};

const transcript: ApplicationTranscriptRead = {
  application_id: applicationId,
  entries: [
    {
      type: "state_change",
      occurred_at: "2026-04-29T12:01:00Z",
      change_type: "created",
      from_state: null,
      to_state: "queued",
      actor_kind: "user",
      actor_id: applicationDetail.applicant_id,
      aggregate_seq: 1,
    },
    {
      type: "message",
      occurred_at: "2026-04-29T12:05:00Z",
      message_seq: 1,
      author_actor_kind: "user",
      author_actor_id: officerId,
      visibility: "officer_only",
      body_markdown: "Officer-only transcript note",
    },
  ],
};

function officerPrincipal(overrides: Partial<Contract["auth"]["identity"]> = {}) {
  return {
    ...contract.auth.identity,
    provider: "pomerium",
    display_name: "Humility Officer",
    ...overrides,
  };
}

async function mockPrincipal(page: Page, body: unknown, status = 200) {
  await page.route(`**${contract.auth.probe_endpoint}`, async (route) => {
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

async function mockDetailAndTranscript(
  page: Page,
  options: {
    detail?: { status: number; body: unknown };
    transcript?: { status: number; body: unknown };
    mutatingRequests?: string[];
  } = {},
) {
  let detailCalls = 0;
  let transcriptCalls = 0;
  const detailResponse = options.detail ?? { status: 200, body: applicationDetail };
  const transcriptResponse = options.transcript ?? { status: 200, body: transcript };

  await page.route(`**${detailEndpoint}`, async (route) => {
    const method = route.request().method();
    if (method !== "GET") options.mutatingRequests?.push(method);
    detailCalls += 1;
    await route.fulfill({
      status: detailResponse.status,
      contentType: "application/json",
      body: JSON.stringify(detailResponse.body),
    });
  });
  await page.route(`**${transcriptEndpoint}`, async (route) => {
    const method = route.request().method();
    if (method !== "GET") options.mutatingRequests?.push(method);
    transcriptCalls += 1;
    await route.fulfill({
      status: transcriptResponse.status,
      contentType: "application/json",
      body: JSON.stringify(transcriptResponse.body),
    });
  });

  return {
    detailCalls: () => detailCalls,
    transcriptCalls: () => transcriptCalls,
  };
}

test("test_officer_detail_anonymous", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=anonymous_detail_blocked;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  await mockPrincipal(page, { code: "identity_missing" }, contract.auth.unauthenticated_api_status);
  const calls = await mockDetailAndTranscript(page);

  await page.goto(detailPath);

  await expect(page.getByText(/auth|sign in|required/i)).toBeVisible();
  expect(calls.detailCalls()).toBe(0);
  expect(calls.transcriptCalls()).toBe(0);
});

test("test_officer_detail_non_officer", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=non_officer_blocked;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  await mockPrincipal(page, officerPrincipal({ groups: ["applicants"] }));
  const calls = await mockDetailAndTranscript(page);

  await page.goto(detailPath);

  await expect(page.getByText(/officer|forbidden|access/i)).toBeVisible();
  expect(calls.detailCalls()).toBe(0);
  expect(calls.transcriptCalls()).toBe(0);
});

test("test_officer_detail_no_discord_claim", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=missing_discord_claim;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  await mockPrincipal(page, officerPrincipal({ discord_user_id: null }));
  const calls = await mockDetailAndTranscript(page);

  await page.goto(detailPath);

  await expect(page.getByText(/discord identity|required|incomplete/i)).toBeVisible();
  expect(calls.detailCalls()).toBe(0);
  expect(calls.transcriptCalls()).toBe(0);
});

test("test_officer_detail_renders_metadata", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=detail_contract_shape;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  await mockPrincipal(page, officerPrincipal());
  await mockDetailAndTranscript(page);

  await page.goto(detailPath);

  const root = page.locator(`[data-application-id="${applicationId}"]`);
  await expect(root).toBeVisible();
  await expect(page.getByTestId("application-detail-state")).toContainText("claimed");
  await expect(page.getByTestId("application-detail-version")).toContainText("3");
  await expect(root).toContainText(officerId.slice(0, 8));
  await expect(root).toContainText(applicationDetail.applicant_id.slice(0, 8));
  await expect(root).toContainText("chapter");
  await expect(root).toContainText("chapter-1");
  await expect(root).toContainText("2026");
});

test("test_officer_detail_renders_responses", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=response_rendering;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  await mockPrincipal(page, officerPrincipal());
  await mockDetailAndTranscript(page);

  await page.goto(detailPath);

  await expect(page.locator(`[data-application-id="${applicationId}"]`)).toContainText("nickname");
  await expect(page.locator(`[data-application-id="${applicationId}"]`)).toContainText("Ada");
  await expect(page.locator(`[data-application-id="${applicationId}"]`)).toContainText("class");
  await expect(page.locator(`[data-application-id="${applicationId}"]`)).toContainText("mage");
});

test("test_officer_detail_renders_transcript", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=transcript_discriminator_rendering;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  await mockPrincipal(page, officerPrincipal());
  await mockDetailAndTranscript(page);

  await page.goto(detailPath);

  const transcriptPanel = page.getByTestId("application-transcript");
  await expect(transcriptPanel).toContainText("queued");
  await expect(transcriptPanel).toContainText("user");
  await expect(transcriptPanel).toContainText(applicationDetail.applicant_id.slice(0, 8));
  await expect(transcriptPanel).toContainText("Officer-only transcript note");
  await expect(transcriptPanel).toContainText("officer_only");
  await expect(transcriptPanel).toContainText(officerId.slice(0, 8));
});

test("test_officer_detail_handles_404", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=detail_not_found_panel;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  await mockPrincipal(page, officerPrincipal());
  await mockDetailAndTranscript(page, {
    detail: { status: 404, body: { code: "application_not_found" } },
  });

  await page.goto(detailPath);

  await expect(page.getByText(/not found|missing application/i)).toBeVisible();
});

test("test_officer_detail_handles_403", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=transcript_forbidden_panel;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  await mockPrincipal(page, officerPrincipal());
  await mockDetailAndTranscript(page, {
    transcript: { status: 403, body: { code: "application_transcript_forbidden" } },
  });

  await page.goto(detailPath);

  await expect(page.getByText(/forbidden|not allowed|permission/i)).toBeVisible();
});

test("test_officer_detail_no_action_buttons", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=read_only_surface_regression;
  //   level=component;
  //   source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-2
  const mutatingRequests: string[] = [];
  await mockPrincipal(page, officerPrincipal());
  await mockDetailAndTranscript(page, { mutatingRequests });

  await page.goto(detailPath);

  await expect(page.locator(`[data-application-id="${applicationId}"]`)).toBeVisible();
  await expect(page.getByRole("button", { name: /claim/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /review|approve|deny|waitlist/i })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: /message|comment|reply/i })).toHaveCount(0);
  expect(mutatingRequests).toEqual([]);
});
