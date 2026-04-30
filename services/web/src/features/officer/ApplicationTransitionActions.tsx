import { For, Show, createSignal, type JSX } from "solid-js";

import {
  ApiError,
  transitionOfficerApplication,
  type ApplicationRead,
  type ApplicationTransitionRequest,
} from "@/api/client";
import { Button } from "@/components/primitives/Button";

import {
  transitionActionInput,
  validOfficerTransitionActions,
  type OfficerTransitionAction,
} from "./applicationStateMachine";
import styles from "./officer.module.css";

export type ApplicationTransitionActionsProps = {
  readonly application: ApplicationRead;
  readonly disabled?: boolean;
  readonly onTransitioned: (application: ApplicationRead) => Promise<void> | void;
  readonly onError: (notice: string, status?: number) => Promise<void> | void;
};

function actionLabel(action: OfficerTransitionAction) {
  return action.replaceAll("_", " ");
}

function transitionErrorNotice(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) return "Forbidden: not allowed to perform this action.";
    if (error.status === 409) return "Transition conflict: invalid application transition.";
    if (error.status === 412) return "Stale version. Refreshing application detail.";
    if (error.status === 428) return "Precondition required. Refreshing application detail.";
    if (error.status === 404) return "Application not found.";
    if (error.status === 422) return "Invalid transition request.";
    return `Transition failed (${error.status}).`;
  }
  return "Network error performing transition.";
}

export function ApplicationTransitionActions(
  props: ApplicationTransitionActionsProps,
): JSX.Element {
  const [activeAction, setActiveAction] = createSignal<OfficerTransitionAction | null>(null);
  const [fieldValue, setFieldValue] = createSignal("");
  const [submitting, setSubmitting] = createSignal(false);
  const [forbiddenActions, setForbiddenActions] = createSignal<ReadonlySet<string>>(new Set());

  const activeInput = () => {
    const action = activeAction();
    return action === null ? null : transitionActionInput(action);
  };
  const canConfirm = () => {
    const input = activeInput();
    return !submitting() && !props.disabled && (!input?.required || fieldValue().trim().length > 0);
  };

  function selectAction(action: OfficerTransitionAction) {
    setActiveAction(action);
    setFieldValue("");
  }

  function buildRequest(action: OfficerTransitionAction): ApplicationTransitionRequest {
    const input = transitionActionInput(action);
    const request: ApplicationTransitionRequest = { action };
    const value = fieldValue().trim();
    if (input.field !== null && value) {
      request[input.field] = value;
    }
    return request;
  }

  async function submit(event: Event) {
    event.preventDefault();
    const action = activeAction();
    if (action === null || !canConfirm()) return;
    setSubmitting(true);
    try {
      const nextApplication = await transitionOfficerApplication({
        applicationId: props.application.id,
        expectedVersion: props.application.version,
        request: buildRequest(action),
      });
      setActiveAction(null);
      setFieldValue("");
      await props.onTransitioned(nextApplication);
    } catch (error) {
      const status = error instanceof ApiError ? error.status : undefined;
      if (status === 403) {
        setForbiddenActions((current) => new Set([...current, action]));
      }
      await props.onError(transitionErrorNotice(error), status);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section class={styles.detailCard} aria-labelledby="application-transition-actions-title">
      <h3 id="application-transition-actions-title">Actions</h3>
      <div class={styles.transitionButtonGroup}>
        <For each={validOfficerTransitionActions(props.application.state)}>
          {(action) => (
            <Button
              type="button"
              variant={activeAction() === action() ? "primary" : "secondary"}
              data-testid={`application-transition-action-${action()}`}
              disabled={
                props.disabled ||
                submitting() ||
                forbiddenActions().has(action())
              }
              onClick={() => selectAction(action())}
            >
              {actionLabel(action())}
            </Button>
          )}
        </For>
      </div>
      <Show when={activeAction()}>
        {(action) => {
          return (
            <form class={styles.transitionForm} onSubmit={(event) => void submit(event)}>
              <Show when={activeInput()?.field}>
                <label class={styles.fieldLabel}>
                  <span>{activeInput()?.label}</span>
                  <textarea
                    aria-label={activeInput()?.label}
                    class={styles.messageTextarea}
                    value={fieldValue()}
                    disabled={props.disabled || submitting()}
                    onInput={(event) => setFieldValue(event.currentTarget.value)}
                  />
                </label>
              </Show>
              <div class={styles.formActions}>
                <Button type="submit" disabled={!canConfirm()}>
                  Confirm {actionLabel(action())}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={submitting()}
                  onClick={() => setActiveAction(null)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          );
        }}
      </Show>
    </section>
  );
}
