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
};

type Contract = {
  routes: {
    officer_queue: { path: string; link_name: string; requires_auth: boolean };
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
    queue: {
      endpoint: string;
      state_filter: string;
      default_states_visible: string[];
    };
    claim: {
      endpoint: string;
      method: string;
      if_match_header: boolean;
      success_status: number;
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

const queuedApplication: ApplicationRead = {
  id: "11111111-1111-4111-8111-111111111111",
  applicant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  target_scope: { scope_kind: "chapter", scope_id: "chapter-1" },
  state: "queued",
  owner_id: null,
  submitted_at: "2026-04-29T12:00:00Z",
  version: 2,
};

const submittedApplication: ApplicationRead = {
  id: "22222222-2222-4222-8222-222222222222",
  applicant_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  target_scope: { scope_kind: "chapter", scope_id: "chapter-1" },
  state: "submitted",
  owner_id: null,
  submitted_at: "2026-04-29T12:05:00Z",
  version: 1,
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

async function mockQueue(
  page: Page,
  responses: Array<{ items: ApplicationRead[]; next_after_id: string | null }>,
) {
  let callIndex = 0;
  const requests: URL[] = [];
  await page.route(`**${contract.applications.queue.endpoint}**`, async (route) => {
    requests.push(new URL(route.request().url()));
    const body = responses[Math.min(callIndex, responses.length - 1)];
    callIndex += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
  return requests;
}

test("test_officer_queue_anonymous_redirect", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=anonymous_blocked;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  let listCalled = false;
  await mockPrincipal(page, { code: "identity_missing" }, contract.auth.unauthenticated_api_status);
  await page.route(`**${contract.applications.queue.endpoint}**`, async (route) => {
    listCalled = true;
    await route.abort();
  });

  await page.goto(contract.routes.officer_queue.path);

  await expect(page.getByText(/auth|sign in|required/i)).toBeVisible();
  expect(listCalled).toBe(false);
});

test("test_officer_queue_non_officer_forbidden", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=non_officer_blocked;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  let listCalled = false;
  await mockPrincipal(page, officerPrincipal({ groups: ["applicants"] }));
  await page.route(`**${contract.applications.queue.endpoint}**`, async (route) => {
    listCalled = true;
    await route.abort();
  });

  await page.goto(contract.routes.officer_queue.path);

  await expect(page.getByText(/officer|forbidden|access/i)).toBeVisible();
  expect(listCalled).toBe(false);
});

test("test_officer_queue_no_discord_claim", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=missing_discord_claim;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  let listCalled = false;
  await mockPrincipal(page, officerPrincipal({ discord_user_id: null }));
  await page.route(`**${contract.applications.queue.endpoint}**`, async (route) => {
    listCalled = true;
    await route.abort();
  });

  await page.goto(contract.routes.officer_queue.path);

  await expect(page.getByText(/discord identity|required|incomplete/i)).toBeVisible();
  expect(listCalled).toBe(false);
});

test("test_officer_queue_lists_rows", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=happy_path_render;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  await mockPrincipal(page, officerPrincipal());
  await mockQueue(page, [{ items: [queuedApplication, submittedApplication], next_after_id: null }]);

  await page.goto(contract.routes.officer_queue.path);

  await expect(page.getByText(queuedApplication.applicant_id.slice(0, 8))).toBeVisible();
  await expect(page.getByText(submittedApplication.applicant_id.slice(0, 8))).toBeVisible();
  await expect(page.getByText("queued")).toBeVisible();
  await expect(page.getByText("submitted")).toBeVisible();
  await expect(page.getByText(String(queuedApplication.version))).toBeVisible();
  const queuedRow = page.locator(`[data-application-id="${queuedApplication.id}"]`);
  const submittedRow = page.locator(`[data-application-id="${submittedApplication.id}"]`);
  await expect(queuedRow.getByRole("button", { name: /claim/i })).toBeVisible();
  await expect(submittedRow.getByRole("button", { name: /claim/i })).toHaveCount(0);
});

test("test_officer_queue_state_filter", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=state_filter;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  await mockPrincipal(page, officerPrincipal());
  const requests = await mockQueue(page, [
    { items: [queuedApplication, submittedApplication], next_after_id: null },
    { items: [queuedApplication], next_after_id: null },
  ]);

  await page.goto(contract.routes.officer_queue.path);
  await page.getByRole("button", { name: /submitted/i }).click();

  await expect.poll(() => requests.length).toBe(2);
  expect(requests[0].searchParams.get("state")).toBe(contract.applications.queue.state_filter);
  expect(requests[1].searchParams.get("state")).toBe("queued");
});

test("test_officer_queue_load_more", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=pagination;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  await mockPrincipal(page, officerPrincipal());
  const requests = await mockQueue(page, [
    { items: [queuedApplication], next_after_id: queuedApplication.id },
    { items: [submittedApplication], next_after_id: null },
  ]);

  await page.goto(contract.routes.officer_queue.path);
  await page.getByRole("button", { name: /load more/i }).click();

  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1].searchParams.get("after_id")).toBe(queuedApplication.id);
  await expect(page.getByText(queuedApplication.applicant_id.slice(0, 8))).toBeVisible();
  await expect(page.getByText(submittedApplication.applicant_id.slice(0, 8))).toBeVisible();
});

test("test_officer_queue_claim_happy_path", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=claim_round_trip;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  await mockPrincipal(page, officerPrincipal());
  const claimed = {
    ...queuedApplication,
    state: "claimed",
    owner_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    version: 3,
  };
  const requests = await mockQueue(page, [
    { items: [queuedApplication], next_after_id: null },
    { items: [claimed], next_after_id: null },
  ]);
  let claimBody: string | null = null;
  let ifMatch: string | undefined;
  await page.route(
    `**${contract.applications.claim.endpoint.replace("{id}", queuedApplication.id)}`,
    async (route) => {
      claimBody = route.request().postData();
      ifMatch = route.request().headers()["if-match"];
      await route.fulfill({
        status: contract.applications.claim.success_status,
        contentType: "application/json",
        body: JSON.stringify(claimed),
      });
    },
  );

  await page.goto(contract.routes.officer_queue.path);
  await page.getByRole("button", { name: /claim/i }).click();

  expect(claimBody).toBeNull();
  expect(ifMatch).toBe(`"${queuedApplication.version}"`);
  await expect.poll(() => requests.length).toBe(2);
  await expect(page.locator(`[data-application-id="${queuedApplication.id}"]`)).toContainText("claimed");
  await expect(page.locator(`[data-application-id="${queuedApplication.id}"]`)).toContainText(
    claimed.owner_id.slice(0, 8),
  );
});

test("test_officer_queue_claim_conflict", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=claim_conflict;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  await mockPrincipal(page, officerPrincipal());
  const requests = await mockQueue(page, [
    { items: [queuedApplication], next_after_id: null },
    { items: [queuedApplication], next_after_id: null },
  ]);
  await page.route(
    `**${contract.applications.claim.endpoint.replace("{id}", queuedApplication.id)}`,
    async (route) => {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ code: "application_already_claimed" }),
      });
    },
  );

  await page.goto(contract.routes.officer_queue.path);
  await page.getByRole("button", { name: /claim/i }).click();

  await expect(page.getByText(/conflict|already claimed/i)).toBeVisible();
  await expect.poll(() => requests.length).toBe(2);
});

test("test_officer_queue_claim_stale_version", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=claim_stale;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  await mockPrincipal(page, officerPrincipal());
  const requests = await mockQueue(page, [
    { items: [queuedApplication], next_after_id: null },
    { items: [queuedApplication], next_after_id: null },
  ]);
  await page.route(
    `**${contract.applications.claim.endpoint.replace("{id}", queuedApplication.id)}`,
    async (route) => {
      await route.fulfill({
        status: 412,
        contentType: "application/json",
        body: JSON.stringify({ code: "stale_application_version" }),
      });
    },
  );

  await page.goto(contract.routes.officer_queue.path);
  await page.getByRole("button", { name: /claim/i }).click();

  await expect(page.getByText(/stale|version|refresh/i)).toBeVisible();
  await expect.poll(() => requests.length).toBe(2);
});

test("test_officer_queue_claim_forbidden", async ({ page }) => {
  // Risk annotation: group=TG-3;
  //   named_risk=claim_forbidden;
  //   level=component;
  //   source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-3
  await mockPrincipal(page, officerPrincipal());
  await mockQueue(page, [
    { items: [queuedApplication], next_after_id: null },
    { items: [queuedApplication], next_after_id: null },
  ]);
  await page.route(
    `**${contract.applications.claim.endpoint.replace("{id}", queuedApplication.id)}`,
    async (route) => {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ code: "authority_decision_denied" }),
      });
    },
  );

  await page.goto(contract.routes.officer_queue.path);
  await page.getByRole("button", { name: /claim/i }).click();

  await expect(page.getByText(/forbidden|not allowed|permission/i)).toBeVisible();
  await expect(
    page.locator(`[data-application-id="${queuedApplication.id}"]`).getByRole("button", {
      name: /claim/i,
    }),
  ).toHaveCount(0);
});
