import { createSignal } from "solid-js";

import { ArkCombobox } from "@/components/primitives/ArkCombobox";
import { ArkDialog } from "@/components/primitives/ArkDialog";
import { ArkTabs } from "@/components/primitives/ArkTabs";
import { Button } from "@/components/primitives/Button";
import { Meter } from "@/components/gap/Meter";
import { DarkNemesisForm } from "@/features/forms/DarkNemesisForm";

import styles from "./home.module.css";

const chapterOptions = [
  { label: "Dark Nemesis", value: "dark-nemesis" },
  { label: "General roster", value: "general" },
  { label: "Officer review", value: "officer-review" },
];

export function HomeRoute() {
  const [submitted, setSubmitted] = createSignal<string | null>(null);

  return (
    <div class={styles.layout}>
      <section class={styles.publicPanel} aria-labelledby="public-title">
        <div>
          <p class="eyebrow">Public surface</p>
          <h2 id="public-title">Dark Nemesis application</h2>
          <p>
            This route stays public. Pomerium only gates the admin path, while form submission
            contracts remain API-owned.
          </p>
        </div>
        <Meter label="Substrate coverage" value={78} />
        <ArkTabs
          left={<DarkNemesisForm onSubmitPreview={setSubmitted} />}
          right={
            <div class={styles.componentCheck}>
              <ArkCombobox label="Preview surface" options={chapterOptions} />
              <ArkDialog title="Ark UI compatibility gate" trigger="Open dialog">
                Ark UI Solid primitives render in the Solid 2 beta runtime. The release gate test
                covers dialog, select, combobox, tabs, and keyboard toolbar behavior before INIT-118
                can release.
              </ArkDialog>
            </div>
          }
        />
      </section>
      <aside class={styles.previewPanel} aria-label="Submission preview">
        <h2>Submission payload</h2>
        <pre>{submitted() ?? "No local preview submitted yet."}</pre>
        <Button type="button" variant="secondary" onClick={() => setSubmitted(null)}>
          Clear
        </Button>
      </aside>
    </div>
  );
}
