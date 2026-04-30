import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page, type Request } from "@playwright/test";

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
    message: {
      endpoint: string;
      method: string;
      success_statuses: number[];
      visibility_values: string[];
    };
    transition: {
      endpoint: string;
      method: string;
      if_match_header: boolean;
      success_status: number;
      actions: string[];
    };
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
const messageEndpoint = contract.applications.message.endpoint.replace("{id}", applicationId);
const transitionEndpoint = contract.applications.transition.endpoint.replace(
  "{id}",
  applicationId,
);

function application(overrides: Partial<ApplicationRead> = {}): ApplicationRead {
  return {
    id: applicationId,
    applicant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    target_scope: { scope_kind: "chapter", scope_id: "chapter-1" },
    state: "claimed",
    owner_id: officerId,
    submitted_at: "2026-04-29T12:00:00Z",
    version: 3,
    form_snapshot: {
      fields: [{ id: "nickname", label: "Nickname" }],
    },
    responses: { nickname: "Ada" },
    queued_at: "2026-04-29T12:01:00Z",
    claimed_at: "2026-04-29T12:10:00Z",
    review_started_at: null,
    decided_at: null,
    withdrawn_at: null,
    created_at: "2026-04-29T12:00:00Z",
    updated_at: "2026-04-29T12:10:00Z",
    ...overrides,
  };
}

const initialTranscript: ApplicationTranscriptRead = {
  application_id: applicationId,
  entries: [
    {
      type: "state_change",
      occurred_at: "2026-04-29T12:01:00Z",
      change_type: "created",
      from_state: null,
      to_state: "queued",
      actor_kind: "user",
      actor_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      aggregate_seq: 1,
    },
  ],
};

function withMessage(bodyMarkdown: string, visibility: "applicant_visible" | "officer_only") {
  return {
    application_id: applicationId,
    entries: [
      ...initialTranscript.entries,
      {
        type: "message" as const,
        occurred_at: "2026-04-29T12:20:00Z",
        message_seq: 2,
        author_actor_kind: "user",
        author_actor_id: officerId,
        visibility,
        body_markdown: bodyMarkdown,
      },
    ],
  };
}

function withTransition(toState: string) {
  return {
    application_id: applicationId,
    entries: [
      ...initialTranscript.entries,
      {
        type: "state_change" as const,
        occurred_at: "2026-04-29T12:25:00Z",
        change_type: "application.transitioned",
        from_state: "claimed",
        to_state: toState,
        actor_kind: "user",
        actor_id: officerId,
        aggregate_seq: 2,
      },
    ],
  };
}

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
    detailResponses?: ApplicationRead[];
    transcriptResponses?: ApplicationTranscriptRead[];
  } = {},
) {
  let detailCalls = 0;
  let transcriptCalls = 0;
  const detailResponses = options.detailResponses ?? [application()];
  const transcriptResponses = options.transcriptResponses ?? [initialTranscript];

  await page.route(`**${detailEndpoint}`, async (route) => {
    const body = detailResponses[Math.min(detailCalls, detailResponses.length - 1)];
    detailCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
  await page.route(`**${transcriptEndpoint}`, async (route) => {
    const body = transcriptResponses[Math.min(transcriptCalls, transcriptResponses.length - 1)];
    transcriptCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });

  return {
    detailCalls: () => detailCalls,
    transcriptCalls: () => transcriptCalls,
  };
}

async function bootOfficerDetail(page: Page, options: Parameters<typeof mockDetailAndTranscript>[1] = {}) {
  await mockPrincipal(page, officerPrincipal());
  const calls = await mockDetailAndTranscript(page, options);
  await page.goto(detailPath);
  await expect(page.locator(`[data-application-id="${applicationId}"]`)).toBeVisible();
  return calls;
}

async function mockMessageAppend(
  page: Page,
  handler: (request: Request) => Promise<{ status: number; body: unknown }>,
) {
  const requests: Request[] = [];
  await page.route(`**${messageEndpoint}`, async (route) => {
    requests.push(route.request());
    const response = await handler(route.request());
    await route.fulfill({
      status: response.status,
      contentType: "application/json",
      body: JSON.stringify(response.body),
    });
  });
  return requests;
}

async function mockTransition(
  page: Page,
  handler: (request: Request) => Promise<{ status: number; body: unknown }>,
) {
  const requests: Request[] = [];
  await page.route(`**${transitionEndpoint}`, async (route) => {
    requests.push(route.request());
    const response = await handler(route.request());
    await route.fulfill({
      status: response.status,
      contentType: "application/json",
      body: JSON.stringify(response.body),
    });
  });
  return requests;
}

test("test_message_composer_disabled_for_empty_body", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=message_composer_validation;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  await bootOfficerDetail(page);

  const composer = page.getByTestId("application-message-composer");
  await expect(composer).toBeVisible();
  await expect(composer.getByRole("button", { name: /send/i })).toBeDisabled();
  await page.getByLabel("Append message").fill("   ");
  await expect(composer.getByRole("button", { name: /send/i })).toBeDisabled();
});

test("test_message_composer_appends_visible_message", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=message_payload_binding;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  const calls = await bootOfficerDetail(page, {
    transcriptResponses: [initialTranscript, withMessage("Visible bridge note", "applicant_visible")],
  });
  const requests = await mockMessageAppend(page, async (request) => ({
    status: contract.applications.message.success_statuses[0],
    body: {
      id: "22222222-2222-4222-8222-222222222222",
      application_id: applicationId,
      message_seq: 2,
      author_actor_kind: "user",
      author_actor_id: officerId,
      visibility: "applicant_visible",
      body_markdown: "Visible bridge note",
      client_message_id: JSON.parse(request.postData() ?? "{}").client_message_id,
      correlation_id: "33333333-3333-4333-8333-333333333333",
      causation_id: null,
      created_at: "2026-04-29T12:20:00Z",
    },
  }));

  await page.getByLabel("Append message").fill("Visible bridge note");
  await page.getByRole("radio", { name: /applicant|visible/i }).check();
  await page.getByRole("button", { name: /send/i }).click();

  await expect.poll(() => requests.length).toBe(1);
  const payload = JSON.parse(requests[0].postData() ?? "{}") as Record<string, unknown>;
  expect(payload.body_markdown).toBe("Visible bridge note");
  expect(payload.visibility).toBe("applicant_visible");
  expect(typeof payload.client_message_id).toBe("string");
  expect(payload.author_actor_kind).toBeUndefined();
  expect(payload.author_actor_id).toBeUndefined();
  await expect.poll(() => calls.transcriptCalls()).toBe(2);
  await expect(page.getByTestId("application-transcript")).toContainText("Visible bridge note");
});

test("test_message_composer_appends_officer_only_message", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=message_visibility;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  await bootOfficerDetail(page, {
    transcriptResponses: [initialTranscript, withMessage("Private note", "officer_only")],
  });
  const requests = await mockMessageAppend(page, async (request) => ({
    status: 201,
    body: {
      id: "22222222-2222-4222-8222-222222222222",
      application_id: applicationId,
      message_seq: 2,
      author_actor_kind: "user",
      author_actor_id: officerId,
      visibility: "officer_only",
      body_markdown: "Private note",
      client_message_id: JSON.parse(request.postData() ?? "{}").client_message_id,
      correlation_id: "33333333-3333-4333-8333-333333333333",
      causation_id: null,
      created_at: "2026-04-29T12:20:00Z",
    },
  }));

  await page.getByLabel("Append message").fill("Private note");
  await page.getByRole("radio", { name: /officer.*only/i }).check();
  await page.getByRole("button", { name: /send/i }).click();

  await expect.poll(() => requests.length).toBe(1);
  expect(JSON.parse(requests[0].postData() ?? "{}").visibility).toBe("officer_only");
  await expect(page.getByTestId("application-transcript")).toContainText("Private note");
  await expect(page.getByTestId("application-transcript")).toContainText("officer_only");
});

test("test_message_composer_clears_after_success", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=message_success_state;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  await bootOfficerDetail(page);
  await mockMessageAppend(page, async (request) => ({
    status: 200,
    body: {
      id: "22222222-2222-4222-8222-222222222222",
      application_id: applicationId,
      message_seq: 2,
      author_actor_kind: "user",
      author_actor_id: officerId,
      visibility: "applicant_visible",
      body_markdown: "Clear me",
      client_message_id: JSON.parse(request.postData() ?? "{}").client_message_id,
      correlation_id: "33333333-3333-4333-8333-333333333333",
      causation_id: null,
      created_at: "2026-04-29T12:20:00Z",
    },
  }));

  await page.getByLabel("Append message").fill("Clear me");
  await page.getByRole("button", { name: /send/i }).click();

  await expect(page.getByLabel("Append message")).toHaveValue("");
});

test("test_message_composer_rotates_idempotency_token", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=message_idempotency_token_rotation;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  await bootOfficerDetail(page);
  const requests = await mockMessageAppend(page, async (request) => ({
    status: 201,
    body: {
      id: `22222222-2222-4222-8222-22222222222${requests.length}`,
      application_id: applicationId,
      message_seq: requests.length + 1,
      author_actor_kind: "user",
      author_actor_id: officerId,
      visibility: "applicant_visible",
      body_markdown: JSON.parse(request.postData() ?? "{}").body_markdown,
      client_message_id: JSON.parse(request.postData() ?? "{}").client_message_id,
      correlation_id: "33333333-3333-4333-8333-333333333333",
      causation_id: null,
      created_at: "2026-04-29T12:20:00Z",
    },
  }));

  await page.getByLabel("Append message").fill("First token");
  await page.getByRole("button", { name: /send/i }).click();
  await page.getByLabel("Append message").fill("Second token");
  await page.getByRole("button", { name: /send/i }).click();

  await expect.poll(() => requests.length).toBe(2);
  const first = JSON.parse(requests[0].postData() ?? "{}").client_message_id;
  const second = JSON.parse(requests[1].postData() ?? "{}").client_message_id;
  expect(first).not.toBe(second);
});

test("test_message_composer_handles_403", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=message_forbidden_notice;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  await bootOfficerDetail(page);
  await mockMessageAppend(page, async () => ({
    status: 403,
    body: { code: "application_message_forbidden" },
  }));

  await page.getByLabel("Append message").fill("Forbidden note");
  await page.getByRole("button", { name: /send/i }).click();

  await expect(page.getByText(/forbidden|permission|not allowed/i)).toBeVisible();
});

test("test_transition_buttons_match_state", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=state_machine_visibility;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  const cases: Array<{ state: string; visible: string[]; hidden: string[] }> = [
    { state: "submitted", visible: ["route"], hidden: ["claim", "review", "approve"] },
    { state: "queued", visible: ["route"], hidden: ["claim", "review", "approve"] },
    { state: "claimed", visible: ["review"], hidden: ["claim", "approve", "deny"] },
    {
      state: "in_review",
      visible: ["request_interview", "waitlist", "approve", "deny"],
      hidden: ["claim", "route"],
    },
    { state: "approved", visible: [], hidden: ["claim", "review", "approve", "deny"] },
  ];

  for (const stateCase of cases) {
    await mockPrincipal(page, officerPrincipal());
    await mockDetailAndTranscript(page, {
      detailResponses: [application({ state: stateCase.state, version: 3 })],
    });
    await page.goto(detailPath);
    for (const action of stateCase.visible) {
      await expect(page.getByTestId(`application-transition-action-${action}`)).toBeVisible();
    }
    for (const action of stateCase.hidden) {
      await expect(page.getByTestId(`application-transition-action-${action}`)).toHaveCount(0);
    }
    await page.unrouteAll({ behavior: "ignoreErrors" });
  }
});

test("test_transition_review_with_notes", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=transition_required_fields;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  const calls = await bootOfficerDetail(page, {
    detailResponses: [application(), application({ state: "in_review", version: 4 })],
    transcriptResponses: [initialTranscript, withTransition("in_review")],
  });
  const requests = await mockTransition(page, async () => ({
    status: 200,
    body: application({ state: "in_review", version: 4 }),
  }));

  await page.getByTestId("application-transition-action-review").click();
  await page.getByRole("textbox", { name: /notes/i }).fill("Ready for review");
  await page.getByRole("button", { name: /confirm/i }).click();

  await expect.poll(() => requests.length).toBe(1);
  const payload = JSON.parse(requests[0].postData() ?? "{}") as Record<string, unknown>;
  expect(payload).toEqual({ action: "review", notes: "Ready for review" });
  expect(requests[0].headers()["if-match"]).toBe('"3"');
  await expect.poll(() => calls.detailCalls()).toBe(2);
  await expect.poll(() => calls.transcriptCalls()).toBe(2);
});

test("test_transition_approve_with_decision_reason", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=transition_decision_reason;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  await bootOfficerDetail(page, {
    detailResponses: [application({ state: "in_review", version: 4 })],
  });
  const requests = await mockTransition(page, async () => ({
    status: 200,
    body: application({ state: "approved", version: 5 }),
  }));

  await page.getByTestId("application-transition-action-approve").click();
  await page.getByRole("textbox", { name: /decision reason/i }).fill("Accepted");
  await page.getByRole("button", { name: /confirm/i }).click();

  await expect.poll(() => requests.length).toBe(1);
  expect(JSON.parse(requests[0].postData() ?? "{}")).toEqual({
    action: "approve",
    decision_reason: "Accepted",
  });
  expect(requests[0].headers()["if-match"]).toBe('"4"');
});

test("test_transition_deny_with_decision_reason", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=transition_decision_reason;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  await bootOfficerDetail(page, {
    detailResponses: [application({ state: "in_review", version: 4 })],
  });
  const requests = await mockTransition(page, async () => ({
    status: 200,
    body: application({ state: "denied", version: 5 }),
  }));

  await page.getByTestId("application-transition-action-deny").click();
  await page.getByRole("textbox", { name: /decision reason/i }).fill("Not a fit");
  await page.getByRole("button", { name: /confirm/i }).click();

  await expect.poll(() => requests.length).toBe(1);
  expect(JSON.parse(requests[0].postData() ?? "{}")).toEqual({
    action: "deny",
    decision_reason: "Not a fit",
  });
});

test("test_transition_stale_version_refetches", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=transition_stale_recovery;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  const calls = await bootOfficerDetail(page, {
    detailResponses: [application(), application({ version: 4 })],
  });
  await mockTransition(page, async () => ({
    status: 412,
    body: { code: "stale_application_version" },
  }));

  await page.getByTestId("application-transition-action-review").click();
  await page.getByRole("textbox", { name: /notes/i }).fill("Stale review");
  await page.getByRole("button", { name: /confirm/i }).click();

  await expect(page.getByText(/stale|version|refresh/i)).toBeVisible();
  await expect.poll(() => calls.detailCalls()).toBe(2);
  await expect.poll(() => calls.transcriptCalls()).toBe(2);
});

test("test_transition_409_shows_notice_and_refetches", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=transition_conflict_recovery;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  const calls = await bootOfficerDetail(page, {
    detailResponses: [application({ state: "in_review" }), application({ state: "in_review" })],
  });
  await mockTransition(page, async () => ({
    status: 409,
    body: { code: "invalid_application_transition" },
  }));

  await page.getByTestId("application-transition-action-approve").click();
  await page.getByRole("textbox", { name: /decision reason/i }).fill("Accepted");
  await page.getByRole("button", { name: /confirm/i }).click();

  await expect(page.getByText(/conflict|transition|invalid/i)).toBeVisible();
  await expect.poll(() => calls.detailCalls()).toBe(2);
  await expect.poll(() => calls.transcriptCalls()).toBe(2);
});

test("test_transition_403_disables_button", async ({ page }) => {
  // Risk annotation: group=TG-2;
  //   named_risk=transition_forbidden_disables_action;
  //   level=component;
  //   source=.tmp/init-133B-iii/phase6/step6a-contract.md#TG-2
  await bootOfficerDetail(page);
  await mockTransition(page, async () => ({
    status: 403,
    body: { code: "authority_decision_denied" },
  }));

  await page.getByTestId("application-transition-action-review").click();
  await page.getByRole("textbox", { name: /notes/i }).fill("Forbidden review");
  await page.getByRole("button", { name: /confirm/i }).click();

  await expect(page.getByText(/forbidden|permission|not allowed/i)).toBeVisible();
  await expect(page.getByTestId("application-transition-action-review")).toBeDisabled();
});
