import { Link, useMatches } from "@tanstack/solid-router";
import { For, createMemo } from "solid-js";

import styles from "./gap.module.css";

interface BreadcrumbStaticData {
  readonly breadcrumb?: string;
}

export function Breadcrumbs() {
  const matches = useMatches();
  const crumbs = createMemo(() =>
    matches()
      .map((match) => ({
        pathname: match.pathname,
        label: (match.staticData as BreadcrumbStaticData | undefined)?.breadcrumb,
      }))
      .filter((crumb): crumb is { pathname: string; label: string } => Boolean(crumb.label)),
  );

  return (
    <nav class={styles.breadcrumbs} aria-label="Breadcrumbs">
      <ol>
        <li>
          <Link to="/">Home</Link>
        </li>
        <For each={crumbs()}>
          {(crumb) => (
            <li>
              <Link to={crumb().pathname}>{crumb().label}</Link>
            </li>
          )}
        </For>
      </ol>
    </nav>
  );
}
