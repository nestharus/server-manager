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
    target_scope: applicationScopeSchema,
    state: applicationStateSchema,
    owner_id: z.string().nullable(),
    submitted_at: z.string(),
    version: z.number(),
  })
  .passthrough();

export const applicationListReadSchema = z.object({
  items: z.array(applicationReadSchema),
  next_after_id: z.string().nullable(),
});

export const applicationTransitionRequestSchema = z.object({
  action: z.literal("claim"),
});

export const applicationTransitionResponseSchema = applicationReadSchema;

export type CurrentPrincipal = z.infer<typeof principalSchema>;
export type AdminChapterSummary = z.infer<typeof chapterListSchema>["chapters"][number];
export type ApplicationState = z.infer<typeof applicationStateSchema>;
export type ApplicationRead = z.infer<typeof applicationReadSchema>;
export type ApplicationListRead = z.infer<typeof applicationListReadSchema>;

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
  if (contentType.includes("application/json")) {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }
  return text;
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

export async function fetchCurrentPrincipal() {
  return await getJson("/api/me", principalSchema);
}

export async function fetchAdminChapters() {
  const payload = await getJson("/api/web/admin/chapters", chapterListSchema);
  return payload.chapters;
}

export async function fetchApplicantDiscordIdentity() {
  return await getJson(
    "/auth/discord/me",
    z.object({
      discord_user_id: z.string(),
    }),
  );
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

export async function claimOfficerApplication(input: {
  applicationId: string;
  expectedVersion: number;
}) {
  const path = `/api/web/officer/applications/${input.applicationId}/claim`;
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
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
