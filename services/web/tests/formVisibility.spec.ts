import { expect, test } from "@playwright/test";

import { evaluateVisibility } from "../src/features/public/formVisibility";

type FieldFixture = Parameters<typeof evaluateVisibility>[0][number];

function field(
  id: string,
  options: Partial<FieldFixture> = {},
): FieldFixture {
  return {
    id,
    type: "short",
    label: id.replaceAll("_", " "),
    required: false,
    page: 1,
    max_length: 64,
    visible_when: null,
    ...options,
  } as FieldFixture;
}

test("test_evaluate_visibility_returns_true_for_field_with_no_visible_when", () => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
  expect(evaluateVisibility([field("always")], {})).toEqual({ always: true });
});

test.describe("operator semantics", () => {
  const cases: Array<{
    name: string;
    op: "eq" | "neq" | "in" | "not_in";
    value: unknown;
    sourceResponse: unknown;
    expected: boolean;
  }> = [
    { name: "eq true", op: "eq", value: "yes", sourceResponse: "yes", expected: true },
    { name: "eq false", op: "eq", value: "yes", sourceResponse: "no", expected: false },
    { name: "neq true", op: "neq", value: "yes", sourceResponse: "no", expected: true },
    { name: "neq false", op: "neq", value: "yes", sourceResponse: "yes", expected: false },
    {
      name: "in true",
      op: "in",
      value: ["yes", "maybe"],
      sourceResponse: "yes",
      expected: true,
    },
    {
      name: "in false",
      op: "in",
      value: ["yes", "maybe"],
      sourceResponse: "no",
      expected: false,
    },
    {
      name: "not_in true",
      op: "not_in",
      value: ["yes", "maybe"],
      sourceResponse: "no",
      expected: true,
    },
    {
      name: "not_in false",
      op: "not_in",
      value: ["yes", "maybe"],
      sourceResponse: "yes",
      expected: false,
    },
  ];

  for (const testCase of cases) {
    test(`test_evaluate_visibility_${testCase.name.replaceAll(" ", "_")}`, () => {
      // Risk annotation: group=TG-4;
      //   named_risk=spa_wizard_visibility_payload_contract;
      //   level=component;
      //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
      const fields = [
        field("source"),
        field("dependent", {
          visible_when: {
            field_id: "source",
            op: testCase.op,
            value: testCase.value,
          },
        }),
      ];

      expect(evaluateVisibility(fields, { source: testCase.sourceResponse })).toEqual({
        source: true,
        dependent: testCase.expected,
      });
    });
  }
});

test.describe("missing and hidden source behavior", () => {
  const cases: Array<{
    op: "eq" | "neq" | "in" | "not_in";
    value: unknown;
    hiddenSourceResponse: unknown;
  }> = [
    { op: "eq", value: "yes", hiddenSourceResponse: "yes" },
    { op: "neq", value: "yes", hiddenSourceResponse: "no" },
    { op: "in", value: ["yes"], hiddenSourceResponse: "yes" },
    { op: "not_in", value: ["yes"], hiddenSourceResponse: "no" },
  ];

  for (const testCase of cases) {
    test(`test_missing_source_is_false_for_${testCase.op}`, () => {
      // Risk annotation: group=TG-4;
      //   named_risk=spa_wizard_visibility_payload_contract;
      //   level=component;
      //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4-F1
      const fields = [
        field("source"),
        field("dependent", {
          visible_when: {
            field_id: "source",
            op: testCase.op,
            value: testCase.value,
          },
        }),
      ];

      expect(evaluateVisibility(fields, {})).toEqual({
        source: true,
        dependent: false,
      });
    });

    test(`test_hidden_source_is_false_for_${testCase.op}`, () => {
      // Risk annotation: group=TG-4;
      //   named_risk=spa_wizard_visibility_payload_contract;
      //   level=component;
      //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4-F1
      const fields = [
        field("gate", {
          type: "boolean",
          max_length: undefined,
        }),
        field("source", {
          visible_when: {
            field_id: "gate",
            op: "eq",
            value: true,
          },
        }),
        field("dependent", {
          visible_when: {
            field_id: "source",
            op: testCase.op,
            value: testCase.value,
          },
        }),
      ];

      expect(
        evaluateVisibility(fields, {
          gate: false,
          source: testCase.hiddenSourceResponse,
        }),
      ).toEqual({
        gate: true,
        source: false,
        dependent: false,
      });
    });
  }
});

test("test_chained_visibility_allows_a_b_c_when_links_are_visible", () => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
  const fields = [
    field("a", { type: "select", options: ["yes", "no"], max_length: undefined }),
    field("b", {
      visible_when: { field_id: "a", op: "eq", value: "yes" },
    }),
    field("c", {
      visible_when: { field_id: "b", op: "eq", value: "value" },
    }),
  ];

  expect(evaluateVisibility(fields, { a: "yes", b: "value" })).toEqual({
    a: true,
    b: true,
    c: true,
  });
});

test("test_chained_visibility_breaks_when_middle_source_is_hidden", () => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4-F1
  const fields = [
    field("a", { type: "select", options: ["yes", "no"], max_length: undefined }),
    field("b", {
      visible_when: { field_id: "a", op: "eq", value: "yes" },
    }),
    field("c", {
      visible_when: { field_id: "b", op: "eq", value: "value" },
    }),
  ];

  expect(evaluateVisibility(fields, { a: "no", b: "value" })).toEqual({
    a: true,
    b: false,
    c: false,
  });
});

test("test_evaluate_visibility_preserves_authored_field_order", () => {
  // Risk annotation: group=TG-4;
  //   named_risk=spa_wizard_visibility_payload_contract;
  //   level=component;
  //   source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-4
  const fields = [
    field("dependent", {
      visible_when: { field_id: "source", op: "eq", value: "yes" },
    }),
    field("source"),
  ];

  expect(evaluateVisibility(fields, { source: "yes" })).toEqual({
    dependent: false,
    source: true,
  });
});
