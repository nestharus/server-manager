import type { PublicFormField } from "@/api/client";

export function evaluateVisibility(
  fields: PublicFormField[],
  responses: Record<string, unknown>,
): Record<string, boolean> {
  const visibility: Record<string, boolean> = {};

  for (const field of fields) {
    const predicate = field.visible_when;
    if (!predicate) {
      visibility[field.id] = true;
      continue;
    }

    if (!visibility[predicate.field_id] || !hasOwn(responses, predicate.field_id)) {
      visibility[field.id] = false;
      continue;
    }

    const sourceValue = responses[predicate.field_id];
    if (predicate.op === "eq") {
      visibility[field.id] = sourceValue === predicate.value;
    } else if (predicate.op === "neq") {
      visibility[field.id] = sourceValue !== predicate.value;
    } else if (predicate.op === "in") {
      visibility[field.id] = Array.isArray(predicate.value)
        && predicate.value.includes(sourceValue);
    } else {
      visibility[field.id] = Array.isArray(predicate.value)
        && !predicate.value.includes(sourceValue);
    }
  }

  return visibility;
}

export function derivePages(fields: PublicFormField[]): number[] {
  return Array.from(new Set(fields.map((field) => field.page ?? 1))).sort(
    (left, right) => left - right,
  );
}

export function pageVisibleFields(
  fields: PublicFormField[],
  page: number,
  visibility: Record<string, boolean>,
): PublicFormField[] {
  return fields.filter((field) => (field.page ?? 1) === page && visibility[field.id]);
}

function hasOwn(values: Record<string, unknown>, key: string) {
  return Object.prototype.hasOwnProperty.call(values, key);
}
