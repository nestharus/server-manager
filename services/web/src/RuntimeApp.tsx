import { For, Show, createSignal } from "solid-js";

import { Icon } from "@/components/icons/Icon";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import { Meter } from "@/components/gap/Meter";
import { Toolbar } from "@/components/gap/Toolbar";
import { darkNemesisForm } from "@/features/forms/schema";

import "./styles/layers.css";

function PublicSurface() {
  const [tab, setTab] = createSignal<"overview" | "details">("overview");
  const [dialogOpen, setDialogOpen] = createSignal(false);
  const [payload, setPayload] = createSignal("No local preview submitted yet.");

  return (
    <div class="appMain">
      <div class="runtimeGrid">
        <section class="runtimePanel">
          <p class="eyebrow">Public surface</p>
          <h2>Dark Nemesis application</h2>
          <p class="runtimeCopy">
            This route stays public. Pomerium only gates the admin path, while form submission
            contracts remain API-owned.
          </p>
          <Meter label="Substrate coverage" value={78} />
          <div role="tablist" class="runtimeTabs">
            <button
              role="tab"
              aria-selected={tab() === "overview" ? "true" : "false"}
              type="button"
              onClick={() => setTab("overview")}
            >
              Overview
            </button>
            <button
              role="tab"
              aria-selected={tab() === "details" ? "true" : "false"}
              type="button"
              onClick={() => setTab("details")}
            >
              Details
            </button>
          </div>
          <Show
            when={tab() === "overview"}
            fallback={
              <div class="runtimeStack">
                <label class="runtimeField">
                  <span>Preview surface</span>
                  <Input value="Dark Nemesis" />
                </label>
                <Button type="button" variant="secondary" onClick={() => setDialogOpen(true)}>
                  Open dialog
                </Button>
                <Show when={dialogOpen()}>
                  <div role="dialog" aria-modal="true" class="runtimeDialog">
                    <h3>Ark UI compatibility gate</h3>
                    <p>
                      Ark UI Solid primitives are installed and statically wired; this release gate
                      keeps a rendered dialog interaction in the Solid 2 beta runtime.
                    </p>
                    <Button type="button" onClick={() => setDialogOpen(false)}>
                      Close
                    </Button>
                  </div>
                </Show>
              </div>
            }
          >
            <form
              class="runtimeStack"
              aria-label={darkNemesisForm.title}
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                setPayload(JSON.stringify(Object.fromEntries(data.entries()), null, 2));
              }}
            >
              <div class="runtimeFormHeader">
                <h3>{darkNemesisForm.title}</h3>
                <Toolbar
                  label="Form actions"
                  actions={[
                    {
                      id: "draft",
                      label: "Draft",
                      onPress: () => setPayload("Draft saved locally."),
                    },
                    {
                      id: "reset",
                      label: "Reset",
                      onPress: () => setPayload("No local preview submitted yet."),
                    },
                  ]}
                />
              </div>
              <For each={darkNemesisForm.questions}>
                {(question) => (
                  <label class="runtimeField">
                    <span>{question().label}</span>
                    <Input
                      name={question().id}
                      type={question().type === "number" ? "number" : "text"}
                      required={question().required}
                      maxlength={question().max_length}
                    />
                  </label>
                )}
              </For>
              <Button type="submit">Preview submission</Button>
            </form>
          </Show>
        </section>
        <aside class="runtimePanel">
          <h2>Submission payload</h2>
          <pre>{payload()}</pre>
        </aside>
      </div>
    </div>
  );
}

function AdminSurface() {
  return (
    <div class="appMain">
      <section class="runtimePanel">
        <p class="eyebrow">Auth-gated surface</p>
        <h2>Chapter administration</h2>
        <p class="runtimeCopy">
          Identity comes from Pomerium headers through the API. The SPA does not own tokens or OIDC
          state.
        </p>
        <div data-testid="chapter-table" class="runtimeTable">
          <div>Chapter</div>
          <div>State</div>
          <div>Version</div>
          <div>No chapters yet</div>
        </div>
      </section>
    </div>
  );
}

export function RuntimeApp() {
  const isAdmin = window.location.pathname.startsWith("/admin");
  return (
    <div class="appShell">
      <header class="appHeader">
        <div class="brandBlock">
          <span class="brandMark">H</span>
          <div>
            <p class="eyebrow">Humility</p>
            <h1>Server Manager</h1>
          </div>
        </div>
        <nav class="topNav" aria-label="Primary">
          <a href="/" aria-current={!isAdmin ? "page" : undefined}>
            Public
          </a>
          <a href="/admin/chapters" aria-current={isAdmin ? "page" : undefined}>
            Admin
          </a>
        </nav>
        <Button
          variant="ghost"
          type="button"
          title="Toggle color theme"
          onClick={() => {
            const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
            document.documentElement.dataset.theme = next;
          }}
        >
          <Icon name="circle-half-stroke" title="Theme" />
        </Button>
      </header>
      {isAdmin ? <AdminSurface /> : <PublicSurface />}
    </div>
  );
}
