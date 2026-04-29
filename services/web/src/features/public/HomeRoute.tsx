import { useNavigate } from "@tanstack/solid-router";

import { Meter } from "@/components/gap/Meter";
import { Button } from "@/components/primitives/Button";

export function HomeRoute() {
  const navigate = useNavigate();

  return (
    <div class="runtimeGrid">
      <section class="runtimePanel" aria-labelledby="public-title">
        <p class="eyebrow">Public surface</p>
        <h2 id="public-title">Humility applications</h2>
        <p class="runtimeCopy">
          Public application intake stays available while officer-only tools remain auth-gated.
        </p>
        <Meter label="Substrate coverage" value={78} />
        <Button
          id="start-application"
          type="button"
          onClick={async () => {
            await navigate({ to: "/applications" });
          }}
        >
          Start application
        </Button>
      </section>
      <aside class="runtimePanel">
        <h2>Route status</h2>
        <pre>Public route ready</pre>
      </aside>
    </div>
  );
}
