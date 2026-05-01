import { Link, useParams } from "@tanstack/solid-router";
import { For, Show, createSignal, onMount, type JSX } from "solid-js";

import {
  ApiError,
  fetchCurrentPrincipal,
  fetchOfficerApplication,
  fetchOfficerApplicationTranscript,
  type ApplicationMessageRead,
  type ApplicationRead,
  type ApplicationTranscriptEntry,
  type ApplicationTranscriptRead,
  type CurrentPrincipal,
} from "@/api/client";
import { Button } from "@/components/primitives/Button";

import { ApplicationMessageComposer } from "./ApplicationMessageComposer";
import { ApplicationTransitionActions } from "./ApplicationTransitionActions";
import styles from "./officer.module.css";

export type ApplicationMetadataPanelProps = {
  readonly application: () => ApplicationRead;
};

export type ApplicationResponsesPanelProps = {
  readonly application: () => ApplicationRead;
};

export type ApplicationTranscriptListProps = {
  readonly entries: () => ApplicationTranscriptRead["entries"];
};

type DetailLayoutProps = {
  readonly read: () => ApplicationRead;
  readonly readTranscript: () => ApplicationTranscriptRead;
  readonly loading: () => boolean;
  readonly onMessageAppended: (message: ApplicationMessageRead) => Promise<void> | void;
  readonly onTransitioned: (application: ApplicationRead) => Promise<void> | void;
  readonly onError: (notice: string, status?: number) => Promise<void> | void;
};

function shortId(value: string | null) {
  return value === null ? "" : value.slice(0, 8);
}

function formatTimestamp(value: string | null) {
  if (value === null || value === "") return "Not set";
  return new Date(value).toLocaleString();
}

function renderValue(value: unknown) {
  if (value === null) return "null";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function detailNotice(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Application not found.";
    if (error.status === 403) return "Forbidden: not allowed to read this application.";
    if (error.status === 422) return "Invalid application id.";
    return `Application detail failed (${error.status}).`;
  }
  return "Network error loading application detail.";
}

function transcriptTransition(
  entry: Extract<ApplicationTranscriptEntry, { type: "state_change" }>,
) {
  return `${entry.from_state ?? "none"} -> ${entry.to_state ?? "none"}`;
}

function TranscriptEntryView(props: { readonly entry: ApplicationTranscriptEntry }): JSX.Element {
  return (
    <li
      class={
        props.entry.type === "state_change"
          ? styles.transcriptStateChange
          : styles.transcriptMessage
      }
      data-entry-type={props.entry.type}
      data-to-state={props.entry.type === "state_change" ? (props.entry.to_state ?? "") : undefined}
    >
      <Show
        when={props.entry.type === "state_change"}
        fallback={
          <div class={styles.transcriptEntryBody}>
            <div class={styles.transcriptMeta}>
              <span>{formatTimestamp(props.entry.occurred_at)}</span>
              <span>{props.entry.type === "message" ? props.entry.visibility : ""}</span>
              <span>
                {props.entry.type === "message" ? props.entry.author_actor_kind : ""}{" "}
                {props.entry.type === "message" ? shortId(props.entry.author_actor_id) : ""}
              </span>
            </div>
            <p class={styles.transcriptMessageBody}>
              {props.entry.type === "message" ? props.entry.body_markdown : ""}
            </p>
          </div>
        }
      >
        <div class={styles.transcriptEntryBody}>
          <div class={styles.transcriptMeta}>
            <span>{formatTimestamp(props.entry.occurred_at)}</span>
            <span>{props.entry.type === "state_change" ? props.entry.change_type : ""}</span>
            <span>
              {props.entry.type === "state_change" ? props.entry.actor_kind : ""}{" "}
              {props.entry.type === "state_change" ? shortId(props.entry.actor_id) : ""}
            </span>
          </div>
          <p class={styles.transcriptTransition}>
            {props.entry.type === "state_change" ? transcriptTransition(props.entry) : ""}
          </p>
        </div>
      </Show>
    </li>
  );
}

export function ApplicationMetadataPanel(props: ApplicationMetadataPanelProps): JSX.Element {
  const rows = () => [
    ["State", props.application().state],
    ["Owner", shortId(props.application().owner_id)],
    ["Applicant", shortId(props.application().applicant_id)],
    [
      "Scope",
      `${props.application().target_scope.scope_kind}:${props.application().target_scope.scope_id ?? "global"}`,
    ],
    ["Submitted", formatTimestamp(props.application().submitted_at)],
    ["Queued", formatTimestamp(props.application().queued_at)],
    ["Claimed", formatTimestamp(props.application().claimed_at)],
    ["Updated", formatTimestamp(props.application().updated_at)],
  ];

  return (
    <section class={styles.detailCard} aria-labelledby="application-metadata-title">
      <div class={styles.detailCardHeader}>
        <h3 id="application-metadata-title">Application metadata</h3>
        <span data-testid="application-detail-version">Version {props.application().version}</span>
      </div>
      <dl class={styles.metadataList}>
        <For each={rows()}>
          {(row) => (
            <div>
              <dt>{row()[0]}</dt>
              <dd data-testid={row()[0] === "State" ? "application-detail-state" : undefined}>
                {row()[1]}
              </dd>
            </div>
          )}
        </For>
      </dl>
    </section>
  );
}

export function ApplicationResponsesPanel(props: ApplicationResponsesPanelProps): JSX.Element {
  const responses = () => Object.entries(props.application().responses);

  return (
    <section class={styles.detailCard} aria-labelledby="application-responses-title">
      <h3 id="application-responses-title">Responses</h3>
      <dl class={styles.responseList}>
        <For each={responses()} fallback={<p class="runtimeCopy">No responses were recorded.</p>}>
          {(entry) => (
            <div>
              <dt>{entry()[0]}</dt>
              <dd>{renderValue(entry()[1])}</dd>
            </div>
          )}
        </For>
      </dl>
    </section>
  );
}

export function ApplicationTranscriptList(props: ApplicationTranscriptListProps): JSX.Element {
  return (
    <section
      class={styles.detailCard}
      aria-labelledby="application-transcript-title"
      data-testid="application-transcript"
    >
      <h3 id="application-transcript-title">Transcript</h3>
      <ol class={styles.transcriptList}>
        <For
          each={props.entries()}
          fallback={<p class="runtimeCopy">No transcript entries were recorded.</p>}
        >
          {(entry) => <TranscriptEntryView entry={entry()} />}
        </For>
      </ol>
    </section>
  );
}

function DetailLayout(props: DetailLayoutProps): JSX.Element {
  return (
    <div class={styles.detailLayout} data-application-id={props.read().id}>
      <div class={styles.detailColumn}>
        <ApplicationMetadataPanel application={props.read} />
        <ApplicationResponsesPanel application={props.read} />
        <ApplicationMessageComposer
          applicationId={() => props.read().id}
          disabled={props.loading()}
          onMessageAppended={props.onMessageAppended}
          onError={props.onError}
        />
        <ApplicationTransitionActions
          application={props.read}
          disabled={props.loading()}
          onTransitioned={props.onTransitioned}
          onError={props.onError}
        />
      </div>
      <ApplicationTranscriptList entries={() => props.readTranscript().entries} />
    </div>
  );
}

export function ApplicationDetailRoute(): JSX.Element {
  const params = useParams({ from: "/applications/$applicationId" });
  const [principal, setPrincipal] = createSignal<CurrentPrincipal | null>(null);
  const [principalStatus, setPrincipalStatus] = createSignal<"loading" | "ready" | "auth-error">(
    "loading",
  );
  const [application, setApplication] = createSignal<ApplicationRead | null>(null);
  const [transcript, setTranscript] = createSignal<ApplicationTranscriptRead | null>(null);
  const [notice, setNotice] = createSignal<string | null>(null);
  const [loading, setLoading] = createSignal(false);

  const applicationId = () => {
    return params().applicationId;
  };

  async function loadDetail(id: string, options: { readonly preserveNotice?: boolean } = {}) {
    setLoading(true);
    if (!options.preserveNotice) setNotice(null);
    try {
      const [nextApplication, nextTranscript] = await Promise.all([
        fetchOfficerApplication(id),
        fetchOfficerApplicationTranscript(id),
      ]);
      setApplication(nextApplication);
      setTranscript(nextTranscript);
    } catch (error) {
      setApplication(null);
      setTranscript(null);
      setNotice(detailNotice(error));
    } finally {
      setLoading(false);
    }
  }

  async function loadTranscript(id: string) {
    try {
      setTranscript(await fetchOfficerApplicationTranscript(id));
    } catch (error) {
      setNotice(detailNotice(error));
    }
  }

  async function handleMessageAppended(_message: ApplicationMessageRead) {
    setNotice(null);
    await loadTranscript(applicationId());
  }

  async function handleTransitioned(nextApplication: ApplicationRead) {
    setApplication(nextApplication);
    setNotice(null);
    await loadTranscript(applicationId());
  }

  async function handleActionError(message: string, status?: number) {
    setNotice(message);
    if (status === 409 || status === 412 || status === 428) {
      await loadDetail(applicationId(), { preserveNotice: true });
    }
  }

  async function bootstrap() {
    try {
      const nextPrincipal = await fetchCurrentPrincipal();
      setPrincipal(nextPrincipal);
      setPrincipalStatus("ready");
      if (nextPrincipal.groups.includes("officers") && nextPrincipal.discord_user_id) {
        await loadDetail(applicationId());
      }
    } catch (error) {
      console.error("[ApplicationDetailRoute] Principal bootstrap failed", error);
      setPrincipalStatus("auth-error");
    }
  }

  onMount(() => {
    void bootstrap();
  });

  const principalReady = () => principalStatus() === "ready" && principal() !== null;
  const canReview = () => {
    const current = principal();
    return (
      current !== null && current.groups.includes("officers") && current.discord_user_id !== null
    );
  };

  return (
    <section class={styles.queuePanel} aria-labelledby="application-detail-title">
      <div class={styles.header}>
        <div>
          <p class="eyebrow">Officer review</p>
          <h2 id="application-detail-title">Application detail</h2>
        </div>
        <div class={styles.headerActions}>
          <Link class={styles.detailLink} to="/applications/queue">
            Queue
          </Link>
          <Button
            type="button"
            variant="secondary"
            disabled={!canReview() || loading()}
            onClick={() => void loadDetail(applicationId())}
          >
            Refresh
          </Button>
        </div>
      </div>

      <Show when={principalStatus() === "loading"}>
        <p class="runtimeCopy">Authentication required.</p>
      </Show>
      <Show when={principalStatus() === "auth-error"}>
        <p class="runtimeCopy">Authentication required. Sign in with Pomerium.</p>
      </Show>
      <Show when={principalReady() && principal() && !principal()?.groups.includes("officers")}>
        <p class="runtimeCopy">Officer access forbidden.</p>
      </Show>
      <Show
        when={
          principalReady() &&
          principal()?.groups.includes("officers") &&
          !principal()?.discord_user_id
        }
      >
        <p class="runtimeCopy">
          Discord identity incomplete. Officer Discord identity is required.
        </p>
      </Show>

      <Show when={notice()}>
        {(message) => (
          <p class={styles.notice} role="status">
            {message()}
          </p>
        )}
      </Show>

      <Show when={loading()}>
        <p class="runtimeCopy">Loading application detail.</p>
      </Show>

      <Show when={canReview() && application() !== null && transcript() !== null}>
        <DetailLayout
          read={() => application()!}
          readTranscript={() => transcript()!}
          loading={loading}
          onMessageAppended={handleMessageAppended}
          onTransitioned={handleTransitioned}
          onError={handleActionError}
        />
      </Show>
    </section>
  );
}
