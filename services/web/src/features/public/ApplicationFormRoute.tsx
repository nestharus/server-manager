import { createEffect, createSignal, on, onCleanup, onMount, Show } from "solid-js";

import {
  ApiError,
  fetchApplicantDiscordIdentity,
  submitPublicApplication,
} from "@/api/client";
import { Button } from "@/components/primitives/Button";

type FormPayload = {
  scope: {
    scope_kind: "global";
    scope_id: null;
  };
  responses: {
    character_name: string;
    application_text: string;
  };
  client_application_id: string;
};

type ApplicantAuthState =
  | { status: "checking" }
  | { status: "anonymous" }
  | { status: "verified"; discord_user_id: string };

const CLIENT_APPLICATION_ID_KEY = "humility.publicApplication.clientApplicationId";
const DRAFT_KEY = "humility.publicApplication.draft";
const FOCUSABLE_DIALOG_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "textarea:not([disabled])",
  "select:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function getClientApplicationId() {
  const existing = sessionStorage.getItem(CLIENT_APPLICATION_ID_KEY);
  if (existing) return existing;
  const generated = crypto.randomUUID();
  sessionStorage.setItem(CLIENT_APPLICATION_ID_KEY, generated);
  return generated;
}

function redirectToDiscordAuth() {
  window.location.assign("/auth/discord/start?return_to=/applications");
}

function preserveApplicationDraft(form: HTMLFormElement) {
  const formData = new FormData(form);
  sessionStorage.setItem(
    DRAFT_KEY,
    JSON.stringify({
      character_name: String(formData.get("character_name") ?? ""),
      application_text: String(formData.get("application_text") ?? ""),
    }),
  );
}

function restoreApplicationDraft(form: HTMLFormElement) {
  const raw = sessionStorage.getItem(DRAFT_KEY);
  if (!raw) return;
  try {
    const draft = JSON.parse(raw) as Partial<FormPayload["responses"]>;
    const characterName = form.elements.namedItem("character_name");
    const applicationText = form.elements.namedItem("application_text");
    if (characterName instanceof HTMLInputElement && draft.character_name) {
      characterName.value = draft.character_name;
    }
    if (applicationText instanceof HTMLTextAreaElement && draft.application_text) {
      applicationText.value = draft.application_text;
    }
  } catch {
    sessionStorage.removeItem(DRAFT_KEY);
  }
}

export function ApplicationFormRoute() {
  let formRef: HTMLFormElement | undefined;
  let dialogRef: HTMLDivElement | undefined;
  let previouslyFocusedElement: HTMLElement | undefined;
  let dialogFocusFrame: number | undefined;
  let receiptTimer: number | undefined;
  let draftRestoreFrame: number | undefined;
  const [authState, setAuthState] = createSignal<ApplicantAuthState>({ status: "checking" });
  const [activeTab, setActiveTab] = createSignal<"overview" | "details">("overview");
  const [dialogOpen, setDialogOpen] = createSignal(false);
  const [submitStatus, setSubmitStatus] = createSignal("No application submitted yet.");

  async function refreshApplicantDiscordState() {
    try {
      const identity = await fetchApplicantDiscordIdentity();
      setAuthState({
        status: "verified",
        discord_user_id: identity.discord_user_id,
      });
      if (receiptTimer !== undefined) window.clearTimeout(receiptTimer);
      receiptTimer = window.setTimeout(() => {
        setAuthState({ status: "checking" });
        void refreshApplicantDiscordState();
      }, 9 * 60 * 1000);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setAuthState({ status: "anonymous" });
        return;
      }
      console.error("[ApplicationFormRoute] Discord identity fetch failed", error);
      setAuthState({ status: "anonymous" });
    }
  }

  function dialogFocusableElements() {
    return Array.from(dialogRef?.querySelectorAll<HTMLElement>(FOCUSABLE_DIALOG_SELECTOR) ?? [])
      .filter((element) => !element.hasAttribute("disabled") && element.tabIndex >= 0);
  }

  function focusFirstDialogElement() {
    const [firstElement] = dialogFocusableElements();
    (firstElement ?? dialogRef)?.focus();
  }

  function closeDialog() {
    setDialogOpen(false);
  }

  function onDialogKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog();
      return;
    }
    if (event.key !== "Tab") return;

    const focusableElements = dialogFocusableElements();
    if (focusableElements.length === 0) {
      event.preventDefault();
      dialogRef?.focus();
      return;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    if (event.shiftKey && document.activeElement === firstElement) {
      event.preventDefault();
      lastElement.focus();
      return;
    }
    if (!event.shiftKey && document.activeElement === lastElement) {
      event.preventDefault();
      firstElement.focus();
    }
  }

  async function onSubmit(event: SubmitEvent) {
    event.preventDefault();
    if (!formRef) return;
    let identity: { discord_user_id: string };
    try {
      identity = await fetchApplicantDiscordIdentity();
    } catch {
      preserveApplicationDraft(formRef);
      redirectToDiscordAuth();
      return;
    }
    if (!identity.discord_user_id) {
      preserveApplicationDraft(formRef);
      redirectToDiscordAuth();
      return;
    }

    const formData = new FormData(formRef);
    const payload: FormPayload = {
      scope: {
        scope_kind: "global",
        scope_id: null,
      },
      responses: {
        character_name: String(formData.get("character_name") ?? ""),
        application_text: String(formData.get("application_text") ?? ""),
      },
      client_application_id: getClientApplicationId(),
    };
    let submission: Awaited<ReturnType<typeof submitPublicApplication>>;
    try {
      submission = await submitPublicApplication(payload);
    } catch {
      preserveApplicationDraft(formRef);
      setSubmitStatus("Network error. Please try again.");
      return;
    }
    if (submission.status === 401) {
      preserveApplicationDraft(formRef);
      redirectToDiscordAuth();
      return;
    }
    setSubmitStatus(submission.body.message ?? `Application returned ${submission.status}`);
  }

  onMount(() => {
    void refreshApplicantDiscordState();
  });

  onCleanup(() => {
    if (receiptTimer !== undefined) window.clearTimeout(receiptTimer);
    if (draftRestoreFrame !== undefined) window.cancelAnimationFrame(draftRestoreFrame);
    if (dialogFocusFrame !== undefined) window.cancelAnimationFrame(dialogFocusFrame);
  });

  function scheduleDraftRestore(retries = 10) {
    if (draftRestoreFrame !== undefined) window.cancelAnimationFrame(draftRestoreFrame);
    draftRestoreFrame = window.requestAnimationFrame(() => {
      draftRestoreFrame = undefined;
      if (formRef) {
        restoreApplicationDraft(formRef);
        return;
      }
      if (retries > 0) scheduleDraftRestore(retries - 1);
    });
  }

  createEffect(
    on(
      () => authState().status,
      (status) => {
        if (status === "verified") {
          scheduleDraftRestore();
        }
      },
    ),
  );

  createEffect(() => {
    if (!dialogOpen()) {
      if (dialogFocusFrame !== undefined) {
        window.cancelAnimationFrame(dialogFocusFrame);
        dialogFocusFrame = undefined;
      }
      previouslyFocusedElement?.focus();
      previouslyFocusedElement = undefined;
      return;
    }

    previouslyFocusedElement = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : undefined;
    dialogFocusFrame = window.requestAnimationFrame(() => {
      dialogFocusFrame = undefined;
      focusFirstDialogElement();
    });
  });

  const loginState = () => {
    const state = authState();
    if (state.status === "checking") return "Checking Discord login...";
    if (state.status === "verified") return `Logged in as Discord ${state.discord_user_id}`;
    return "Not logged in with Discord.";
  };

  return (
    <Show
      when={authState().status === "verified"}
      fallback={
        <section class="runtimePanel">
          <div class="runtimeStack" aria-live="polite">
            <Button id="discord-login" type="button" onClick={redirectToDiscordAuth}>
              Login with Discord
            </Button>
            <p class="runtimeCopy" aria-live="polite">
              {loginState()}
            </p>
          </div>
        </section>
      }
    >
      <div class="runtimeGrid">
        <section class="runtimePanel">
          <p class="eyebrow">Application intake</p>
          <h2>Humility applications</h2>
          <div role="tablist" class="runtimeTabs">
            <button
              id="tab-overview"
              role="tab"
              aria-selected={activeTab() === "overview" ? "true" : "false"}
              type="button"
              onClick={() => setActiveTab("overview")}
            >
              Overview
            </button>
            <button
              id="tab-details"
              role="tab"
              aria-selected={activeTab() === "details" ? "true" : "false"}
              type="button"
              onClick={() => setActiveTab("details")}
            >
              Details
            </button>
          </div>
          <form
            id="application-form"
            ref={(element) => {
              formRef = element;
            }}
            class="runtimeStack"
            aria-label="Application form"
            onSubmit={onSubmit}
          >
            <label class="runtimeField">
              <span>Character name</span>
              <input class="input" name="character_name" aria-label="Character name" required />
            </label>
            <label class="runtimeField">
              <span>Application text</span>
              <textarea
                class="input"
                name="application_text"
                aria-label="Application text"
                required
              />
            </label>
            <Button type="submit">
              <span data-testid="application-submit-icon" aria-hidden="true">
                +
              </span>
              Submit application
            </Button>
          </form>
          <p id="discord-login-state" class="runtimeCopy" aria-live="polite">
            {loginState()}
          </p>
          <div id="details-panel" class="runtimeStack" hidden={activeTab() !== "details"}>
            <span data-testid="application-status-icon" aria-hidden="true">
              i
            </span>
            <Button id="open-details" type="button" variant="secondary" onClick={() => setDialogOpen(true)}>
              Open details
            </Button>
            <Show when={dialogOpen()}>
              <div class="runtimeDialogOverlay" aria-hidden="true" onClick={closeDialog} />
              <div
                ref={(element) => {
                  dialogRef = element;
                }}
                role="dialog"
                aria-modal="true"
                aria-labelledby="application-details-dialog-title"
                class="runtimeDialog"
                tabindex={-1}
                onKeyDown={onDialogKeyDown}
              >
                <div class="runtimeDialogHeader">
                  <h3 id="application-details-dialog-title">Application details</h3>
                  <Button type="button" variant="secondary" onClick={closeDialog}>
                    Close
                  </Button>
                </div>
              </div>
            </Show>
          </div>
        </section>
        <aside class="runtimePanel" aria-live="polite">
          <h2>Submission status</h2>
          <pre id="submit-status">{submitStatus()}</pre>
        </aside>
      </div>
    </Show>
  );
}
