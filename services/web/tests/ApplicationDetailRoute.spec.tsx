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
    officer_detail: { path: string };
  };
  auth: {
    probe_endpoint: string;
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
      success_statuses: number[];
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
const transcriptEndpoint = contract.applications.transcript.endpoint.replace("{id}", applicationId);
const messageEndpoint = contract.applications.message.endpoint.replace("{id}", applicationId);

function application(): ApplicationRead {
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

const appendedTranscript: ApplicationTranscriptRead = {
  application_id: applicationId,
  entries: [
    ...initialTranscript.entries,
    {
      type: "message",
      occurred_at: "2026-04-29T12:20:00Z",
      message_seq: 2,
      author_actor_kind: "user",
      author_actor_id: officerId,
      visibility: "applicant_visible",
      body_markdown: "Reactive transcript note",
    },
  ],
};

function officerPrincipal() {
  return {
    ...contract.auth.identity,
    provider: "pomerium",
    display_name: "Humility Officer",
    groups: ["officers"],
    discord_user_id: "210987654321098765",
  };
}

async function mockPrincipal(page: Page) {
  await page.route(`**${contract.auth.probe_endpoint}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(officerPrincipal()),
    });
  });
}

async function mockDetail(page: Page) {
  await page.route(`**${detailEndpoint}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(application()),
    });
  });
}

async function mockTranscriptSequence(page: Page) {
  let calls = 0;
  await page.route(`**${transcriptEndpoint}`, async (route) => {
    const body = calls === 0 ? initialTranscript : appendedTranscript;
    calls += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });

  return {
    calls: () => calls,
  };
}

async function mockMessageAppend(page: Page) {
  const requests: Request[] = [];
  await page.route(`**${messageEndpoint}`, async (route) => {
    requests.push(route.request());
    const payload = JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>;
    await route.fulfill({
      status: contract.applications.message.success_statuses[0],
      contentType: "application/json",
      body: JSON.stringify({
        id: "22222222-2222-4222-8222-222222222222",
        application_id: applicationId,
        message_seq: 2,
        author_actor_kind: "user",
        author_actor_id: officerId,
        visibility: "applicant_visible",
        body_markdown: "Reactive transcript note",
        client_message_id: payload.client_message_id,
        correlation_id: "33333333-3333-4333-8333-333333333333",
        causation_id: null,
        created_at: "2026-04-29T12:20:00Z",
      }),
    });
  });
  return requests;
}

test("application detail transcript updates after message append without remount", async ({
  page,
}) => {
  await mockPrincipal(page);
  await mockDetail(page);
  const transcript = await mockTranscriptSequence(page);
  const messageRequests = await mockMessageAppend(page);

  await page.goto(detailPath);

  const transcriptPanel = page.getByTestId("application-transcript");
  await expect(transcriptPanel).toContainText("queued");
  await expect(transcriptPanel).not.toContainText("Reactive transcript note");

  await page.getByLabel("Append message").fill("Reactive transcript note");
  await page.getByRole("radio", { name: /applicant|visible/i }).check();
  await page.getByRole("button", { name: /send/i }).click();

  await expect.poll(() => messageRequests.length).toBe(1);
  await expect.poll(() => transcript.calls()).toBe(2);
  await expect(transcriptPanel).toContainText("Reactive transcript note");
});
