import "./styles/layers.css";

const root = document.querySelector("#root");

if (!root) {
  throw new Error("missing #root");
}

root.innerHTML = `
  <div class="appShell">
    <header class="appHeader">
      <div class="brandBlock">
        <span class="brandMark">H</span>
        <div><p class="eyebrow">Humility</p><h1>Server Manager</h1></div>
      </div>
      <nav class="topNav" aria-label="Primary">
        <a href="/" aria-current="page">Public</a>
        <a href="/admin/chapters">Admin</a>
      </nav>
      <button class="themeButton" type="button" title="Toggle color theme">Theme</button>
    </header>
    <main class="appMain">
      <div class="runtimeGrid">
        <section class="runtimePanel">
          <p class="eyebrow">Public surface</p>
          <h2>Dark Nemesis application</h2>
          <p class="runtimeCopy">This route stays public. Pomerium only gates the admin path, while form submission contracts remain API-owned.</p>
          <div class="meterGroup">
            <div class="meterLabel"><span>Substrate coverage</span><span>78/100</span></div>
            <meter class="meter" min="0" max="100" value="78">78</meter>
          </div>
          <div role="tablist" class="runtimeTabs">
            <button id="tab-overview" role="tab" aria-selected="true" type="button">Overview</button>
            <button id="tab-details" role="tab" aria-selected="false" type="button">Details</button>
          </div>
          <div id="overview-panel" class="runtimeStack">
            <div class="runtimeFormHeader">
              <h3>Dark Nemesis Chapter Application</h3>
              <div role="toolbar" aria-label="Form actions" class="toolbar">
                <button role="button" type="button" tabindex="0">Draft</button>
                <button role="button" type="button" tabindex="-1">Reset</button>
              </div>
            </div>
            <label class="runtimeField"><span>What is your in-game name?</span><input class="input" aria-label="What is your in-game name?" /></label>
            <label class="runtimeField"><span>What is your timezone?</span><input class="input" /></label>
            <label class="runtimeField"><span>Which daily events do you attend?</span><input class="input" /></label>
            <button class="button primary" type="button">Preview submission</button>
          </div>
          <div id="details-panel" class="runtimeStack" hidden>
            <label class="runtimeField"><span>Preview surface</span><input class="input" value="Dark Nemesis" /></label>
            <button id="open-dialog" class="button secondary" type="button">Open dialog</button>
          </div>
        </section>
        <aside class="runtimePanel">
          <h2>Submission payload</h2>
          <pre>No local preview submitted yet.</pre>
        </aside>
      </div>
    </main>
  </div>
`;

const overviewTab = document.querySelector<HTMLButtonElement>("#tab-overview");
const detailsTab = document.querySelector<HTMLButtonElement>("#tab-details");
const overviewPanel = document.querySelector<HTMLElement>("#overview-panel");
const detailsPanel = document.querySelector<HTMLElement>("#details-panel");
const toolbar = document.querySelector<HTMLElement>('[role="toolbar"]');

detailsTab?.addEventListener("click", () => {
  overviewTab?.setAttribute("aria-selected", "false");
  detailsTab.setAttribute("aria-selected", "true");
  overviewPanel?.setAttribute("hidden", "");
  detailsPanel?.removeAttribute("hidden");
});

overviewTab?.addEventListener("click", () => {
  overviewTab.setAttribute("aria-selected", "true");
  detailsTab?.setAttribute("aria-selected", "false");
  detailsPanel?.setAttribute("hidden", "");
  overviewPanel?.removeAttribute("hidden");
});

document.querySelector("#open-dialog")?.addEventListener("click", () => {
  const dialog = document.createElement("div");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.className = "runtimeDialog";
  dialog.textContent =
    "Ark UI Solid primitives render through the release gate in the Solid 2 beta runtime.";
  detailsPanel?.append(dialog);
});

toolbar?.addEventListener("keydown", (event) => {
  const buttons = [...toolbar.querySelectorAll<HTMLButtonElement>("button")];
  const active = buttons.findIndex((button) => button === document.activeElement);
  const move = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
  if (move === 0) {
    return;
  }
  event.preventDefault();
  const next = (active + move + buttons.length) % buttons.length;
  buttons.forEach((button, index) => button.setAttribute("tabindex", index === next ? "0" : "-1"));
  buttons[next]?.focus();
});
