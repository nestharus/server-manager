import { createForm } from "@tanstack/solid-form";
import { For, Show } from "solid-js";

import { Toolbar } from "@/components/gap/Toolbar";
import { ArkSelect } from "@/components/primitives/ArkSelect";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import {
  createResponseSchema,
  darkNemesisForm,
  defaultResponses,
  type FormQuestion,
} from "./schema";

import styles from "./form.module.css";

function QuestionControl(props: {
  readonly question: FormQuestion;
  readonly value: unknown;
  readonly onChange: (value: unknown) => void;
}) {
  const question = () => props.question;
  const options = () =>
    question().options?.map((option) => ({ label: option, value: option })) ?? [];

  return (
    <label class={styles.question}>
      <span>
        {question().label}
        <Show when={question().required}>
          <strong aria-label="required"> *</strong>
        </Show>
      </span>
      <Show
        when={question().type === "select"}
        fallback={
          <Show
            when={question().type === "long"}
            fallback={
              <Show
                when={question().type === "multi_select"}
                fallback={
                  <Input
                    type={question().type === "number" ? "number" : "text"}
                    maxlength={question().max_length}
                    value={String(props.value ?? "")}
                    required={question().required}
                    onInput={(event) => props.onChange(event.currentTarget.value)}
                  />
                }
              >
                <select
                  multiple
                  required={question().required}
                  onChange={(event) =>
                    props.onChange(
                      Array.from(event.currentTarget.selectedOptions).map((option) => option.value),
                    )
                  }
                >
                  <For each={question().options ?? []}>
                    {(option) => <option value={option()}>{option()}</option>}
                  </For>
                </select>
              </Show>
            }
          >
            <textarea
              maxlength={question().max_length}
              required={question().required}
              value={String(props.value ?? "")}
              onInput={(event) => props.onChange(event.currentTarget.value)}
            />
          </Show>
        }
      >
        <ArkSelect
          label={question().label}
          options={options()}
          value={String(props.value ?? "")}
          onChange={props.onChange}
        />
      </Show>
    </label>
  );
}

export function DarkNemesisForm(props: { readonly onSubmitPreview: (value: string) => void }) {
  const responseSchema = createResponseSchema(darkNemesisForm);
  const form = createForm(() => ({
    defaultValues: defaultResponses(darkNemesisForm),
    validators: {
      onSubmit: responseSchema,
    },
    onSubmit: ({ value }) => {
      props.onSubmitPreview(JSON.stringify(value, null, 2));
    },
  }));

  return (
    <form
      class={styles.form}
      aria-label={darkNemesisForm.title}
      onSubmit={(event) => {
        event.preventDefault();
        event.stopPropagation();
        void form.handleSubmit();
      }}
    >
      <div class={styles.formHeader}>
        <h3>{darkNemesisForm.title}</h3>
        <Toolbar
          label="Form actions"
          actions={[
            {
              id: "draft",
              label: "Draft",
              onPress: () => props.onSubmitPreview("Draft saved locally."),
            },
            { id: "reset", label: "Reset", onPress: () => form.reset() },
          ]}
        />
      </div>
      <For each={darkNemesisForm.questions}>
        {(question) => (
          <form.Field name={question().id}>
            {(field) => (
              <QuestionControl
                question={question()}
                value={field().state.value}
                onChange={(value) => field().handleChange(value)}
              />
            )}
          </form.Field>
        )}
      </For>
      <Button type="submit">Preview submission</Button>
    </form>
  );
}
