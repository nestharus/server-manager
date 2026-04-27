import { parse } from "yaml";
import { z } from "zod";

import rawDarkNemesisYaml from "../../../../../forms/dark-nemesis.yaml?raw";

const questionSchema = z.object({
  id: z.string().regex(/^[a-z][a-z0-9_]{0,63}$/),
  type: z.enum(["short", "long", "number", "select", "multi_select", "boolean"]),
  label: z.string().min(1),
  required: z.boolean().default(false),
  max_length: z.number().int().positive().optional(),
  options: z.array(z.string().min(1)).optional(),
});

const formSchema = z.object({
  id: z.string(),
  title: z.string(),
  questions: z.array(questionSchema).min(1),
});

export type FormQuestion = z.infer<typeof questionSchema>;
export type FormDefinition = z.infer<typeof formSchema>;
export type FormResponses = Record<string, unknown>;

export const darkNemesisForm = formSchema.parse(parse(rawDarkNemesisYaml));

export function createResponseSchema(definition: FormDefinition) {
  const entries = definition.questions.map((question) => {
    let valueSchema: z.ZodType;
    if (question.type === "number") {
      valueSchema = z.coerce.number();
    } else if (question.type === "multi_select") {
      valueSchema = z.array(z.string());
    } else if (question.type === "boolean") {
      valueSchema = z.boolean();
    } else {
      valueSchema = z.string();
    }

    if (!question.required) {
      valueSchema = valueSchema.optional();
    }
    return [question.id, valueSchema] as const;
  });

  return z.object(Object.fromEntries(entries));
}

export function defaultResponses(definition: FormDefinition): FormResponses {
  return Object.fromEntries(
    definition.questions.map((question) => {
      if (question.type === "multi_select") {
        return [question.id, []];
      }
      if (question.type === "boolean") {
        return [question.id, false];
      }
      return [question.id, ""];
    }),
  );
}
