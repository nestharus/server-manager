import { expect, test, type Page } from "@playwright/test";

const FORM_ROUTE = "/applications";
const PUBLIC_FORM_ENDPOINT = "/api/public/application-forms/current";
const PUBLIC_CHAPTERS_ENDPOINT = "/api/public/chapters";
const PUBLIC_SUBMIT_ENDPOINT = "/api/public/applications";
const CHAPTER_ID = "chapter-alpha";

type SubmittedPayload = {
  scope?: { scope_kind?: string; scope_id?: string | null };
  responses?: Record<string, unknown>;
};

const selectorForm = {
  id: "form-selector",
  name: "Public Application",
  target_type: "chapter_membership",
  scope: { scope_kind: "global", scope_id: null },
  fields: [
    {
      id: "chapter",
      type: "chapter_select",
      label: "Chapter",
      required: true,
      placeholder: "Choose a chapter",
    },
    {
      id: "character_name",
      type: "short",
      label: "Character name",
      required: true,
      max_length: 64,
    },
    {
      id: "application_text",
      type: "long",
      label: "Application text",
      required: true,
      max_length: 4000,
    },
  ],
  routing_rules: {
    schema_version: 1,
    queue: "chapter_officers",
    review_scope: null,
  },
  version: 2,
  status: "current",
  published_at: "2026-04-30T12:00:00Z",
  archived_at: null,
  created_at: "2026-04-30T12:00:00Z",
};

const textOnlyForm = {
  ...selectorForm,
  id: "form-global",
  fields: selectorForm.fields.filter((field) => field.type !== "chapter_select"),
  version: 1,
};

const multiSelectForm = {
  ...textOnlyForm,
  id: "form-multi-select",
  fields: [
    ...textOnlyForm.fields,
    {
      id: "activity_preferences",
      type: "multi_select",
      label: "Activity preferences",
      required: false,
      options: ["Raids", "Dungeons", "PvP"],
    },
  ],
};

const multiPageForm = {
  ...textOnlyForm,
  id: "form-multi-page",
  fields: [
    {
      id: "character_name",
      type: "short",
      label: "Character name",
      required: true,
      max_length: 64,
      page: 1,
    },
    {
      id: "application_text",
      type: "long",
      label: "Application text",
      required: true,
      max_length: 4000,
      page: 2,
    },
  ],
};

const conditionalForm = {
  ...textOnlyForm,
  id: "form-conditional",
  fields: [
    {
      id: "character_name",
      type: "short",
      label: "Character name",
      required: true,
      max_length: 64,
      page: 1,
    },
    {
      id: "officer_interest",
      type: "select",
      label: "Officer interest",
      required: true,
      options: ["No", "Yes"],
      page: 1,
    },
    {
      id: "officer_statement",
      type: "long",
      label: "Officer statement",
      required: true,
      max_length: 4000,
      page: 1,
      visible_when: {
        field_id: "officer_interest",
        op: "eq",
        value: "Yes",
      },
    },
    {
      id: "application_text",
      type: "long",
      label: "Application text",
      required: true,
      max_length: 4000,
      page: 2,
    },
  ],
};

async function mockVerifiedApplicant(page: Page) {
  await page.route("**/auth/discord/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ discord_user_id: "123456789012345678" }),
    });
  });
}

async function mockPublicForm(page: Page, formDefinition: unknown) {
  await page.route(`**${PUBLIC_FORM_ENDPOINT}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(formDefinition),
    });
  });
}

async function mockPublicChapters(page: Page) {
  const requests: string[] = [];
  await page.route(`**${PUBLIC_CHAPTERS_ENDPOINT}`, async (route) => {
    requests.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        chapters: [{ id: CHAPTER_ID, name: "Alpha Chapter" }],
      }),
    });
  });
  return requests;
}

async function mockPublicSubmit(page: Page) {
  const payloads: SubmittedPayload[] = [];
  await page.route(`**${PUBLIC_SUBMIT_ENDPOINT}`, async (route) => {
    payloads.push(route.request().postDataJSON() as SubmittedPayload);
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        message: "Application received",
        application_id: "11111111-1111-4111-8111-111111111111",
      }),
    });
  });
  return payloads;
}

test("test_chapter_select_renders_as_native_select", async ({ page }) => {
  // Risk annotation: group=TG-5;
  //   named_risk=spa_chapter_selector_payload_contract;
  //   level=component;
  //   source=.tmp/init-135/phase6/step6a-contract.md#TG-5
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, selectorForm);
  await mockPublicChapters(page);

  await page.goto(FORM_ROUTE);

  const select = page.getByLabel("Chapter");
  await expect(select).toBeVisible();
  await expect(select).toHaveJSProperty("tagName", "SELECT");
  await expect(select.locator("option")).toHaveText(["Choose a chapter", "Alpha Chapter"]);
  await expect(select.locator("option").first()).toBeDisabled();
});

test("test_required_chapter_select_blocks_submit_when_empty", async ({ page }) => {
  // Risk annotation: group=TG-5;
  //   named_risk=spa_chapter_selector_payload_contract;
  //   level=component;
  //   source=.tmp/init-135/phase6/step6a-contract.md#TG-5
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, selectorForm);
  await mockPublicChapters(page);
  const payloads = await mockPublicSubmit(page);

  await page.goto(FORM_ROUTE);
  const chapterSelect = page.getByLabel("Chapter");
  await page.getByLabel("Character name").fill("Kalec");
  await page.getByLabel("Application text").fill("I want to join scheduled guild activities.");
  await expect(chapterSelect).toHaveValue("");
  await page.getByRole("button", { name: "Submit application" }).click();

  await expect(chapterSelect).toBeFocused();
  await expect
    .poll(async () =>
      chapterSelect.evaluate((element) => (element as HTMLSelectElement).validity.valueMissing),
    )
    .toBe(true);
  await expect.poll(() => payloads.length).toBe(0);
});

test("test_chapter_select_fetches_from_public_chapters_endpoint", async ({ page }) => {
  // Risk annotation: group=TG-5;
  //   named_risk=spa_chapter_selector_payload_contract;
  //   level=component;
  //   source=.tmp/init-135/phase6/step6a-contract.md#TG-5
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, selectorForm);
  const chapterRequests = await mockPublicChapters(page);

  await page.goto(FORM_ROUTE);

  await expect(page.getByRole("option", { name: "Alpha Chapter" })).toBeVisible();
  expect(chapterRequests).toHaveLength(1);
});

test("test_submit_payload_includes_chapter_scope_and_response", async ({ page }) => {
  // Risk annotation: group=TG-5;
  //   named_risk=spa_chapter_selector_payload_contract;
  //   level=component;
  //   source=.tmp/init-135/phase6/step6a-contract.md#TG-5
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, selectorForm);
  await mockPublicChapters(page);
  const payloads = await mockPublicSubmit(page);

  await page.goto(FORM_ROUTE);
  await page.getByLabel("Chapter").selectOption(CHAPTER_ID);
  await page.getByLabel("Character name").fill("Kalec");
  await page.getByLabel("Application text").fill("I want to join scheduled guild activities.");
  await page.getByRole("button", { name: "Submit application" }).click();

  await expect.poll(() => payloads.length).toBe(1);
  expect(payloads[0].scope).toEqual({ scope_kind: "chapter", scope_id: CHAPTER_ID });
  expect(payloads[0].responses?.chapter).toBe(CHAPTER_ID);
  expect(payloads[0].responses?.character_name).toBe("Kalec");
  expect(payloads[0].responses?.application_text).toBe(
    "I want to join scheduled guild activities.",
  );
});

test("test_existing_two_text_field_path_remains_functional", async ({ page }) => {
  // Risk annotation: group=TG-5;
  //   named_risk=spa_chapter_selector_payload_contract;
  //   level=component;
  //   source=.tmp/init-135/phase6/step6a-contract.md#TG-5
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, textOnlyForm);
  const payloads = await mockPublicSubmit(page);
  let chapterListCalled = false;
  await page.route(`**${PUBLIC_CHAPTERS_ENDPOINT}`, async (route) => {
    chapterListCalled = true;
    await route.abort();
  });

  await page.goto(FORM_ROUTE);
  await expect(page.getByLabel("Chapter")).toHaveCount(0);
  await page.getByLabel("Character name").fill("Kalec");
  await page.getByLabel("Application text").fill("I want to join scheduled guild activities.");
  await page.getByRole("button", { name: "Submit application" }).click();

  await expect.poll(() => payloads.length).toBe(1);
  expect(payloads[0].scope).toEqual({ scope_kind: "global", scope_id: null });
  expect(payloads[0].responses).toEqual({
    character_name: "Kalec",
    application_text: "I want to join scheduled guild activities.",
  });
  expect(chapterListCalled).toBe(false);
});

test("test_draft_restore_preserves_multi_select_values", async ({ page }) => {
  await page.addInitScript(() => {
    window.sessionStorage.setItem(
      "humility.publicApplication.draft",
      JSON.stringify({ activity_preferences: ["Raids", "Dungeons"] }),
    );
  });
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, multiSelectForm);
  const payloads = await mockPublicSubmit(page);

  await page.goto(FORM_ROUTE);
  await expect(page.getByLabel("Activity preferences")).toHaveValues(["Raids", "Dungeons"]);
  await page.getByLabel("Character name").fill("Kalec");
  await page.getByLabel("Application text").fill("I want to join scheduled guild activities.");
  await page.getByRole("button", { name: "Submit application" }).click();

  await expect.poll(() => payloads.length).toBe(1);
  expect(payloads[0].responses?.activity_preferences).toEqual(["Raids", "Dungeons"]);
});

test("test_multipage_initial_render_shows_page_one_and_step_indicator", async ({ page }) => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, multiPageForm);

  await page.goto(FORM_ROUTE);

  await expect(page.getByText("Step 1 of 2")).toBeVisible();
  await expect(page.getByLabel("Character name")).toBeVisible();
  await expect(page.getByLabel("Application text")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Next" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Submit application" })).toHaveCount(0);
});

test("test_next_button_validates_current_page_required_fields", async ({ page }) => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, multiPageForm);

  await page.goto(FORM_ROUTE);
  await page.getByRole("button", { name: "Next" }).click();

  await expect(page.getByText("Step 1 of 2")).toBeVisible();
  await expect(page.getByLabel("Character name")).toBeFocused();

  await page.getByLabel("Character name").fill("Kalec");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Step 2 of 2")).toBeVisible();
  await expect(page.getByLabel("Application text")).toBeVisible();
});

test("test_previous_button_preserves_prior_responses", async ({ page }) => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, multiPageForm);

  await page.goto(FORM_ROUTE);
  await page.getByLabel("Character name").fill("Kalec");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Previous" }).click();

  await expect(page.getByText("Step 1 of 2")).toBeVisible();
  await expect(page.getByLabel("Character name")).toHaveValue("Kalec");
});

test("test_visible_when_toggles_fields_when_source_response_changes", async ({ page }) => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, conditionalForm);

  await page.goto(FORM_ROUTE);
  await expect(page.getByLabel("Officer statement")).toHaveCount(0);

  await page.getByLabel("Officer interest").selectOption("Yes");
  await expect(page.getByLabel("Officer statement")).toBeVisible();

  await page.getByLabel("Officer interest").selectOption("No");
  await expect(page.getByLabel("Officer statement")).toHaveCount(0);
});

test("test_submit_only_appears_on_last_page_and_posts_visible_fields", async ({ page }) => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, conditionalForm);
  const payloads = await mockPublicSubmit(page);

  await page.goto(FORM_ROUTE);
  await expect(page.getByRole("button", { name: "Submit application" })).toHaveCount(0);
  await page.getByLabel("Character name").fill("Kalec");
  await page.getByLabel("Officer interest").selectOption("Yes");
  await page.getByLabel("Officer statement").fill("I can help review applications.");
  await page.getByRole("button", { name: "Next" }).click();

  await expect(page.getByText("Step 2 of 2")).toBeVisible();
  await expect(page.getByRole("button", { name: "Next" })).toHaveCount(0);
  await expect(page.getByTestId("application-submit-icon")).toBeVisible();
  await page.getByLabel("Application text").fill("I want to join scheduled guild activities.");
  await page.getByRole("button", { name: "Submit application" }).click();

  await expect.poll(() => payloads.length).toBe(1);
  expect(payloads[0].responses).toEqual({
    character_name: "Kalec",
    officer_interest: "Yes",
    officer_statement: "I can help review applications.",
    application_text: "I want to join scheduled guild activities.",
  });
});

test("test_hidden_dependent_field_value_does_not_appear_in_submit_payload", async ({ page }) => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4-F4
  await mockVerifiedApplicant(page);
  await mockPublicForm(page, conditionalForm);
  const payloads = await mockPublicSubmit(page);

  await page.goto(FORM_ROUTE);
  await page.getByLabel("Character name").fill("Kalec");
  await page.getByLabel("Officer interest").selectOption("Yes");
  await page.getByLabel("Officer statement").fill("This value must be stripped.");
  await page.getByLabel("Officer interest").selectOption("No");
  await expect(page.getByLabel("Officer statement")).toHaveCount(0);
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Application text").fill("I want to join scheduled guild activities.");
  await page.getByRole("button", { name: "Submit application" }).click();

  await expect.poll(() => payloads.length).toBe(1);
  expect(payloads[0].responses).toEqual({
    character_name: "Kalec",
    officer_interest: "No",
    application_text: "I want to join scheduled guild activities.",
  });
  expect(payloads[0].responses?.officer_statement).toBeUndefined();
});
