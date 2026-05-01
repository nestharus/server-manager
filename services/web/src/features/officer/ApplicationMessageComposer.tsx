import { createSignal, type JSX } from "solid-js";

import {
  ApiError,
  appendOfficerApplicationMessage,
  type ApplicationMessageRead,
  type ApplicationMessageVisibility,
} from "@/api/client";
import { Button } from "@/components/primitives/Button";

import styles from "./officer.module.css";

export type ApplicationMessageComposerProps = {
  readonly applicationId: () => string;
  readonly disabled?: boolean;
  readonly onMessageAppended: (message: ApplicationMessageRead) => Promise<void> | void;
  readonly onError: (notice: string, status?: number) => Promise<void> | void;
};

function newClientMessageId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `message-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function messageErrorNotice(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) return "Forbidden: not allowed to append messages.";
    if (error.status === 404) return "Application not found.";
    if (error.status === 422) return "Invalid message.";
    return `Message append failed (${error.status}).`;
  }
  return "Network error appending message.";
}

export function ApplicationMessageComposer(props: ApplicationMessageComposerProps): JSX.Element {
  const [bodyMarkdown, setBodyMarkdown] = createSignal("");
  const [visibility, setVisibility] =
    createSignal<ApplicationMessageVisibility>("applicant_visible");
  const [clientMessageId, setClientMessageId] = createSignal(newClientMessageId());
  const [submitting, setSubmitting] = createSignal(false);

  const canSend = () => bodyMarkdown().trim().length > 0 && !submitting() && !props.disabled;

  async function submit(event: Event) {
    event.preventDefault();
    if (!canSend()) return;
    setSubmitting(true);
    try {
      const message = await appendOfficerApplicationMessage({
        applicationId: props.applicationId(),
        bodyMarkdown: bodyMarkdown(),
        visibility: visibility(),
        clientMessageId: clientMessageId(),
      });
      setBodyMarkdown("");
      setClientMessageId(newClientMessageId());
      await props.onMessageAppended(message);
    } catch (error) {
      await props.onError(
        messageErrorNotice(error),
        error instanceof ApiError ? error.status : undefined,
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      class={styles.detailCard}
      aria-labelledby="application-message-composer-title"
      data-testid="application-message-composer"
    >
      <h3 id="application-message-composer-title">Message</h3>
      <form class={styles.composerForm} onSubmit={(event) => void submit(event)}>
        <textarea
          aria-label="Append message"
          class={styles.messageTextarea}
          value={bodyMarkdown()}
          disabled={props.disabled || submitting()}
          onInput={(event) => setBodyMarkdown(event.currentTarget.value)}
        />
        <div class={styles.visibilityGroup} role="radiogroup" aria-label="Message visibility">
          <label>
            <input
              type="radio"
              name="application-message-visibility"
              value="applicant_visible"
              checked={visibility() === "applicant_visible"}
              disabled={props.disabled || submitting()}
              onChange={() => setVisibility("applicant_visible")}
            />
            Applicant visible
          </label>
          <label>
            <input
              type="radio"
              name="application-message-visibility"
              value="officer_only"
              checked={visibility() === "officer_only"}
              disabled={props.disabled || submitting()}
              onChange={() => setVisibility("officer_only")}
            />
            Officer only
          </label>
        </div>
        <div class={styles.formActions}>
          <Button type="submit" disabled={!canSend()}>
            Send
          </Button>
        </div>
      </form>
    </section>
  );
}
