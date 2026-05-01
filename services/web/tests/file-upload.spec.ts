import { expect, test } from "@playwright/test";

import {
  fileUploadUrlRequestSchema,
  fileUploadUrlResponseSchema,
  publicFormFieldSchema,
} from "../src/api/client";

test("publicFormFieldSchema accepts a file field", () => {
  // Risk annotation: group=TG-1;
  //   named_risk=file_field_contract_roundtrip_and_publish_validators;
  //   level=contract;
  //   source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1
  const parsed = publicFormFieldSchema.parse({
    id: "character_sheet",
    type: "file",
    label: "Character sheet",
    required: true,
    accept: ["image/png", "application/pdf"],
    max_size_bytes: 1_048_576,
    page: 2,
    visible_when: {
      field_id: "has_character_sheet",
      op: "eq",
      value: true,
    },
  });

  expect(parsed).toEqual({
    id: "character_sheet",
    type: "file",
    label: "Character sheet",
    required: true,
    accept: ["image/png", "application/pdf"],
    max_size_bytes: 1_048_576,
    page: 2,
    visible_when: {
      field_id: "has_character_sheet",
      op: "eq",
      value: true,
    },
  });
});

test("publicFormFieldSchema rejects malformed file fields", () => {
  // Risk annotation: group=TG-1;
  //   named_risk=file_field_contract_roundtrip_and_publish_validators;
  //   level=contract;
  //   source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1
  const valid = {
    id: "character_sheet",
    type: "file",
    label: "Character sheet",
    accept: ["image/png"],
    max_size_bytes: 1_048_576,
  };

  expect(publicFormFieldSchema.safeParse({ ...valid, accept: [] }).success).toBe(false);
  expect(publicFormFieldSchema.safeParse({ ...valid, accept: "image/png" }).success).toBe(false);
  expect(publicFormFieldSchema.safeParse({ ...valid, accept: undefined }).success).toBe(false);
  expect(publicFormFieldSchema.safeParse({ ...valid, max_size_bytes: 0 }).success).toBe(false);
});

test("fileUploadUrlRequestSchema accepts the upload URL request contract", () => {
  // Risk annotation: group=TG-1;
  //   named_risk=file_field_contract_roundtrip_and_publish_validators;
  //   level=contract;
  //   source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1
  expect(
    fileUploadUrlRequestSchema.parse({
      form_definition_id: "11111111-1111-4111-8111-111111111111",
      field_id: "character_sheet",
      content_type: "image/png",
      size_bytes: 1024,
    }),
  ).toEqual({
    form_definition_id: "11111111-1111-4111-8111-111111111111",
    field_id: "character_sheet",
    content_type: "image/png",
    size_bytes: 1024,
  });
  expect(
    fileUploadUrlRequestSchema.safeParse({
      form_definition_id: "11111111-1111-4111-8111-111111111111",
      field_id: "character_sheet",
      content_type: "image/png",
      size_bytes: 0,
    }).success,
  ).toBe(false);
});

test("fileUploadUrlResponseSchema accepts the upload URL response contract", () => {
  // Risk annotation: group=TG-1;
  //   named_risk=file_field_contract_roundtrip_and_publish_validators;
  //   level=contract;
  //   source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1
  const response = {
    upload_url: "https://uploads.test.local/presigned",
    object_key: "applications/11111111-1111-4111-8111-111111111111/character_sheet/22222222-2222-4222-8222-222222222222",
    expires_at: "2026-05-01T12:00:00Z",
  };

  expect(fileUploadUrlResponseSchema.parse(response)).toEqual(response);
  expect(fileUploadUrlResponseSchema.safeParse({ ...response, object_key: undefined }).success).toBe(
    false,
  );
});
