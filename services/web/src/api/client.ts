import { z } from "zod";

const principalSchema = z.object({
  subject: z.string(),
  email: z.string().nullable(),
  display_name: z.string().nullable(),
  provider: z.literal("pomerium"),
  groups: z.array(z.string()),
  discord_user_id: z.string().nullable(),
});

const chapterListSchema = z.object({
  chapters: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      state: z.string(),
      version: z.number(),
      created_at: z.string(),
    }),
  ),
});

const publicChapterSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
});

export const publicChapterListSchema = z.object({
  chapters: z.array(publicChapterSummarySchema),
});

const basePublicFormFieldSchema = z.object({
  id: z.string(),
  label: z.string(),
  required: z.boolean().default(false),
});

export const publicFormFieldSchema = z.discriminatedUnion("type", [
  basePublicFormFieldSchema.extend({
    type: z.literal("short"),
    max_length: z.number().nullable().optional(),
  }),
  basePublicFormFieldSchema.extend({
    type: z.literal("long"),
    max_length: z.number().nullable().optional(),
  }),
  basePublicFormFieldSchema.extend({
    type: z.literal("number"),
  }),
  basePublicFormFieldSchema.extend({
    type: z.literal("select"),
    options: z.array(z.string()),
  }),
  basePublicFormFieldSchema.extend({
    type: z.literal("multi_select"),
    options: z.array(z.string()),
  }),
  basePublicFormFieldSchema.extend({
    type: z.literal("boolean"),
  }),
  basePublicFormFieldSchema.extend({
    type: z.literal("chapter_select"),
    required: z.literal(true),
    placeholder: z.string().nullable().optional(),
  }),
]);

export const publicFormDefinitionSchema = z.object({
  id: z.string(),
  name: z.string(),
  target_type: z.string(),
  scope: z.object({
    scope_kind: z.string(),
    scope_id: z.string().nullable(),
  }),
  fields: z.array(publicFormFieldSchema),
  routing_rules: z.record(z.string(), z.unknown()).default({}),
  version: z.number(),
  status: z.string(),
  published_at: z.string(),
  archived_at: z.string().nullable().optional(),
  created_at: z.string(),
});

const submissionResponseBodySchema = z.object({
  code: z.string().optional(),
  message: z.string().optional(),
  application_id: z.string().optional(),
  parse_error: z.boolean().optional(),
  raw_text: z.string().optional(),
  content_type: z.string().optional(),
});

export const applicationStateSchema = z.enum([
  "submitted",
  "queued",
  "claimed",
  "in_review",
  "interview",
  "waitlisted",
  "approved",
  "denied",
  "withdrawn",
]);

export const applicationScopeSchema = z.object({
  scope_kind: z.string(),
  scope_id: z.string().nullable(),
});

export const applicationReadSchema = z
  .object({
    id: z.string(),
    applicant_id: z.string(),
    form_definition_id: z.string().default(""),
    form_version: z.number().default(1),
    form_snapshot: z.record(z.string(), z.unknown()).default({}),
    target_scope: applicationScopeSchema,
    responses: z.record(z.string(), z.unknown()).default({}),
    state: applicationStateSchema,
    owner_id: z.string().nullable(),
    interview_thread_id: z.string().nullable().default(null),
    decision_reason: z.string().nullable().default(null),
    submitted_at: z.string(),
    queued_at: z.string().nullable().default(null),
    claimed_at: z.string().nullable().default(null),
    review_started_at: z.string().nullable().default(null),
    decided_at: z.string().nullable().default(null),
    withdrawn_at: z.string().nullable().default(null),
    created_at: z.string().default(""),
    updated_at: z.string().default(""),
    version: z.number(),
  })
  .passthrough();

export const applicationListReadSchema = z.object({
  items: z.array(applicationReadSchema),
  next_after_id: z.string().nullable(),
});

export const applicationMessageVisibilitySchema = z.enum([
  "applicant_visible",
  "officer_only",
]);

export const applicationMessageReadSchema = z.object({
  id: z.string(),
  application_id: z.string(),
  message_seq: z.number(),
  author_actor_kind: z.string(),
  author_actor_id: z.string(),
  visibility: applicationMessageVisibilitySchema,
  body_markdown: z.string(),
  client_message_id: z.string().nullable(),
  correlation_id: z.string(),
  causation_id: z.string().nullable(),
  created_at: z.string(),
});

export const applicationTransitionActionSchema = z.enum([
  "route",
  "claim",
  "review",
  "request_interview",
  "waitlist",
  "reassign",
  "reactivate",
  "approve",
  "deny",
  "withdraw",
]);

export const applicationTransitionRequestSchema = z.object({
  action: applicationTransitionActionSchema,
  notes: z.string().optional(),
  decision_reason: z.string().optional(),
  thread_id: z.string().optional(),
  reason: z.string().optional(),
  new_owner_id: z.string().optional(),
});

export const applicationTransitionResponseSchema = applicationReadSchema;

export const applicationStateChangeEntrySchema = z.object({
  type: z.literal("state_change"),
  occurred_at: z.string(),
  change_type: z.string(),
  from_state: applicationStateSchema.nullable(),
  to_state: applicationStateSchema.nullable(),
  actor_kind: z.string(),
  actor_id: z.string(),
  aggregate_seq: z.number(),
});

export const applicationMessageEntrySchema = z.object({
  type: z.literal("message"),
  occurred_at: z.string(),
  message_seq: z.number(),
  author_actor_kind: z.string(),
  author_actor_id: z.string(),
  visibility: z.enum(["applicant_visible", "officer_only"]),
  body_markdown: z.string(),
});

export const applicationTranscriptEntrySchema = z.discriminatedUnion("type", [
  applicationStateChangeEntrySchema,
  applicationMessageEntrySchema,
]);

export const applicationTranscriptReadSchema = z.object({
  application_id: z.string(),
  entries: z.array(applicationTranscriptEntrySchema),
});

export type CurrentPrincipal = z.infer<typeof principalSchema>;
export type AdminChapterSummary = z.infer<typeof chapterListSchema>["chapters"][number];
export type PublicChapterSummary = z.infer<typeof publicChapterSummarySchema>;
export type PublicFormDefinition = z.infer<typeof publicFormDefinitionSchema>;
export type PublicFormField = z.infer<typeof publicFormFieldSchema>;
export type ApplicationState = z.infer<typeof applicationStateSchema>;
export type ApplicationRead = z.infer<typeof applicationReadSchema>;
export type ApplicationListRead = z.infer<typeof applicationListReadSchema>;
export type ApplicationMessageVisibility = z.infer<typeof applicationMessageVisibilitySchema>;
export type ApplicationMessageRead = z.infer<typeof applicationMessageReadSchema>;
export type ApplicationTransitionAction = z.infer<typeof applicationTransitionActionSchema>;
export type ApplicationTransitionRequest = z.infer<typeof applicationTransitionRequestSchema>;
export type ApplicationTranscriptEntry = z.infer<typeof applicationTranscriptEntrySchema>;
export type ApplicationTranscriptRead = z.infer<typeof applicationTranscriptReadSchema>;
export type SubmissionResponseBody = z.infer<typeof submissionResponseBodySchema>;

export class ApiError extends Error {
  readonly status: number;
  readonly path: string;
  readonly statusText: string;
  readonly payload: unknown;

  constructor(input: { status: number; path: string; statusText?: string; payload?: unknown }) {
    super(`${input.path} returned ${input.status}`);
    this.name = "ApiError";
    this.status = input.status;
    this.path = input.path;
    this.statusText = input.statusText ?? "";
    this.payload = input.payload;
  }
}

async function readErrorPayload(response: Response): Promise<unknown> {
  const text = await response.text().catch(() => "");
  if (!text) return undefined;
  const contentType = response.headers.get("content-type") ?? "";
  if (isJsonContentType(contentType)) {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }
  return text;
}

function isJsonContentType(contentType: string) {
  return /\bjson\b|\+json\b/i.test(contentType);
}

function responseTextExcerpt(rawText: string) {
  const normalized = rawText.trim().replace(/\s+/g, " ");
  return normalized.length > 240 ? `${normalized.slice(0, 237)}...` : normalized;
}

async function getJson<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  const response = await fetch(path, {
    headers: {
      Accept: "application/json",
    },
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new ApiError({
      status: response.status,
      path,
      statusText: response.statusText,
      payload: await readErrorPayload(response),
    });
  }
  return schema.parse(await response.json());
}

async function readSubmissionResponseBody(
  path: string,
  response: Response,
): Promise<SubmissionResponseBody> {
  const contentType = response.headers.get("content-type") ?? "";
  const fallbackMessage = response.ok
    ? "Application response was not JSON."
    : `${path} returned ${response.status}`;

  if (!isJsonContentType(contentType)) {
    const rawText = await response.text().catch(() => "");
    return {
      message: responseTextExcerpt(rawText) || fallbackMessage,
      parse_error: true,
      raw_text: rawText,
      content_type: contentType || undefined,
    };
  }

  const textFallbackResponse = response.clone();
  try {
    const rawBody = await response.json();
    return submissionResponseBodySchema.parse(rawBody);
  } catch (error) {
    if (error instanceof z.ZodError) throw error;
    const rawText = await textFallbackResponse.text().catch(() => "");
    return {
      message: responseTextExcerpt(rawText) || `${fallbackMessage}: invalid JSON response.`,
      parse_error: true,
      raw_text: rawText,
      content_type: contentType || undefined,
    };
  }
}

export async function fetchCurrentPrincipal() {
  return await getJson("/api/me", principalSchema);
}

export async function fetchAdminChapters() {
  const payload = await getJson("/api/web/admin/chapters", chapterListSchema);
  return payload.chapters;
}

export async function fetchPublicChapters() {
  const payload = await getJson("/api/public/chapters", publicChapterListSchema);
  return payload.chapters;
}

export async function fetchPublicApplicationForm() {
  return await getJson("/api/public/application-forms/current", publicFormDefinitionSchema);
}

export async function fetchApplicantDiscordIdentity() {
  return await getJson(
    "/auth/discord/me",
    z.object({
      discord_user_id: z.string(),
    }),
  );
}

export async function submitPublicApplication(payload: unknown) {
  const path = "/api/public/applications";
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await readSubmissionResponseBody(path, response);
  return {
    status: response.status,
    body,
  };
}

export async function fetchOfficerApplicationQueue(input: {
  states: readonly ApplicationState[];
  limit?: number;
  afterId?: string | null;
}) {
  if (input.states.length === 0) {
    throw new Error("At least one application state is required.");
  }
  const params = new URLSearchParams();
  params.set("state", input.states.join(","));
  if (input.limit !== undefined) params.set("limit", String(input.limit));
  if (input.afterId) params.set("after_id", input.afterId);
  return await getJson(`/api/web/officer/applications?${params.toString()}`, applicationListReadSchema);
}

export async function fetchOfficerApplication(applicationId: string) {
  return await getJson(
    `/api/web/officer/applications/${applicationId}`,
    applicationReadSchema,
  );
}

export async function fetchOfficerApplicationTranscript(applicationId: string) {
  return await getJson(
    `/api/web/officer/applications/${applicationId}/transcript`,
    applicationTranscriptReadSchema,
  );
}

export async function claimOfficerApplication(input: {
  applicationId: string;
  expectedVersion: number;
}) {
  const path = `/api/web/officer/applications/${input.applicationId}/claim`;
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    // No Content-Type is sent because this POST intentionally has no body.
    headers: {
      Accept: "application/json",
      "If-Match": `"${input.expectedVersion}"`,
    },
  });
  if (!response.ok) {
    throw new ApiError({
      status: response.status,
      path,
      statusText: response.statusText,
      payload: await readErrorPayload(response),
    });
  }
  return applicationTransitionResponseSchema.parse(await response.json());
}

export async function appendOfficerApplicationMessage(input: {
  applicationId: string;
  bodyMarkdown: string;
  visibility: ApplicationMessageVisibility;
  clientMessageId: string;
}) {
  const path = `/api/web/officer/applications/${input.applicationId}/messages`;
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      body_markdown: input.bodyMarkdown,
      visibility: input.visibility,
      client_message_id: input.clientMessageId,
    }),
  });
  if (!response.ok) {
    throw new ApiError({
      status: response.status,
      path,
      statusText: response.statusText,
      payload: await readErrorPayload(response),
    });
  }
  return applicationMessageReadSchema.parse(await response.json());
}

export async function transitionOfficerApplication(input: {
  applicationId: string;
  expectedVersion: number;
  request: ApplicationTransitionRequest;
}) {
  const path = `/api/web/officer/applications/${input.applicationId}/transitions`;
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "If-Match": `"${input.expectedVersion}"`,
    },
    body: JSON.stringify(input.request),
  });
  if (!response.ok) {
    throw new ApiError({
      status: response.status,
      path,
      statusText: response.statusText,
      payload: await readErrorPayload(response),
    });
  }
  return applicationTransitionResponseSchema.parse(await response.json());
}
