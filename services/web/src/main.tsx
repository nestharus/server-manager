import "./styles/layers.css";

const rootElement = document.querySelector<HTMLElement>("#root");

if (!rootElement) {
  throw new Error("missing #root");
}

const root: HTMLElement = rootElement;

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

type ApplicantDiscordMe = {
  discord_user_id: string;
};

type ApplicantAuthState =
  | { status: "checking" }
  | { status: "anonymous" }
  | { status: "verified"; discord_user_id: string; expires_at: number };

let applicantAuthState: ApplicantAuthState = { status: "checking" };
let applicantReceiptExpiryTimer: number | undefined;

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
  const verified = applicantAuthState.status === "verified";
  let loginState = "Not logged in with Discord.";
  if (applicantAuthState.status === "checking") {
    loginState = "Checking Discord login...";
  } else if (applicantAuthState.status === "verified") {
    loginState = `Logged in as Discord ${applicantAuthState.discord_user_id}`;
  }
  const formMarkup = verified
    ? `
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
      `
    : `
        <div class="runtimeStack" aria-live="polite">
          <button id="discord-login" class="button primary" type="button">Login with Discord</button>
        </div>
      `;
  return shell(`
    <div class="runtimeGrid">
      <section class="runtimePanel">
        <p class="eyebrow">Application intake</p>
        <h2>Humility applications</h2>
        <div role="tablist" class="runtimeTabs">
          <button id="tab-overview" role="tab" aria-selected="true" type="button">Overview</button>
          <button id="tab-details" role="tab" aria-selected="false" type="button">Details</button>
        </div>
        ${formMarkup}
        <p id="discord-login-state" class="runtimeCopy" aria-live="polite">${loginState}</p>
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
  const discordLogin = document.querySelector<HTMLButtonElement>("#discord-login");
  const overviewTab = document.querySelector<HTMLButtonElement>("#tab-overview");
  const detailsTab = document.querySelector<HTMLButtonElement>("#tab-details");
  const detailsPanel = document.querySelector<HTMLElement>("#details-panel");

  document.querySelector("#start-application")?.addEventListener("click", () => {
    window.location.assign("/applications");
  });

  discordLogin?.addEventListener("click", () => {
    window.location.assign("/auth/discord/start?return_to=/applications");
  });

  if (isApplications() && shouldProbeApplicantReceipt()) {
    void refreshApplicantDiscordState();
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const identity = await fetchApplicantDiscordIdentity();
    if (!identity) {
      preserveApplicationDraft(form);
      redirectToDiscordAuth();
      return;
    }
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
    const body = (await response.json().catch(() => ({}))) as {
      code?: string;
      message?: string;
      application_id?: string;
    };
    if (response.status === 401 && body.code === "applicant_receipt_required") {
      preserveApplicationDraft(form);
      redirectToDiscordAuth();
      return;
    }
    if (status) status.textContent = body.message ?? `Application returned ${response.status}`;
  });

  if (form) {
    restoreApplicationDraft(form);
  }

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

function shouldProbeApplicantReceipt() {
  return (
    applicantAuthState.status === "checking" ||
    (applicantAuthState.status === "verified" && Date.now() >= applicantAuthState.expires_at)
  );
}

async function fetchApplicantDiscordIdentity(): Promise<ApplicantDiscordMe | null> {
  try {
    const response = await fetch("/auth/discord/me", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return null;
    const body = (await response.json()) as ApplicantDiscordMe;
    return body.discord_user_id ? body : null;
  } catch {
    return null;
  }
}

async function refreshApplicantDiscordState() {
  const identity = await fetchApplicantDiscordIdentity();
  if (!identity) {
    applicantAuthState = { status: "anonymous" };
    render();
    return;
  }
  applicantAuthState = {
    status: "verified",
    discord_user_id: identity.discord_user_id,
    expires_at: Date.now() + 9 * 60 * 1000,
  };
  if (applicantReceiptExpiryTimer !== undefined) {
    window.clearTimeout(applicantReceiptExpiryTimer);
  }
  applicantReceiptExpiryTimer = window.setTimeout(() => {
    applicantAuthState = { status: "checking" };
    render();
  }, 9 * 60 * 1000);
  render();
}

function redirectToDiscordAuth() {
  window.location.assign("/auth/discord/start?return_to=/applications");
}

function preserveApplicationDraft(form: HTMLFormElement) {
  const formData = new FormData(form);
  sessionStorage.setItem(
    "humility.publicApplication.draft",
    JSON.stringify({
      character_name: String(formData.get("character_name") ?? ""),
      application_text: String(formData.get("application_text") ?? ""),
    }),
  );
}

function restoreApplicationDraft(form: HTMLFormElement) {
  const raw = sessionStorage.getItem("humility.publicApplication.draft");
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
    sessionStorage.removeItem("humility.publicApplication.draft");
  }
}

render();
