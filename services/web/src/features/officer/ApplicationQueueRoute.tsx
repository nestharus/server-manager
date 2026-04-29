import { Link } from "@tanstack/solid-router";
import { For, Show, createSignal, onMount } from "solid-js";

import {
  ApiError,
  claimOfficerApplication,
  fetchCurrentPrincipal,
  fetchOfficerApplicationQueue,
  type ApplicationRead,
  type ApplicationState,
  type CurrentPrincipal,
} from "@/api/client";
import { Button } from "@/components/primitives/Button";

import styles from "./officer.module.css";

const ALL_STATES: ApplicationState[] = [
  "submitted",
  "queued",
  "claimed",
  "in_review",
  "interview",
  "waitlisted",
  "approved",
  "denied",
  "withdrawn",
];
const DEFAULT_STATES: ApplicationState[] = ["submitted", "queued"];

function shortId(value: string | null) {
  return value === null ? "" : value.slice(0, 8);
}

function claimNotice(status: number) {
  if (status === 409) return "Conflict: application was already claimed.";
  if (status === 412) return "Stale version. Refreshing queue.";
  if (status === 428) return "Precondition required. Refreshing queue.";
  if (status === 403) return "Forbidden: not allowed to claim this application.";
  return `Claim failed with status ${status}.`;
}

export function ApplicationQueueRoute() {
  const [principal, setPrincipal] = createSignal<CurrentPrincipal | null>(null);
  const [principalStatus, setPrincipalStatus] = createSignal<"loading" | "ready" | "auth-error">(
    "loading",
  );
  const [selectedStates, setSelectedStates] = createSignal<ApplicationState[]>(DEFAULT_STATES);
  const [items, setItems] = createSignal<ApplicationRead[]>([]);
  const [nextAfterId, setNextAfterId] = createSignal<string | null>(null);
  const [claimingId, setClaimingId] = createSignal<string | null>(null);
  const [notice, setNotice] = createSignal<string | null>(null);
  const [forbiddenClaimIds, setForbiddenClaimIds] = createSignal<Set<string>>(new Set());

  async function loadQueue(
    mode: "replace" | "append",
    afterId?: string | null,
    states: readonly ApplicationState[] = selectedStates(),
  ) {
    try {
      const response = await fetchOfficerApplicationQueue({
        states,
        afterId,
      });
      setItems((current) => (mode === "append" ? [...current, ...response.items] : response.items));
      setNextAfterId(response.next_after_id);
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0;
      setNotice(status === 0 ? "Network error loading queue." : `Queue load failed (${status}).`);
    }
  }

  async function bootstrap() {
    try {
      const nextPrincipal = await fetchCurrentPrincipal();
      setPrincipal(nextPrincipal);
      setPrincipalStatus("ready");
      if (nextPrincipal.groups.includes("officers") && nextPrincipal.discord_user_id) {
        await loadQueue("replace");
      }
    } catch {
      setPrincipalStatus("auth-error");
    }
  }

  async function toggleState(state: ApplicationState) {
    const current = selectedStates();
    const next = current.includes(state)
      ? current.filter((candidate) => candidate !== state)
      : [...current, state];
    const effectiveStates = next.length > 0 ? next : current;
    setSelectedStates(effectiveStates);
    setNotice(null);
    await loadQueue("replace", undefined, effectiveStates);
  }

  async function claim(application: ApplicationRead) {
    setClaimingId(application.id);
    setNotice(null);
    try {
      await claimOfficerApplication({
        applicationId: application.id,
        expectedVersion: application.version,
      });
      await loadQueue("replace");
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0;
      setNotice(claimNotice(status));
      if (status === 403) {
        setForbiddenClaimIds((current) => new Set([...current, application.id]));
      }
      await loadQueue("replace");
    } finally {
      setClaimingId(null);
    }
  }

  onMount(() => {
    void bootstrap();
  });

  const principalReady = () => principalStatus() === "ready" && principal() !== null;
  const canReview = () => {
    const current = principal();
    return current !== null && current.groups.includes("officers") && current.discord_user_id !== null;
  };

  return (
    <section class={styles.queuePanel} aria-labelledby="queue-title">
      <div class={styles.header}>
        <div>
          <p class="eyebrow">Officer review</p>
          <h2 id="queue-title">Application queue</h2>
        </div>
        <Button type="button" variant="secondary" onClick={() => void loadQueue("replace")}>
          Refresh
        </Button>
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
      <Show when={principalReady() && principal()?.groups.includes("officers") && !principal()?.discord_user_id}>
        <p class="runtimeCopy">Discord identity incomplete. Officer Discord identity is required.</p>
      </Show>

      <Show when={canReview()}>
        <div class={styles.filters} aria-label="Application states">
          <For each={ALL_STATES}>
            {(state) => (
              <button
                type="button"
                class={selectedStates().includes(state()) ? styles.selectedFilter : styles.filter}
                aria-pressed={selectedStates().includes(state()) ? "true" : "false"}
                onClick={() => void toggleState(state())}
              >
                {state()}
              </button>
            )}
          </For>
        </div>

        <Show when={notice()}>
          {(message) => (
            <p class={styles.notice} role="status">
              {message()}
            </p>
          )}
        </Show>

        <div class={styles.queueTable} role="table" aria-label="Application queue">
          <div class={styles.tableHeader} role="row">
            <span>Applicant</span>
            <span>State</span>
            <span>Submitted</span>
            <span>Version</span>
            <span>Owner</span>
            <span>Action</span>
          </div>
          <For each={items()}>
            {(application) => (
              <div
                class={styles.tableRow}
                role="row"
                data-application-id={application().id}
              >
                <span>{shortId(application().applicant_id)}</span>
                <span>{application().state}</span>
                <span>{new Date(application().submitted_at).toLocaleString()}</span>
                <span>{application().version}</span>
                <span>{shortId(application().owner_id)}</span>
                <span class={styles.rowActions}>
                  <Link
                    class={styles.detailLink}
                    to="/applications/$applicationId"
                    params={{ applicationId: application().id }}
                  >
                    View
                  </Link>
                  <Show
                    when={
                      application().state === "queued" && !forbiddenClaimIds().has(application().id)
                    }
                  >
                    <Button
                      type="button"
                      disabled={claimingId() === application().id}
                      onClick={() => void claim(application())}
                    >
                      Claim
                    </Button>
                  </Show>
                </span>
              </div>
            )}
          </For>
        </div>

        <Show when={nextAfterId() !== null}>
          <Button type="button" variant="secondary" onClick={() => void loadQueue("append", nextAfterId())}>
            Load more
          </Button>
        </Show>
      </Show>
    </section>
  );
}
