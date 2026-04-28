import "./styles/layers.css";

const root = document.querySelector("#root");

if (!root) {
  throw new Error("missing #root");
}

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

const isApplications = () => window.location.pathname === "/applications";
const isAdmin = () => window.location.pathname.startsWith("/admin");

function shell(content: string) {
  return `
    <div class="appShell">
      <header class="appHeader">
        <div class="brandBlock">
          <span class="brandMark">H</span>
          <div><p class="eyebrow">Humility</p><h1>Server Manager</h1></div>
        </div>
        <nav class="topNav" aria-label="Primary">
          <a href="/" ${!isApplications() && !isAdmin() ? 'aria-current="page"' : ""}>Public</a>
          <a href="/applications" ${isApplications() ? 'aria-current="page"' : ""}>Application form</a>
          <a href="/admin/chapters" ${isAdmin() ? 'aria-current="page"' : ""}>Admin</a>
        </nav>
        <button class="themeButton" type="button" title="Toggle color theme">Theme</button>
      </header>
      <main class="appMain">${content}</main>
    </div>
  `;
}

function publicRoute() {
  return shell(`
    <div class="runtimeGrid">
      <section class="runtimePanel">
        <p class="eyebrow">Public surface</p>
        <h2>Humility applications</h2>
        <p class="runtimeCopy">Public application intake stays available while officer-only tools remain auth-gated.</p>
        <div class="meterGroup">
          <div class="meterLabel"><span>Substrate coverage</span><span>78/100</span></div>
          <meter class="meter" min="0" max="100" value="78">78</meter>
        </div>
        <button id="start-application" class="button primary" type="button">Start application</button>
      </section>
      <aside class="runtimePanel">
        <h2>Route status</h2>
        <pre>Public route ready</pre>
      </aside>
    </div>
  `);
}

function applicationRoute() {
  return shell(`
    <div class="runtimeGrid">
      <section class="runtimePanel">
        <p class="eyebrow">Application intake</p>
        <h2>Humility applications</h2>
        <div role="tablist" class="runtimeTabs">
          <button id="tab-overview" role="tab" aria-selected="true" type="button">Overview</button>
          <button id="tab-details" role="tab" aria-selected="false" type="button">Details</button>
        </div>
        <form id="application-form" class="runtimeStack" aria-label="Application form">
          <label class="runtimeField">
            <span>Character name</span>
            <input class="input" name="character_name" aria-label="Character name" required />
          </label>
          <label class="runtimeField">
            <span>Application text</span>
            <textarea class="input" name="application_text" aria-label="Application text" required></textarea>
          </label>
          <button class="button primary" type="submit">
            <span data-testid="application-submit-icon" aria-hidden="true">+</span>
            Submit application
          </button>
        </form>
        <div id="details-panel" class="runtimeStack" hidden>
          <span data-testid="application-status-icon" aria-hidden="true">i</span>
          <button id="open-details" class="button secondary" type="button">Open details</button>
        </div>
      </section>
      <aside class="runtimePanel" aria-live="polite">
        <h2>Submission status</h2>
        <pre id="submit-status">No application submitted yet.</pre>
      </aside>
    </div>
  `);
}

function adminRoute() {
  return shell(`
    <section class="runtimePanel">
      <p class="eyebrow">Auth-gated surface</p>
      <h2>Chapter administration</h2>
      <p class="runtimeCopy">Identity comes from Pomerium headers through the API.</p>
      <div data-testid="chapter-table" class="runtimeTable">
        <div>Chapter</div><div>State</div><div>Version</div><div>No chapters yet</div>
      </div>
    </section>
  `);
}

function render() {
  root.innerHTML = isAdmin() ? adminRoute() : isApplications() ? applicationRoute() : publicRoute();
  bindApplicationRoute();
}

function getClientApplicationId() {
  const storageKey = "humility.publicApplication.clientApplicationId";
  const existing = sessionStorage.getItem(storageKey);
  if (existing) return existing;
  const generated = crypto.randomUUID();
  sessionStorage.setItem(storageKey, generated);
  return generated;
}

function bindApplicationRoute() {
  const form = document.querySelector<HTMLFormElement>("#application-form");
  const status = document.querySelector<HTMLElement>("#submit-status");
  const overviewTab = document.querySelector<HTMLButtonElement>("#tab-overview");
  const detailsTab = document.querySelector<HTMLButtonElement>("#tab-details");
  const detailsPanel = document.querySelector<HTMLElement>("#details-panel");

  document.querySelector("#start-application")?.addEventListener("click", () => {
    window.location.assign("/applications");
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
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
    const response = await fetch("/api/public/applications", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    const body = (await response.json()) as { message?: string; application_id?: string };
    if (status) status.textContent = body.message ?? `Application returned ${response.status}`;
  });

  detailsTab?.addEventListener("click", () => {
    overviewTab?.setAttribute("aria-selected", "false");
    detailsTab.setAttribute("aria-selected", "true");
    detailsPanel?.removeAttribute("hidden");
  });

  document.querySelector("#open-details")?.addEventListener("click", () => {
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.className = "runtimeDialog";
    dialog.textContent = "Application details";
    detailsPanel?.append(dialog);
  });
}

render();
