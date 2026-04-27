import { z } from "zod";

const principalSchema = z.object({
  subject: z.string(),
  email: z.string().nullable(),
  display_name: z.string().nullable(),
  provider: z.literal("pomerium"),
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

export type CurrentPrincipal = z.infer<typeof principalSchema>;
export type AdminChapterSummary = z.infer<typeof chapterListSchema>["chapters"][number];

async function getJson<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  const response = await fetch(path, {
    headers: {
      Accept: "application/json",
    },
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return schema.parse(await response.json());
}

export function fetchCurrentPrincipal() {
  return getJson("/api/v1/me", principalSchema);
}

export async function fetchAdminChapters() {
  const payload = await getJson("/api/v1/web/admin/chapters", chapterListSchema);
  return payload.chapters;
}
