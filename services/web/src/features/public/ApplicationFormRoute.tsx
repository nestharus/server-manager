import { createEffect, createMemo, createSignal, on, onCleanup, onMount, Show } from "solid-js";

import {
  ApiError,
  fetchApplicantDiscordIdentity,
  fetchPublicApplicationForm,
  fetchPublicChapters,
  requestPublicApplicationUploadUrl,
  type FormFileResponse,
  type PublicChapterSummary,
  type PublicFormDefinition,
  type PublicFormField,
  submitPublicApplication,
} from "@/api/client";
import { Button } from "@/components/primitives/Button";
import { derivePages, evaluateVisibility, pageVisibleFields } from "./formVisibility";

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

type FileUploadState = "idle" | "uploading" | "uploaded" | "failed";

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
      page: 1,
    },
    {
      id: "application_text",
      type: "long",
      label: "Application text",
      required: true,
      max_length: 4000,
      page: 1,
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

function preserveApplicationDraft(
  form: HTMLFormElement,
  responseValues?: Record<string, unknown>,
) {
  if (responseValues) {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(responseValues));
    return;
  }
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

function readApplicationDraft(): Record<string, unknown> | undefined {
  if (typeof sessionStorage === "undefined") return undefined;
  const raw = sessionStorage.getItem(DRAFT_KEY);
  if (!raw) return undefined;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    sessionStorage.removeItem(DRAFT_KEY);
    return undefined;
  }
}

function restoreApplicationDraft(
  form: HTMLFormElement,
): Record<string, unknown> | undefined {
  const draft = readApplicationDraft();
  if (!draft) return undefined;
  try {
    for (const [key, value] of Object.entries(draft)) {
      const element = form.elements.namedItem(key);
      if (element instanceof HTMLInputElement && element.type === "file") {
        continue;
      }
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
    return draft;
  } catch {
    return undefined;
  }
}

function chapterSelectField(form: PublicFormDefinition): PublicFormField | undefined {
  return form.fields.find((field) => field.type === "chapter_select");
}

function responseValue(field: PublicFormField, formData: FormData): unknown {
  if (field.type === "file") {
    return undefined;
  }
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

function draftResponseValue(
  field: PublicFormField,
  value: unknown,
): unknown {
  if (field.type === "file") {
    return isFormFileResponse(value) ? value : undefined;
  }
  if (field.type === "number") {
    const raw = Array.isArray(value) ? value[0] : value;
    return raw === "" || raw === null ? null : Number(raw);
  }
  if (field.type === "multi_select") {
    return Array.isArray(value) ? value.map(String) : [String(value)];
  }
  if (field.type === "boolean") {
    return value === true || value === "on";
  }
  return Array.isArray(value) ? String(value[0] ?? "") : String(value ?? "");
}

function isFormFileResponse(value: unknown): value is FormFileResponse {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.object_key === "string"
    && typeof candidate.content_type === "string"
    && typeof candidate.size_bytes === "number"
  );
}

function renderFormField(
  field: PublicFormField,
  chapters: readonly PublicChapterSummary[],
  value: unknown,
  uploadState: FileUploadState,
  onFileSelected: (field: PublicFormField, event: Event) => void,
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
          value={value == null ? "" : String(value)}
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
          value={value == null ? "" : String(value)}
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
            <option value="" disabled selected={value == null || value === ""}>
              Select an option
            </option>
          )}
          {field.options.map((option) => (
            <option
              value={option}
              selected={
                Array.isArray(value)
                  ? value.map(String).includes(option)
                  : String(value ?? "") === option
              }
            >
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (field.type === "boolean") {
    return (
      <label class="runtimeField">
        <span>{field.label}</span>
        <input
          name={field.id}
          aria-label={field.label}
          aria-required={field.required ? "true" : undefined}
          required={field.required}
          type="checkbox"
          checked={value === true}
        />
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
        >
          <option value="" disabled selected={value == null || value === ""}>
            {field.placeholder ?? "Choose a chapter"}
          </option>
          {chapters.map((chapter) => (
            <option value={chapter.id} selected={String(value ?? "") === chapter.id}>
              {chapter.name}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (field.type === "file") {
    const uploaded = isFormFileResponse(value);
    return (
      <label class="runtimeField">
        <span>{field.label}</span>
        <input
          class="input"
          name={field.id}
          aria-label={field.label}
          required={field.required && !uploaded}
          type="file"
          accept={field.accept.join(",")}
          disabled={uploadState === "uploading"}
          onChange={(event) => onFileSelected(field, event)}
        />
        <Show when={uploadState !== "idle" || uploaded}>
          <span class="runtimeCopy" aria-live="polite">
            {uploadState === "uploading"
              ? "Uploading..."
              : uploadState === "failed"
                ? "Upload failed."
                : "Uploaded."}
          </span>
        </Show>
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
        value={value == null ? "" : String(value)}
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
  const [currentPageIndex, setCurrentPageIndex] = createSignal(0);
  const [responses, setResponses] = createSignal<Record<string, unknown>>({});
  const [fileUploadStates, setFileUploadStates] = createSignal<Record<string, FileUploadState>>({});
  const visibility = createMemo(() => evaluateVisibility(formDefinition().fields, responses()));
  const visiblePages = createMemo(() => {
    const fields = formDefinition().fields;
    const currentVisibility = visibility();
    const visible = derivePages(fields).filter(
      (page) => pageVisibleFields(fields, page, currentVisibility).length > 0,
    );
    return visible.length > 0 ? visible : derivePages(fields);
  });
  const currentVisibleFields = createMemo(() => {
    const page = visiblePages()[currentPageIndex()] ?? visiblePages()[0] ?? 1;
    return pageVisibleFields(formDefinition().fields, page, visibility());
  });

  function pruneHiddenResponses(
    fields: PublicFormField[],
    values: Record<string, unknown>,
  ): Record<string, unknown> {
    const currentVisibility = evaluateVisibility(fields, values);
    const knownFieldIds = new Set(fields.map((field) => field.id));
    return Object.fromEntries(
      Object.entries(values).filter(
        ([fieldId]) => knownFieldIds.has(fieldId) && currentVisibility[fieldId],
      ),
    );
  }

  function setResponseValue(field: PublicFormField, value: unknown) {
    setResponses((current) =>
      pruneHiddenResponses(formDefinition().fields, { ...current, [field.id]: value }),
    );
  }

  function setFileUploadState(fieldId: string, state: FileUploadState) {
    setFileUploadStates((current) => ({ ...current, [fieldId]: state }));
  }

  function applyResponsesToForm(values: Record<string, unknown>) {
    if (!formRef) return;
    for (const field of currentVisibleFields()) {
      const element = formRef.elements.namedItem(field.id);
      if (element instanceof HTMLSelectElement && element.multiple) {
        const value = values[field.id];
        const selectedValues = new Set(
          Array.isArray(value) ? value.map(String) : [],
        );
        for (const option of element.options) {
          option.selected = selectedValues.has(option.value);
        }
      } else if (element instanceof HTMLInputElement && element.type === "checkbox") {
        element.checked = values[field.id] === true;
      } else if (
        element instanceof HTMLInputElement
        || element instanceof HTMLTextAreaElement
        || element instanceof HTMLSelectElement
      ) {
        element.value = values[field.id] == null ? "" : String(values[field.id]);
      }
    }
  }

  function onFormInput(event: Event) {
    if (!formRef) return;
    const target = event.target;
    if (
      !(target instanceof HTMLInputElement)
      && !(target instanceof HTMLTextAreaElement)
      && !(target instanceof HTMLSelectElement)
    ) {
      return;
    }
    if (!target.name) return;
    if (target instanceof HTMLInputElement && target.type === "file") return;
    const field = formDefinition().fields.find((candidate) => candidate.id === target.name);
    if (!field) return;
    setResponseValue(field, responseValue(field, new FormData(formRef)));
  }

  async function onFileSelected(field: PublicFormField, event: Event) {
    if (field.type !== "file") return;
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement)) return;
    const file = target.files?.[0];
    setResponses((current) => {
      const next = { ...current };
      delete next[field.id];
      return pruneHiddenResponses(formDefinition().fields, next);
    });
    if (!file) {
      setFileUploadState(field.id, "idle");
      return;
    }
    if (!field.accept.includes(file.type) || file.size > field.max_size_bytes) {
      target.value = "";
      setFileUploadState(field.id, "failed");
      return;
    }
    setFileUploadState(field.id, "uploading");
    try {
      const upload = await requestPublicApplicationUploadUrl({
        form_definition_id: formDefinition().id,
        field_id: field.id,
        content_type: file.type,
        size_bytes: file.size,
      });
      const putResponse = await fetch(upload.upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file,
      });
      if (!putResponse.ok) {
        throw new Error(`upload failed with ${putResponse.status}`);
      }
      setResponseValue(field, {
        object_key: upload.object_key,
        content_type: file.type,
        size_bytes: file.size,
      });
      setFileUploadState(field.id, "uploaded");
    } catch (error) {
      console.error("[ApplicationFormRoute] File upload failed", error);
      target.value = "";
      setFileUploadState(field.id, "failed");
    }
  }

  function goNext() {
    if (!formRef?.reportValidity()) return;
    setCurrentPageIndex((index) => Math.min(index + 1, visiblePages().length - 1));
  }

  function goPrevious() {
    setCurrentPageIndex((index) => Math.max(index - 1, 0));
  }

  function responseForField(field: PublicFormField) {
    const current = responses()[field.id];
    if (current !== undefined) return current;
    const draft = readApplicationDraft();
    if (draft && Object.prototype.hasOwnProperty.call(draft, field.id)) {
      return draftResponseValue(field, draft[field.id]);
    }
    return undefined;
  }

  function responsesWithDraftDefaults(form: PublicFormDefinition) {
    const draft = readApplicationDraft();
    if (!draft) return responses();
    const draftResponses = Object.fromEntries(
      form.fields
        .filter((field) => Object.prototype.hasOwnProperty.call(draft, field.id))
        .map((field) => [field.id, draftResponseValue(field, draft[field.id])]),
    );
    return { ...draftResponses, ...responses() };
  }

  async function refreshPublicFormDefinition() {
    let loadedForm: PublicFormDefinition;
    try {
      loadedForm = await fetchPublicApplicationForm();
    } catch (error) {
      console.error("[ApplicationFormRoute] Public form fetch failed", error);
      loadedForm = FALLBACK_FORM;
    }
    setFormDefinition(loadedForm);
    const draft = readApplicationDraft();
    if (draft) {
      const nextResponses = Object.fromEntries(
        loadedForm.fields
          .filter((field) => Object.prototype.hasOwnProperty.call(draft, field.id))
          .map((field) => [field.id, draftResponseValue(field, draft[field.id])]),
      );
      setResponses(pruneHiddenResponses(loadedForm.fields, nextResponses));
    }
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
      preserveApplicationDraft(formRef, responses());
      redirectToDiscordAuth();
      return;
    }
    if (!identity.discord_user_id) {
      preserveApplicationDraft(formRef, responses());
      redirectToDiscordAuth();
      return;
    }

    const form = formDefinition();
    const visibleResponses = pruneHiddenResponses(form.fields, responsesWithDraftDefaults(form));
    const pendingFileField = form.fields.find(
      (field) =>
        field.type === "file"
        && visibility()[field.id]
        && fileUploadStates()[field.id] === "uploading",
    );
    if (pendingFileField) {
      setSubmitStatus("File upload still in progress. Please try again.");
      return;
    }
    const chapterField = chapterSelectField(form);
    const selectedChapterId = chapterField
      ? String(visibleResponses[chapterField.id] ?? "")
      : "";
    const payload: FormPayload = {
      scope: {
        scope_kind: chapterField ? "chapter" : "global",
        scope_id: chapterField ? selectedChapterId : null,
      },
      responses: visibleResponses,
      client_application_id: getClientApplicationId(),
    };
    let submission: Awaited<ReturnType<typeof submitPublicApplication>>;
    try {
      submission = await submitPublicApplication(payload);
    } catch {
      preserveApplicationDraft(formRef, responses());
      setSubmitStatus("Network error. Please try again.");
      return;
    }
    if (submission.status === 401) {
      preserveApplicationDraft(formRef, responses());
      redirectToDiscordAuth();
      return;
    }
    const submitMessage = submission.body.message ?? `Application returned ${submission.status}`;
    const applicationId = submission.body.application_id;
    setSubmitStatus(applicationId ? `${submitMessage}\nReference: ${applicationId}` : submitMessage);
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
        const draft = restoreApplicationDraft(formRef);
        if (draft) {
          const nextResponses = Object.fromEntries(
            formDefinition().fields
              .filter((field) => Object.prototype.hasOwnProperty.call(draft, field.id))
              .map((field) => [field.id, draftResponseValue(field, draft[field.id])]),
          );
          setResponses(pruneHiddenResponses(formDefinition().fields, nextResponses));
        }
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

  createEffect(
    on(
      () => formDefinition().id,
      () => {
        setCurrentPageIndex(0);
        const draft = readApplicationDraft();
        if (draft) {
          const nextResponses = Object.fromEntries(
            formDefinition().fields
              .filter((field) => Object.prototype.hasOwnProperty.call(draft, field.id))
              .map((field) => [field.id, draftResponseValue(field, draft[field.id])]),
          );
          setResponses(pruneHiddenResponses(formDefinition().fields, nextResponses));
        }
        if (authState().status === "verified") scheduleDraftRestore();
      },
    ),
  );

  createEffect(() => {
    const pages = visiblePages();
    if (currentPageIndex() >= pages.length) {
      setCurrentPageIndex(Math.max(pages.length - 1, 0));
    }
  });

  createEffect(() => {
    responses();
    currentVisibleFields();
    queueMicrotask(() => applyResponsesToForm(responses()));
  });

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
            onInput={onFormInput}
            onChange={onFormInput}
          >
            <p class="runtimeCopy">
              Step {currentPageIndex() + 1} of {visiblePages().length}
            </p>
            {currentVisibleFields().map((field) =>
              renderFormField(
                field,
                publicChapters(),
                responseForField(field),
                fileUploadStates()[field.id] ?? "idle",
                onFileSelected,
              ),
            )}
            <div class="runtimeActions">
              <Show when={currentPageIndex() > 0}>
                <Button type="button" variant="secondary" onClick={goPrevious}>
                  Previous
                </Button>
              </Show>
              <Show
                when={currentPageIndex() === visiblePages().length - 1}
                fallback={
                  <Button type="button" onClick={goNext}>
                    Next
                  </Button>
                }
              >
                <Button type="submit">
                  <span data-testid="application-submit-icon" aria-hidden="true">
                    +
                  </span>
                  Submit application
                </Button>
              </Show>
            </div>
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
