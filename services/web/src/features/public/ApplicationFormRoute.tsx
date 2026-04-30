import { createEffect, createSignal, on, onCleanup, onMount, Show } from "solid-js";

import {
  ApiError,
  fetchApplicantDiscordIdentity,
  fetchPublicApplicationForm,
  fetchPublicChapters,
  type PublicChapterSummary,
  type PublicFormDefinition,
  type PublicFormField,
  submitPublicApplication,
} from "@/api/client";
import { Button } from "@/components/primitives/Button";

type FormPayload = {
  scope: {
    scope_kind: "global" | "chapter";
    scope_id: string | null;
  };
  responses: Record<string, unknown>;
  client_application_id: string;
};

type ApplicantAuthState =
  | { status: "checking" }
  | { status: "anonymous" }
  | { status: "verified"; discord_user_id: string };

const CLIENT_APPLICATION_ID_KEY = "humility.publicApplication.clientApplicationId";
const DRAFT_KEY = "humility.publicApplication.draft";
const FALLBACK_FORM: PublicFormDefinition = {
  id: "fallback-public-application",
  name: "Public Application",
  target_type: "chapter_membership",
  scope: { scope_kind: "global", scope_id: null },
  fields: [
    {
      id: "character_name",
      type: "short",
      label: "Character name",
      required: true,
      max_length: 64,
    },
    {
      id: "application_text",
      type: "long",
      label: "Application text",
      required: true,
      max_length: 4000,
    },
  ],
  routing_rules: {},
  version: 1,
  status: "current",
  published_at: new Date(0).toISOString(),
  archived_at: null,
  created_at: new Date(0).toISOString(),
};
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
  const draft: Record<string, FormDataEntryValue | FormDataEntryValue[]> = {};
  for (const [key, value] of formData.entries()) {
    if (key in draft) {
      const existing = draft[key];
      draft[key] = Array.isArray(existing) ? [...existing, value] : [existing, value];
    } else {
      draft[key] = value;
    }
  }
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
}

function restoreApplicationDraft(form: HTMLFormElement) {
  const raw = sessionStorage.getItem(DRAFT_KEY);
  if (!raw) return;
  try {
    const draft = JSON.parse(raw) as Record<string, string | string[]>;
    for (const [key, value] of Object.entries(draft)) {
      const element = form.elements.namedItem(key);
      if (element instanceof HTMLSelectElement && element.multiple && Array.isArray(value)) {
        const values = new Set(value.map(String));
        for (const option of element.options) {
          option.selected = values.has(option.value);
        }
        continue;
      }
      if (
        element instanceof HTMLInputElement ||
        element instanceof HTMLTextAreaElement ||
        element instanceof HTMLSelectElement
      ) {
        element.value = Array.isArray(value) ? String(value[0] ?? "") : String(value);
      }
    }
  } catch {
    sessionStorage.removeItem(DRAFT_KEY);
  }
}

function chapterSelectField(form: PublicFormDefinition): PublicFormField | undefined {
  return form.fields.find((field) => field.type === "chapter_select");
}

function responseValue(field: PublicFormField, formData: FormData): unknown {
  if (field.type === "number") {
    const raw = String(formData.get(field.id) ?? "");
    return raw === "" ? null : Number(raw);
  }
  if (field.type === "multi_select") {
    return formData.getAll(field.id).map((value) => String(value));
  }
  if (field.type === "boolean") {
    return formData.get(field.id) === "on";
  }
  return String(formData.get(field.id) ?? "");
}

function renderFormField(
  field: PublicFormField,
  chapters: readonly PublicChapterSummary[],
) {
  if (field.type === "long") {
    return (
      <label class="runtimeField">
        <span>{field.label}</span>
        <textarea
          class="input"
          name={field.id}
          aria-label={field.label}
          required={field.required}
          maxlength={field.max_length ?? undefined}
        />
      </label>
    );
  }
  if (field.type === "number") {
    return (
      <label class="runtimeField">
        <span>{field.label}</span>
        <input
          class="input"
          name={field.id}
          aria-label={field.label}
          required={field.required}
          type="number"
        />
      </label>
    );
  }
  if (field.type === "select" || field.type === "multi_select") {
    return (
      <label class="runtimeField">
        <span>{field.label}</span>
        <select
          class="input"
          name={field.id}
          aria-label={field.label}
          required={field.required}
          multiple={field.type === "multi_select"}
        >
          {field.required && field.type === "select" && (
            <option value="" disabled>
              Select an option
            </option>
          )}
          {field.options.map((option) => (
            <option value={option}>{option}</option>
          ))}
        </select>
      </label>
    );
  }
  if (field.type === "boolean") {
    return (
      <label class="runtimeField">
        <span>{field.label}</span>
        <input name={field.id} aria-label={field.label} type="checkbox" />
      </label>
    );
  }
  if (field.type === "chapter_select") {
    return (
      <label class="runtimeField">
        <span>{field.label}</span>
        <select
          class="input"
          name={field.id}
          aria-label={field.label}
          required
          value=""
        >
          <option value="" disabled>
            {field.placeholder ?? "Choose a chapter"}
          </option>
          {chapters.map((chapter) => (
            <option value={chapter.id}>{chapter.name}</option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label class="runtimeField">
      <span>{field.label}</span>
      <input
        class="input"
        name={field.id}
        aria-label={field.label}
        required={field.required}
        maxlength={field.max_length ?? undefined}
      />
    </label>
  );
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
  const [formDefinition, setFormDefinition] = createSignal<PublicFormDefinition>(FALLBACK_FORM);
  const [publicChapters, setPublicChapters] = createSignal<readonly PublicChapterSummary[]>([]);

  async function refreshPublicFormDefinition() {
    let loadedForm: PublicFormDefinition;
    try {
      loadedForm = await fetchPublicApplicationForm();
    } catch (error) {
      console.error("[ApplicationFormRoute] Public form fetch failed", error);
      loadedForm = FALLBACK_FORM;
    }
    setFormDefinition(loadedForm);
    if (!chapterSelectField(loadedForm)) {
      setPublicChapters([]);
      return;
    }
    try {
      setPublicChapters(await fetchPublicChapters());
    } catch (error) {
      console.error("[ApplicationFormRoute] Public chapters fetch failed", error);
      setPublicChapters([]);
    }
  }

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

    const form = formDefinition();
    const formData = new FormData(formRef);
    const responses = Object.fromEntries(
      form.fields.map((field) => [field.id, responseValue(field, formData)]),
    );
    const chapterField = chapterSelectField(form);
    const selectedChapterId = chapterField
      ? String(responses[chapterField.id] ?? "")
      : "";
    const payload: FormPayload = {
      scope: {
        scope_kind: chapterField ? "chapter" : "global",
        scope_id: chapterField ? selectedChapterId : null,
      },
      responses,
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
    void refreshPublicFormDefinition();
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
            {formDefinition().fields.map((field) => renderFormField(field, publicChapters()))}
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
